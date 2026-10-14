"""Evaluation isolation and honest metrics, without paid or real provider requests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import offline_review_response

from app.ai.base import ProviderResponse, SchemaValidationError, TransientLLMError
from app.ai.schemas import (
    ArticleSection,
    GeneratedArticle,
    GeneratedArticleWithSeo,
    ResearchSource,
    ResearchSummary,
    SeoCandidate,
    SeoResult,
)
from app.core.config import settings
from app.services import generation_service
from scripts import evaluate_generation as evaluation


def article() -> GeneratedArticle:
    return GeneratedArticle(
        title="Balcony herb gardening", introduction="Small spaces support useful herb gardens.",
        sections=[ArticleSection(heading="Plan the space", paragraphs=["Choose enough light."])],
        conclusion="Start small and observe each plant.",
    )


def seo() -> SeoResult:
    return SeoResult(
        title="Balcony herb gardening",
        description="Learn how to choose light, pots, and herbs for a small balcony garden.",
        keywords=["balcony herbs", "garden light", "plant pots", "small gardens", "herb care"],
        review_status="generated",
    )


class EvaluatedProvider:
    name = "gemini"
    model = "evaluation-model"

    def __init__(self, *, failure: Exception | None = None, citation: str = "") -> None:
        self.failure = failure
        self.citation = citation
        self.calls = 0

    def generate(self, prompt_name, prompt_version, variables, schema):
        self.calls += 1
        if self.failure:
            raise self.failure
        if prompt_name == "draft_review":
            return offline_review_response(self, prompt_name, prompt_version, variables)
        generated = article()
        generated.introduction += self.citation
        payload = GeneratedArticleWithSeo.model_validate({
            **generated.model_dump(), "seo": SeoCandidate.model_validate(seo().model_dump()),
        })
        return ProviderResponse(
            data=schema.model_validate(payload.model_dump()), provider=self.name, model=self.model,
            input_tokens=20, output_tokens=50, latency_ms=1,
            prompt_name=prompt_name, prompt_version=prompt_version,
        )


def selected_cases() -> list[dict[str, str]]:
    return [{"id": "fixture-case", "query": "Describe herbs.", "category": "evergreen"}]


def bundle_file(tmp_path: Path, cases: list[dict[str, str]]) -> Path:
    path = tmp_path / "public-bundles.json"
    path.write_text(json.dumps({"version": 1, "bundles": [{
        "id": case["id"], "query": case["query"],
        "summary": {
            "status": "sources_retrieved", "retrieved_at": "2026-10-13T00:00:00Z",
            "sources": [{"id": "S1", "title": "Public gardening reference",
                         "url": "https://example.org/gardening", "published_at": "2026-10-01"}],
        },
        "context": 'Public source S1 reports that herbs need suitable pots and light.',
        "excerpts": {"S1": "Herbs need suitable pots and light."},
    } for case in cases]}), encoding="utf-8")
    return path


def test_dry_run_never_enters_pipeline_or_bootstrap(monkeypatch, capsys) -> None:
    def forbidden(*args, **kwargs):
        pytest.fail("Dry run entered an executing path")

    monkeypatch.setattr(evaluation, "run_evaluation", forbidden)
    monkeypatch.setattr(evaluation, "collect_sources", forbidden)
    monkeypatch.setattr(evaluation, "bootstrap_cli", forbidden)
    assert evaluation.main(["--ids", "latest-elon-post", "--limit", "1"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["dry_run"] is True
    assert output["external_calls"] == 0
    assert output["database_access"] is False


def test_source_collection_is_opt_in_even_with_its_flag(monkeypatch, capsys) -> None:
    def forbidden(*args, **kwargs):
        pytest.fail("Source-only dry run executed a request")

    monkeypatch.setattr(evaluation, "collect_sources", forbidden)
    monkeypatch.setattr(evaluation, "bootstrap_cli", forbidden)
    assert evaluation.main(["--collect-sources", "--limit", "1"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["external_calls"] == 0
    assert output["research_mode"] == "live_public_search_only"


@pytest.mark.parametrize("args", [
    ["--live"], ["--limit", "21"], ["--id", "missing"],
    ["--live", "--model", "gemini-flash-latest"],
    ["--live", "--provider", "mock", "--model", "wrong"],
    ["--case-delay-seconds", "-1"], ["--case-delay-seconds", "61"],
    ["--case-delay-seconds", "nan"], ["--case-delay-seconds", "inf"],
    ["--collect-sources", "--source-bundles", "unused.json"],
])
def test_invalid_execution_inputs_fail_before_calls(monkeypatch, args) -> None:
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid input reached execution")

    monkeypatch.setattr(evaluation, "run_evaluation", forbidden)
    with pytest.raises(SystemExit) as exc:
        evaluation.main(args)
    assert exc.value.code == 2


def test_catalog_has_twenty_unique_public_cases() -> None:
    cases = evaluation.load_cases()
    assert len(cases) == 20
    assert len({case["id"] for case in cases}) == 20
    assert len(evaluation.select_cases(cases, ["evergreen-gardening"], 2)) == 1


def test_bibliography_does_not_count_as_body_evidence() -> None:
    generated = article()
    generated.research = ResearchSummary(status="sources_retrieved", sources=[ResearchSource(
        id="S1", title="A public reference", url="https://example.org/garden",
    )])
    assert "[S1]" in generated.to_markdown()
    metrics = evaluation.article_metrics(generated, seo())
    assert metrics["body_citation_ids"] == []
    assert metrics["cited_source_count"] == 0
    generated.introduction += " [S1, S99]"
    metrics = evaluation.article_metrics(generated, seo())
    assert metrics["cited_source_count"] == 1
    assert metrics["unsupported_citation_ids"] == ["S99"]
    assert metrics["citation_support_accuracy"] == "not_evaluated_requires_human_review"


def test_live_pipeline_uses_only_memory_database_and_frozen_sources(monkeypatch, tmp_path) -> None:
    import sqlalchemy

    provider = EvaluatedProvider(citation=" [S1]")
    monkeypatch.setattr(generation_service, "get_provider", lambda: provider)

    def forbidden_search(query):
        pytest.fail("Frozen-source comparison performed live search")

    monkeypatch.setattr(generation_service, "retrieve_sources", forbidden_search)
    engines = []
    original_create = sqlalchemy.create_engine

    def isolated_create(url, *args, **kwargs):
        assert url == "sqlite+pysqlite:///:memory:"
        engines.append(url)
        return original_create(url, *args, **kwargs)

    monkeypatch.setattr(sqlalchemy, "create_engine", isolated_create)
    original_settings = (settings.database_url, settings.ai_provider, settings.ai_model)
    cases = selected_cases()
    report = evaluation.run_evaluation(
        cases, provider="gemini", model=provider.model, source_bundles=bundle_file(tmp_path, cases),
    )
    assert engines == ["sqlite+pysqlite:///:memory:"]
    assert (settings.database_url, settings.ai_provider, settings.ai_model) == original_settings
    assert provider.calls == 2
    assert report["status_counts"] == {"generated": 1}
    assert report["research_mode"] == "frozen_public_bundle"
    result = report["results"][0]
    assert result["seo_bounds_and_complete_ending"] is True
    assert result["source_count"] == 1
    assert result["body_citation_ids"] == ["S1"]
    assert result["calls"][0]["provider"] == provider.name
    assert result["factual_accuracy"] == "not_evaluated"
    assert report["schema_19_of_20_threshold_met"] is False
    assert report["provider_options"]["max_output_tokens"] == settings.ai_max_output_tokens
    assert report["provider_options"]["reasoning_effort"] is None


def test_current_topic_without_evidence_is_declined_before_model(monkeypatch) -> None:
    provider = EvaluatedProvider()
    monkeypatch.setattr(generation_service, "get_provider", lambda: provider)
    monkeypatch.setattr(settings, "tavily_api_key", "")
    report = evaluation.run_evaluation(
        [{"id": "latest-post", "query": "Elon Musk latest tweet", "category": "current"}],
        provider="gemini", model=provider.model,
    )
    assert provider.calls == 0
    assert report["status_counts"] == {"declined": 1}
    assert report["results"][0]["schema_valid"] is None
    assert report["results"][0]["error_code"] == "RESEARCH_NOT_CONFIGURED"


@pytest.mark.parametrize("failure", [
    TransientLLMError("private-key"), SchemaValidationError("key"),
])
def test_failure_is_not_retried_or_exposed(monkeypatch, failure) -> None:
    provider = EvaluatedProvider(failure=failure)
    monkeypatch.setattr(generation_service, "get_provider", lambda: provider)
    monkeypatch.setattr(settings, "tavily_api_key", "")
    report = evaluation.run_evaluation(selected_cases(), provider="gemini", model=provider.model)
    assert provider.calls == 1
    assert report["status_counts"] == {"failed": 1}
    assert str(failure) not in json.dumps(report)
    assert report["results"][0]["calls"][0]["error_code"] == type(failure).__name__


def test_bundle_query_mismatch_cannot_replace_evidence(tmp_path) -> None:
    cases = selected_cases()
    path = bundle_file(tmp_path, cases)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["bundles"][0]["query"] = "A different topic"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly match"):
        evaluation.load_source_bundles(path, cases)


def test_unsupported_citation_can_pass_schema_but_fail_pipeline(monkeypatch, tmp_path) -> None:
    provider = EvaluatedProvider(citation=" [S99]")
    monkeypatch.setattr(generation_service, "get_provider", lambda: provider)
    cases = selected_cases()
    report = evaluation.run_evaluation(
        cases, provider="gemini", model=provider.model, source_bundles=bundle_file(tmp_path, cases),
    )
    result = report["results"][0]
    assert result["status"] == "failed"
    assert result["schema_valid"] is True
    assert result["pipeline_output_valid"] is False
    assert result["unsupported_citation_ids"] == ["S99"]
    assert report["accuracy"] == "not_evaluated_human_review_required"


def test_report_has_drafts_metadata_and_reusable_exact_sources(monkeypatch, tmp_path) -> None:
    provider = EvaluatedProvider(citation=" [S1]")
    monkeypatch.setattr(generation_service, "get_provider", lambda: provider)
    monkeypatch.setattr(evaluation, "REPOSITORY_ROOT", tmp_path)
    cases = selected_cases()
    report = evaluation.run_evaluation(
        cases, provider="gemini", model=provider.model, source_bundles=bundle_file(tmp_path, cases),
    )
    output = evaluation.write_report(report)
    assert (output / "fixture-case" / "article.md").exists()
    metadata = json.loads((output / "fixture-case" / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["factual_accuracy"] == "not_evaluated"
    assert "research" not in metadata
    reused = evaluation.load_source_bundles(output / "source-bundles.json", cases)
    assert reused["fixture-case"].summary.sources[0].id == "S1"


def test_free_plan_pacing_and_progress_preserve_every_case(monkeypatch) -> None:
    provider = EvaluatedProvider()
    monkeypatch.setattr(generation_service, "get_provider", lambda: provider)
    monkeypatch.setattr(settings, "tavily_api_key", "")
    pauses: list[float] = []
    progress: list[dict] = []
    monkeypatch.setattr(evaluation.time, "sleep", pauses.append)
    cases = [*selected_cases(), {
        "id": "second-case", "query": "Explain editorial review.", "category": "evergreen",
    }]
    report = evaluation.run_evaluation(
        cases, provider="gemini", model=provider.model,
        case_delay_seconds=30, on_case=progress.append,
    )
    assert pauses == [30]  # No delay before the first case or after the last one.
    assert provider.calls == 2 and report["case_delay_seconds"] == 30
    assert [item["completed"] for item in progress] == [1, 2]
    assert all(set(item) == {"case_id", "completed", "total", "status", "elapsed_ms"}
               for item in progress)
    assert all(item["status"] == "generated" for item in progress)


def test_source_collection_freezes_exact_queries_without_model_or_database(
    monkeypatch, tmp_path,
) -> None:
    import sqlalchemy

    from app.ai import research
    from app.ai.research import ResearchResult

    def forbidden(*args, **kwargs):
        pytest.fail("Source collection accessed a model or database")

    monkeypatch.setattr(sqlalchemy, "create_engine", forbidden)
    monkeypatch.setattr(generation_service, "get_provider", forbidden)
    cases = selected_cases()
    existing = evaluation.load_source_bundles(bundle_file(tmp_path, cases), cases)["fixture-case"]
    queries: list[str] = []

    def retrieve(query):
        queries.append(query)
        return existing if len(queries) == 1 else ResearchResult(
            ResearchSummary(), "No usable public evidence.", "no_evidence",
        )

    monkeypatch.setattr(research, "retrieve_sources", retrieve)
    cases += [{"id": "missing-case", "query": "An uncertain release.", "category": "missing"}]
    progress: list[dict] = []
    report = evaluation.collect_sources(cases, on_case=progress.append)
    assert queries == [case["query"] for case in cases]
    assert report["database_access"] is False and report["model_calls"] == 0
    assert report["status_counts"] == {"sources_collected": 1, "no_evidence": 1}
    assert [item["status"] for item in progress] == ["sources_collected", "no_evidence"]
    monkeypatch.setattr(evaluation, "REPOSITORY_ROOT", tmp_path)
    output = evaluation.write_report(report)
    reused = evaluation.load_source_bundles(output / "source-bundles.json", cases)
    assert reused["fixture-case"].context == existing.context
    assert reused["missing-case"].summary.sources == []


def test_source_only_cli_does_not_require_a_model(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(evaluation, "bootstrap_cli", lambda: None)
    called = []

    def collect(cases, **kwargs):
        called.append(cases)
        return {"selected_cases": len(cases), "status_counts": {"no_evidence": len(cases)},
                "accuracy": "not_evaluated_human_review_required"}

    monkeypatch.setattr(evaluation, "collect_sources", collect)
    monkeypatch.setattr(evaluation, "write_report", lambda _: tmp_path)
    assert evaluation.main(["--live", "--collect-sources", "--limit", "1"]) == 0
    assert len(called) == 1 and len(called[0]) == 1
    assert json.loads(capsys.readouterr().out)["schema_valid_cases"] is None
