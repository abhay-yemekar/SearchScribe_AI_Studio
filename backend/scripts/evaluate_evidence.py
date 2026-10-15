"""Opt-in evidence-editor regression test on fictional, labelled source excerpts.

Run from backend/: python scripts/evaluate_evidence.py --provider groq --model MODEL
Add --live for bounded requests. No search, app database, email, retry or fallback.
Passing these cases does not qualify a writer or certify factual accuracy.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import uuid4

if __package__:
    from .evaluate_generation import (
        BACKEND_ROOT,
        REPOSITORY_ROOT,
        bootstrap_cli,
        evaluation_settings,
    )
else:
    from evaluate_generation import (
        BACKEND_ROOT,
        REPOSITORY_ROOT,
        bootstrap_cli,
        evaluation_settings,
    )

DEFAULT_CASES = BACKEND_ROOT / "evaluation" / "evidence_cases.json"


def load_cases(path: Path = DEFAULT_CASES) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("Evidence cases require version 1.")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= 20:
        raise ValueError("Choose 1 through 20 evidence cases.")
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict) or any(
            not isinstance(case.get(key), str) or not case[key].strip()
            for key in ("id", "passage", "claim", "expected")
        ):
            raise ValueError("Each case requires an ID, passage, claim and expected verdict.")
        if (not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", case["id"])
                or case["id"] in seen or len(case["passage"]) > 4000
                or len(case["claim"]) > 1000
                or case["expected"] not in {"supported", "editorial", "revise"}):
            raise ValueError("Invalid or duplicate evidence case.")
        seen.add(case["id"])
    return cases


def run_evaluation(
    cases: list[dict[str, str]], *, provider: str, model: str,
    case_delay_seconds: float = 0,
) -> dict[str, Any]:
    from app.ai.base import LLMError
    from app.ai.draft_review import (
        apply_review,
        draft_blocks,
        recheck_draft,
        review_draft,
        validate_review,
    )
    from app.ai.factory import _build_provider
    from app.ai.research import ResearchResult
    from app.ai.schemas import ArticleSection, GeneratedArticle, ResearchSource, ResearchSummary
    from app.core.config import settings

    if not cases or len(cases) > 20 or not math.isfinite(case_delay_seconds):
        raise ValueError("Invalid evaluation bounds.")
    if not 0 <= case_delay_seconds <= 60:
        raise ValueError("Case delay must be between 0 and 60 seconds.")
    results: list[dict[str, Any]] = []
    with evaluation_settings(provider, model), patch.multiple(
        settings, draft_reviewer_provider=provider, draft_reviewer_model=model,
    ):
        selected = _build_provider(provider, model)
        for index, case in enumerate(cases):
            if index and case_delay_seconds:
                time.sleep(case_delay_seconds)
            article = GeneratedArticle(
                title="Source notes", introduction=case["claim"],
                sections=[ArticleSection(heading="Evidence", paragraphs=[
                    "These notes compare a draft with the supplied excerpt.",
                ])], conclusion="Review source notes before publishing.",
            )
            research = ResearchResult(ResearchSummary(
                status="sources_retrieved", retrieved_at="2026-10-14T10:00:00Z",
                sources=[ResearchSource(id="S1", title="Fictional source excerpt",
                                        url="https://example.org/evidence",
                                        published_at="2026-10-14")],
            ), "Fictional reference data.", excerpts={"S1": case["passage"]})
            result: dict[str, Any] = {"id": case["id"], "expected": case["expected"],
                                      "claim": case["claim"], "passage": case["passage"]}
            tick = time.perf_counter()
            stage = "review_transport"
            try:
                response = review_draft(
                    "Review the source notes.", article, None, research, selected,
                )
                stage = "review_contract"
                validate_review(response.data, draft_blocks(article, None), research)
                target = next(item for item in response.data.blocks if item.block_id == "D2")
                result.update({"actual": target.verdict,
                               "label_match": target.verdict == case["expected"],
                               "review": response.data.model_dump(),
                               "review_model": response.model,
                               "review_latency_ms": response.latency_ms,
                               "input_tokens": response.input_tokens,
                               "output_tokens": response.output_tokens})
                stage = "apply_correction"
                corrected, _, changed = apply_review(article, None, research, response.data)
                result["corrected_claim"] = corrected.introduction
                if changed:
                    stage = "correction_recheck"
                    confirmation = recheck_draft(
                        "Review the source notes.", corrected, None, research, selected,
                        only_ids=changed,
                    )
                    result.update({"recheck": confirmation.data.model_dump(),
                                   "recheck_model": confirmation.model,
                                   "recheck_latency_ms": confirmation.latency_ms})
                    result["status"] = (
                        "recheck_rejected" if confirmation.data.issues else "reviewed"
                    )
                else:
                    result["status"] = "reviewed"
            except LLMError as exc:
                result.update({"status": "failed", "error_class": type(exc).__name__,
                               "failure_stage": stage})
            result["elapsed_ms"] = round((time.perf_counter() - tick) * 1000)
            results.append(result)
            print(json.dumps({key: result.get(key) for key in (
                "id", "status", "label_match", "elapsed_ms",
            )}), flush=True)
    completed = [item for item in results if item["status"] == "reviewed"]
    return {
        "version": 1, "provider": provider, "model": model, "selected_cases": len(cases),
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "scope": "Fictional excerpt-consistency labels; not independent factual accuracy.",
        "database_access": False, "search_calls": 0, "retry_count": 0, "fallback_enabled": False,
        "status_counts": dict(Counter(item["status"] for item in results)),
        "label_matches": sum(item.get("label_match", False) for item in results),
        "all_cases_passed": len(completed) == len(cases) and all(
            item["label_match"] for item in completed
        ),
        "correction_accuracy": "requires_human_review_of_saved_replacements",
        "writer_promotion": "not_authorized_by_this_benchmark", "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--provider", choices=("gemini", "groq"), default="groq")
    parser.add_argument("--model", help="Exact model ID, never an API key.")
    parser.add_argument("--ids", default="", help="Comma-separated case IDs.")
    parser.add_argument("--case-delay-seconds", type=float, default=0)
    args = parser.parse_args(argv)
    try:
        cases = load_cases()
        ids = {item.strip() for item in args.ids.split(",") if item.strip()}
        if ids - {case["id"] for case in cases}:
            raise ValueError("Unknown case.")
        cases = [case for case in cases if not ids or case["id"] in ids]
        if not math.isfinite(args.case_delay_seconds) or not 0 <= args.case_delay_seconds <= 60:
            raise ValueError("Invalid case delay.")
        if args.live and (
            not args.model or not re.fullmatch(r"[A-Za-z0-9./_-]{1,60}", args.model)
            or re.search(r"(?:^|[-/])latest(?:$|[-/])", args.model)
        ):
            raise ValueError("Use an exact model ID.")
    except (ValueError, OSError):
        parser.error("Invalid evidence evaluation inputs; no provider was called.")
    if not args.live:
        print(json.dumps({"dry_run": True, "external_calls": 0, "database_access": False,
                          "cases": cases}, ensure_ascii=False, indent=2))
        return 0
    bootstrap_cli()
    try:
        report = run_evaluation(cases, provider=args.provider, model=args.model,
                                case_delay_seconds=args.case_delay_seconds)
        output = REPOSITORY_ROOT / ".cache" / "evidence-evaluation" / (
            datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
        )
        output.mkdir(parents=True, exist_ok=False)
        (output / "report.json").write_text(json.dumps(
            report, indent=2, ensure_ascii=False,
        ), encoding="utf-8")
    except Exception:
        print("Evaluation could not complete. Provider exception details are not exposed.")
        return 1
    print(json.dumps({"report": str(output / "report.json"),
                      "label_matches": report["label_matches"],
                      "selected_cases": report["selected_cases"],
                      "all_cases_passed": report["all_cases_passed"]}))
    return 0 if report["all_cases_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
