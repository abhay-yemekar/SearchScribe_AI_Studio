"""Opt-in, isolated generation evaluation; no network or app imports on a dry run.

From backend/: python scripts/evaluate_generation.py --provider gemini --model MODEL
Add --live to execute. Reports go to ignored .cache/evaluation/, never the app DB.
Frozen public research bundles use {"version": 1, "bundles": [{"id": CASE_ID,
"query": EXACT_QUERY, "summary": ResearchSummary, "context": PUBLIC_EXCERPTS}]}.
Neither schema scores nor retrieved sources certify factual accuracy.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
DEFAULT_CASES = BACKEND_ROOT / "evaluation" / "prompts.json"
MAX_CASES = 20
MAX_BUNDLE_BYTES = 512_000
DECLINED_CODES = {
    "RESEARCH_NOT_CONFIGURED", "CURRENT_SOURCES_NOT_FOUND", "CURRENT_SOURCES_UNAVAILABLE",
}


class ObservedProvider:
    """Observe validated outputs; routing, rendering and storage stay real."""

    def __init__(self, inner: Any, articles: list[Any]) -> None:
        self.inner = inner
        self.articles = articles
        self.name = inner.name
        self.model = inner.model

    def generate(self, *args: Any, **kwargs: Any) -> Any:
        from app.ai.schemas import GeneratedArticle

        response = self.inner.generate(*args, **kwargs)
        if isinstance(response.data, GeneratedArticle):
            self.articles.append(response.data)
        return response


def load_cases(path: Path = DEFAULT_CASES) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("Evaluation prompts require version 1.")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise ValueError("Evaluation requires 1 through 20 cases.")
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict) or any(
            not isinstance(case.get(field), str) or not case[field].strip()
            for field in ("id", "query", "category")
        ):
            raise ValueError("Every case needs an ID, query and category.")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", case["id"]):
            raise ValueError("Case IDs must be lowercase words separated by hyphens.")
        if case["id"] in seen or len(case["query"]) > 500:
            raise ValueError("Case IDs must be unique and queries at most 500 characters.")
        seen.add(case["id"])
    return cases


def select_cases(
    cases: list[dict[str, str]], ids: list[str], limit: int,
) -> list[dict[str, str]]:
    if not 1 <= limit <= MAX_CASES:
        raise ValueError("Limit must be between 1 and 20.")
    unknown = set(ids) - {case["id"] for case in cases}
    if unknown:
        raise ValueError("An unknown evaluation case ID was selected.")
    return [case for case in cases if not ids or case["id"] in ids][:limit]


def bootstrap_cli() -> None:
    """Override only this process, before importing any application module."""
    sys.path.insert(0, str(BACKEND_ROOT))
    os.environ.update({
        "APP_ENV": "test", "DATABASE_URL": "sqlite://", "AI_PROVIDER": "mock",
        "AI_FALLBACK_PROVIDER": "", "AI_FALLBACK_MODEL": "", "AI_MAX_RETRIES": "0",
        "MAIL_PROVIDER": "disabled", "GOOGLE_CLIENT_ID": "",
    })


@contextmanager
def evaluation_settings(provider: str, model: str) -> Iterator[None]:
    from app.ai.factory import reset_provider_cache
    from app.core.config import settings

    overrides = {
        "app_env": "test", "database_url": "sqlite://", "ai_provider": provider,
        "ai_model": model, "ai_max_retries": 0, "ai_fallback_provider": "",
        "ai_fallback_model": "", "mail_provider": "disabled", "google_client_id": "",
    }
    original = {name: getattr(settings, name) for name in overrides}
    previous_logging = logging.root.manager.disable
    try:
        for name, value in overrides.items():
            setattr(settings, name, value)
        reset_provider_cache()
        # Never print SDK exception bodies, prompts or credential-bearing transport logs.
        logging.disable(logging.CRITICAL)
        yield
    finally:
        for name, value in original.items():
            setattr(settings, name, value)
        reset_provider_cache()
        logging.disable(previous_logging)


def load_source_bundles(path: Path, cases: list[dict[str, str]]) -> dict[str, Any]:
    from app.ai.research import ResearchResult
    from app.ai.schemas import ResearchSummary
    from app.core.config import settings

    if path.stat().st_size > MAX_BUNDLE_BYTES:
        raise ValueError("Source bundle file exceeds the evaluation size limit.")
    with path.open("rb") as source_file:
        raw = source_file.read(MAX_BUNDLE_BYTES + 1)
    if len(raw) > MAX_BUNDLE_BYTES:
        raise ValueError("Source bundle file exceeds the evaluation size limit.")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("Source bundles require version 1.")
    entries = payload.get("bundles")
    if not isinstance(entries, list) or len(entries) > MAX_CASES:
        raise ValueError("Source bundles must contain at most 20 entries.")
    expected = {case["id"]: case["query"] for case in cases}
    bundles: dict[str, Any] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Invalid source bundle entry.")
        case_id = entry.get("id")
        if case_id not in expected:
            continue
        if entry.get("query") != expected[case_id] or case_id in bundles:
            raise ValueError("Source bundle query must exactly match its unique case.")
        context = entry.get("context")
        if not isinstance(context, str) or len(context) > settings.research_max_context_chars:
            raise ValueError("Source context must fit the existing research budget.")
        summary = ResearchSummary.model_validate(entry.get("summary"))
        source_ids = {source.id for source in summary.sources}
        if len(source_ids) != len(summary.sources) or any(
            not re.search(rf"\b{source_id}\b", context) for source_id in source_ids
        ):
            raise ValueError("Source bundle IDs must be unique and present in the context.")
        if bool(summary.sources) != (summary.status == "sources_retrieved"):
            raise ValueError("Source bundle status and source count do not agree.")
        if summary.sources and not summary.retrieved_at:
            raise ValueError("Sourced bundles need a retrieval timestamp.")
        if summary.retrieved_at:
            moment = datetime.fromisoformat(summary.retrieved_at.replace("Z", "+00:00"))
            if moment.tzinfo is None:
                raise ValueError("Source bundle timestamp must include a timezone.")
        bundles[case_id] = ResearchResult(
            summary, context, None if summary.sources else "no_evidence",
        )
    if set(bundles) != set(expected):
        raise ValueError("Every selected case must have an exact source bundle.")
    return bundles


def citation_metrics(article: Any) -> dict[str, Any]:
    # The generated Sources bibliography proves no claim; inspect body fields only.
    body = "\n".join([
        article.title, article.introduction, article.conclusion,
        *(text for section in article.sections for text in (
            section.heading, *section.paragraphs, *section.bullets,
        )),
    ])
    brackets = re.findall(r"\[[^\]\n]*\]", body)
    claimed = {
        source_id for bracket in brackets for source_id in re.findall(r"\bS\d+\b", bracket)
    }
    available = {source.id for source in article.research.sources}
    return {
        "body_citation_ids": sorted(claimed),
        "unsupported_citation_ids": sorted(claimed - available),
        "cited_source_count": len(claimed & available),
        "body_citations_present": bool(claimed),
        "citation_support_accuracy": "not_evaluated_requires_human_review",
    }


def article_metrics(article: Any, seo: Any) -> dict[str, Any]:
    from app.ai.schemas import SeoCandidate
    from app.ai.validation import validate_generated_seo

    candidate = SeoCandidate.model_validate(seo.model_dump())
    return {
        **citation_metrics(article), "schema_valid": True, "word_count": article.word_count,
        "seo_review_status": seo.review_status,
        "seo_fallback_used": seo.review_status == "needs_review",
        "seo_bounds_and_complete_ending": validate_generated_seo(candidate) is not None,
        "seo_title_characters": len(seo.title),
        "seo_description_characters": len(seo.description),
        "distinct_keywords": len({word.casefold().strip() for word in seo.keywords}),
    }


def research_metrics(research: Any, query: str) -> dict[str, Any]:
    from app.ai.research import _recent_window, _reported_date, needs_current_sources

    today = datetime.now(UTC).date()
    sources = research.summary.sources
    window = _recent_window(query, today)
    dates = [_reported_date(source) for source in sources]
    matching = (
        sum(moment is not None and window[0] <= moment <= window[1] for moment in dates)
        if window else None
    )
    return {
        "current_topic": needs_current_sources(query), "source_count": len(sources),
        "research_status": research.summary.status, "research_failure": research.failure,
        "reported_dated_source_count": sum(moment is not None for moment in dates),
        "within_requested_window_count": matching,
        "requested_window_utc": [day.isoformat() for day in window] if window else None,
        "coverage_reference_utc_date": today.isoformat(),
        "retrieved_at": research.summary.retrieved_at,
        "coverage_is_not_fact_checking": True,
    }


def collect_sources(
    cases: list[dict[str, str]], *, case_delay_seconds: float = 0,
    on_case: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Freeze the real search stage once, with no model or application database."""
    from app.ai.research import retrieve_sources

    if not 1 <= len(cases) <= MAX_CASES:
        raise ValueError("Source collection requires 1 through 20 selected cases.")
    if not math.isfinite(case_delay_seconds) or not 0 <= case_delay_seconds <= 60:
        raise ValueError("Evaluation case delay must be between 0 and 60 seconds.")
    started = datetime.now(UTC).isoformat()
    results = []
    with evaluation_settings("mock", "mock-1"):
        for index, case in enumerate(cases):
            if index and case_delay_seconds:
                time.sleep(case_delay_seconds)
            tick = time.perf_counter()
            research = retrieve_sources(case["query"])
            result = {
                **case, **research_metrics(research, case["query"]),
                "status": "sources_collected" if research.summary.sources else "no_evidence",
                "elapsed_ms": round((time.perf_counter() - tick) * 1000),
                "research": {"summary": research.summary.model_dump(), "context": research.context},
            }
            results.append(result)
            if on_case:
                on_case({
                    "case_id": case["id"], "completed": len(results), "total": len(cases),
                    "status": result["status"], "elapsed_ms": result["elapsed_ms"],
                })
    return {
        "version": 1, "started_at_utc": started, "finished_at_utc": datetime.now(UTC).isoformat(),
        "research_mode": "live_public_search_only", "model_calls": 0, "database_access": False,
        "selected_cases": len(results),
        "status_counts": dict(Counter(r["status"] for r in results)),
        "case_delay_seconds": case_delay_seconds,
        "accuracy": "not_evaluated_human_review_required", "results": results,
    }


def run_evaluation(
    cases: list[dict[str, str]], *, provider: str, model: str,
    source_bundles: Path | None = None,
    case_delay_seconds: float = 0,
    on_case: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.ai.schemas import GeneratedArticle, ResearchSummary
    from app.core.exceptions import AppError
    from app.db.base import Base
    from app.db.models import Generation, User
    from app.services import generation_service

    if not 1 <= len(cases) <= MAX_CASES:
        raise ValueError("Evaluation execution requires 1 through 20 selected cases.")
    if not math.isfinite(case_delay_seconds) or not 0 <= case_delay_seconds <= 60:
        raise ValueError("Evaluation case delay must be between 0 and 60 seconds.")
    if provider == "mock" and source_bundles is not None:
        raise ValueError("Mock skips live research and frozen source bundles.")
    results: list[dict[str, Any]] = []
    started_at = datetime.now(UTC).isoformat()
    mode = "mock_offline" if provider == "mock" else (
        "frozen_public_bundle" if source_bundles else "live_retrieval"
    )
    with evaluation_settings(provider, model):
        from app.core.config import settings

        provider_options = {
            "max_output_tokens": settings.groq_max_output_tokens if provider == "groq"
            else settings.ai_max_output_tokens,
            "json_mode": settings.groq_json_mode if provider == "groq" else "json_schema",
            "reasoning_effort": settings.groq_reasoning_effort if provider == "groq" else None,
            "operation_timeout_seconds": settings.ai_operation_timeout_seconds,
        }
        bundles = load_source_bundles(source_bundles, cases) if source_bundles else {}
        original_retrieve = generation_service.retrieve_sources
        original_get_provider = generation_service.get_provider
        # Never import app.db.session or instantiate an engine from settings.database_url.
        engine = create_engine("sqlite+pysqlite:///:memory:")
        try:
            Base.metadata.create_all(engine)
            with Session(engine) as db:
                user = User(email="evaluation@example.invalid", name="Offline evaluator")
                db.add(user)
                db.commit()
                service = generation_service.GenerationService(db)
                for case_index, case in enumerate(cases):
                    if case_index and case_delay_seconds:
                        time.sleep(case_delay_seconds)
                    captured: list[Any] = []
                    model_articles: list[Any] = []

                    observed = ObservedProvider(original_get_provider(), model_articles)

                    def capture_research(
                        query: str, case_id: str = case["id"], sink: list[Any] = captured,
                    ) -> Any:
                        result = bundles[case_id] if bundles else original_retrieve(query)
                        sink.append(result)
                        return result

                    result: dict[str, Any] = {
                        **case, "requested_provider": provider, "requested_model": model,
                        "research_mode": mode, "factual_accuracy": "not_evaluated",
                        "schema_valid": None,
                    }
                    seen_rows = {row.id for row in db.scalars(select(Generation))}
                    started = time.perf_counter()
                    try:
                        with (
                            patch.object(generation_service, "retrieve_sources", capture_research),
                            patch.object(generation_service, "get_provider", return_value=observed),
                        ):
                            outcome = service.generate_article(user, case["query"])
                        version = service.articles.latest_version(outcome.article.id)
                        assert version is not None
                        article = GeneratedArticle.model_validate_json(version.content)
                        result.update(article_metrics(article, outcome.seo))
                        result.update({
                            "status": "generated", "markdown": outcome.markdown,
                            "seo": outcome.seo.model_dump(),
                        })
                    except AppError as exc:
                        db.rollback()
                        safe_code = exc.code if re.fullmatch(r"[A-Z0-9_]{1,64}", exc.code) else (
                            "EVALUATION_FAILED"
                        )
                        result.update({
                            "status": "declined" if safe_code in DECLINED_CODES else "failed",
                            "error_code": safe_code,
                        })
                    except Exception:
                        db.rollback()
                        result.update({"status": "failed", "error_code": "EVALUATION_FAILED"})
                    result["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
                    research = captured[0] if captured else generation_service.ResearchResult(
                        ResearchSummary(), "Offline mock preview; no research.",
                    )
                    result.update(research_metrics(research, case["query"]))
                    result["pipeline_output_valid"] = result["status"] == "generated"
                    if model_articles:
                        # Even a declined unsupported citation had syntactically valid schema.
                        candidate = model_articles[0]
                        candidate.research = research.summary
                        result["schema_valid"] = True
                        result.update(citation_metrics(candidate))
                    result["research"] = {
                        "summary": research.summary.model_dump(), "context": research.context,
                    }
                    calls = [
                        row for row in db.scalars(select(Generation)) if row.id not in seen_rows
                    ]
                    if not model_articles and any(
                        row.error_code == "SchemaValidationError" for row in calls
                    ):
                        result["schema_valid"] = False
                    result["calls"] = [{
                        "kind": row.kind, "provider": row.provider, "model": row.model,
                        "status": row.status, "error_code": row.error_code,
                        "input_tokens": row.input_tokens, "output_tokens": row.output_tokens,
                        "latency_ms": row.latency_ms, "prompt_name": row.prompt_name,
                        "prompt_version": row.prompt_version,
                    } for row in calls]
                    results.append(result)
                    if on_case:
                        # Public identifiers and safe status only; no prompts or SDK bodies.
                        on_case({
                            "case_id": case["id"], "completed": len(results),
                            "total": len(cases), "status": result["status"],
                            "elapsed_ms": result["elapsed_ms"],
                        })
        finally:
            engine.dispose()
    status_counts = dict(Counter(result["status"] for result in results))
    schema_valid = sum(result["schema_valid"] is True for result in results)
    return {
        "version": 1, "started_at_utc": started_at,
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "provider": provider, "requested_model": model, "research_mode": mode,
        "provider_options": provider_options,
        "database": "isolated_in_memory_sqlite", "retry_count": 0, "fallback_enabled": False,
        "case_delay_seconds": case_delay_seconds,
        "accuracy": "not_evaluated_human_review_required",
        "schema_scores_do_not_certify_accuracy": True,
        "selected_cases": len(results), "status_counts": status_counts,
        "schema_valid_cases": schema_valid,
        "schema_19_of_20_threshold_met": len(results) == 20 and schema_valid >= 19,
        "results": results,
    }


def write_report(report: dict[str, Any]) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = REPOSITORY_ROOT / ".cache" / "evaluation" / f"{stamp}-{uuid4().hex[:8]}"
    output.mkdir(parents=True, exist_ok=False)
    (output / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    bundles = []
    for result in report["results"]:
        case_dir = output / result["id"]
        case_dir.mkdir()
        metadata = {
            key: value for key, value in result.items() if key not in {"markdown", "research"}
        }
        (case_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        (case_dir / "sources.json").write_text(
            json.dumps(result["research"], indent=2, ensure_ascii=False), encoding="utf-8",
        )
        if result.get("markdown"):
            (case_dir / "article.md").write_text(result["markdown"], encoding="utf-8")
        bundles.append({"id": result["id"], "query": result["query"], **result["research"]})
    (output / "source-bundles.json").write_text(
        json.dumps({"version": 1, "bundles": bundles}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Execute bounded provider requests.")
    parser.add_argument(
        "--collect-sources", action="store_true",
        help="With --live, collect public search evidence only; no model or DB calls.",
    )
    parser.add_argument("--provider", choices=("gemini", "groq", "mock"), default="gemini")
    parser.add_argument("--model", help="Exact provider model ID; required for execution.")
    parser.add_argument("--limit", type=int, default=MAX_CASES)
    parser.add_argument("--ids", default="", help="Comma-separated case IDs.")
    parser.add_argument(
        "--id", action="append", default=[], help="Select one ID; repeat as needed.",
    )
    parser.add_argument("--source-bundles", type=Path, help="Frozen public reference bundles.")
    parser.add_argument(
        "--case-delay-seconds", type=float, default=0,
        help="Pause 0-60 seconds between cases to respect a free account's limits.",
    )
    parser.add_argument(
        "--progress", action="store_true", help="Print sanitized per-case JSON progress.",
    )
    args = parser.parse_args(argv)
    try:
        ids = [item.strip() for item in args.ids.split(",") if item.strip()] + args.id
        cases = select_cases(load_cases(), ids, args.limit)
        if not math.isfinite(args.case_delay_seconds) or not 0 <= args.case_delay_seconds <= 60:
            parser.error("--case-delay-seconds must be between 0 and 60.")
        if args.collect_sources and args.source_bundles:
            parser.error("Source collection cannot also read frozen source bundles.")
        if args.live and not args.collect_sources and (
            not args.model or not re.fullmatch(r"[A-Za-z0-9./_-]{1,60}", args.model)
        ):
            parser.error("--live requires an exact model ID; never pass credentials here.")
        if args.live and args.model and re.search(r"(?:^|[-/])latest(?:$|[-/])", args.model):
            parser.error("Use a fixed model ID instead of a latest alias for comparisons.")
        if (
            args.live and not args.collect_sources
            and args.provider == "mock" and args.model != "mock-1"
        ):
            parser.error("The offline provider's exact model ID is mock-1.")
        if args.source_bundles and args.provider == "mock":
            parser.error("Mock skips research; source bundles require a real provider.")
    except (ValueError, OSError):
        parser.error("Evaluation inputs are invalid or unavailable; no provider was called.")
    if not args.live:
        print(json.dumps({
            "dry_run": True, "external_calls": 0, "database_access": False,
            "provider": args.provider, "model": args.model, "cases": cases,
            "research_mode": "live_public_search_only" if args.collect_sources else (
                "frozen_public_bundle" if args.source_bundles else "live_retrieval"
            ),
            "next_step": (
                "Add --live to collect public sources; no model or application DB will be used."
                if args.collect_sources else
                "Add --live and an exact --model to execute; accuracy needs human review."
            ),
        }, indent=2, ensure_ascii=False))
        return 0
    bootstrap_cli()
    try:
        progress = (lambda item: print(json.dumps(item), flush=True)) if args.progress else None
        if args.collect_sources:
            report = collect_sources(
                cases, case_delay_seconds=args.case_delay_seconds, on_case=progress,
            )
        else:
            report = run_evaluation(
                cases, provider=args.provider, model=args.model, source_bundles=args.source_bundles,
                case_delay_seconds=args.case_delay_seconds, on_case=progress,
            )
        output = write_report(report)
    except Exception:
        print("Evaluation could not start or save its report. No exception details are exposed.")
        return 1
    print(json.dumps({
        "report_directory": str(output), "selected_cases": report["selected_cases"],
        "status_counts": report["status_counts"],
        "schema_valid_cases": report.get("schema_valid_cases"),
        "accuracy": report["accuracy"],
    }, indent=2))
    return 0 if not report["status_counts"].get("failed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
