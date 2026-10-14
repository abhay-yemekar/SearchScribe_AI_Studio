"""Immutable passage selection, source-scope enforcement and review failures."""

from dataclasses import replace

import pytest
from conftest import auth_headers, register_user

from app.ai.base import ProviderResponse, SchemaValidationError
from app.ai.budget import effective_timeout_seconds
from app.ai.evidence_review import EvidenceReview, select_evidence
from app.ai.mock import MockProvider
from app.ai.research import ResearchResult
from app.ai.research_plan import ResearchPlan
from app.ai.schemas import ResearchSource, ResearchSummary
from app.core.config import settings

PRIMARY = "The service applies separate request and token limits to each listed model."
SECONDARY = "A secondary roundup claims that one fixed allowance applies to every model."


def references():
    return ResearchResult(ResearchSummary(
        status="sources_retrieved", retrieved_at="2026-10-14T00:00:00Z",
        sources=[
            ResearchSource(id="S1", title="Secondary roundup", url="https://roundup.example.com/limits"),
            ResearchSource(id="S2", title="Publisher limits", url="https://publisher.example.com/limits"),
        ],
    ), "Untrusted search excerpts.\nRAW SECONDARY CLAIM TO REMOVE", excerpts={
        "S1": SECONDARY, "S2": PRIMARY,
    })


def assessment():
    return EvidenceReview(
        selections=[
            {"source_id": "S1", "role": "secondary", "passage_ids": ["S1-P1"]},
            {"source_id": "S2", "role": "primary", "passage_ids": ["S2-P1"]},
        ],
        conflicts=[{"source_ids": ["S1", "S2"],
                    "description": "Universal versus per-model limits."}],
        limitations=["Exact account allowances are not in the excerpts."],
    )


def test_official_only_excludes_secondary_text_urls_and_unusable_conflicts():
    found = select_evidence(references(), assessment(), primary_only=True)
    assert [source.id for source in found.summary.sources] == ["S2"]
    assert PRIMARY in found.context
    assert SECONDARY not in found.context and "roundup.example.com" not in found.context
    assert "RAW SECONDARY" not in found.context
    assert '"source_ids": ["S1", "S2"]' not in found.context
    assert found.excerpts == {"S2": PRIMARY}


def test_conflicting_quotes_remain_attributed_when_secondary_coverage_is_allowed():
    found = select_evidence(references(), assessment(), primary_only=False)
    assert PRIMARY in found.context and SECONDARY in found.context
    assert "Universal versus per-model limits" in found.context
    assert "not fact-checking" in found.context
    assert "Exact account allowances" in found.context


def test_a_reported_conflict_cannot_silently_drop_the_other_source():
    review = assessment()
    review.selections = [review.selections[1]]
    found = select_evidence(references(), review, primary_only=False)
    assert {source.id for source in found.summary.sources} == {"S1", "S2"}
    assert SECONDARY in found.context and "Universal versus per-model limits" in found.context


@pytest.mark.parametrize("quote", [
    "S2-P99", "S1-P1", "invented source text",
])
def test_only_passages_belonging_to_the_retrieved_source_can_reach_the_writer(quote):
    review = assessment()
    review.selections[1].passage_ids = [quote]
    with pytest.raises(SchemaValidationError):
        select_evidence(references(), review, primary_only=False)


@pytest.mark.parametrize("invalid", ["unknown-source", "unknown-conflict"])
def test_review_source_ids_must_match_retrieved_unique_ids(invalid):
    review = assessment()
    if invalid == "unknown-source":
        review.selections[1].source_id = "S6"
    else:
        review.conflicts[0].source_ids = ["S2", "S6"]
    with pytest.raises(SchemaValidationError):
        select_evidence(references(), review, primary_only=False)


def test_duplicate_rows_merge_original_passages_without_duplicating_sources():
    review = assessment()
    review.selections.append(review.selections[1].model_copy(deep=True))
    found = select_evidence(references(), review, primary_only=True)
    assert [source.id for source in found.summary.sources] == ["S2"]
    assert found.excerpts["S2"] == PRIMARY


def test_conflicting_duplicate_role_claims_are_excluded_from_official_only_context():
    review = assessment()
    duplicate = review.selections[1].model_copy(deep=True)
    duplicate.role = "secondary"
    review.selections.append(duplicate)
    assert select_evidence(references(), review, primary_only=True).failure == "no_evidence"


def test_no_primary_evidence_is_a_coverage_decline_not_an_official_answer():
    review = assessment()
    for selection in review.selections:
        selection.role = "secondary"
    found = select_evidence(references(), review, primary_only=True)
    assert found.failure == "no_evidence" and found.summary.sources == []
    assert "first-party evidence" in found.failure_message


@pytest.mark.parametrize("malformed", [False, True])
def test_pipeline_filters_evidence_or_stops_before_creating_an_article(
    client, monkeypatch, malformed,
):
    class SourceProvider(MockProvider):
        name = "fixture-gemini"
        def __init__(self):
            super().__init__()
            self.calls = []

        def generate(self, prompt_name, prompt_version, variables, schema):
            self.calls.append((prompt_name, variables))
            if schema is ResearchPlan or issubclass(schema, EvidenceReview):
                assert effective_timeout_seconds() <= (15 if schema is ResearchPlan else 20)
                data = ResearchPlan(
                    mode="reference", requires_current_sources=True, primary_sources_only=True,
                    supplemental_query="Original documentation", clarification_question="",
                ) if schema is ResearchPlan else assessment()
                if malformed and isinstance(data, EvidenceReview):
                    data.selections[1].passage_ids = [
                        "An invented unsupported claim from a model response.",
                    ]
                return ProviderResponse(
                    data=data, provider=self.name, model=self.model,
                    prompt_name=prompt_name, prompt_version=prompt_version,
                    input_tokens=100, output_tokens=100, latency_ms=1,
                )
            response = super().generate(prompt_name, prompt_version, variables, schema)
            return replace(response, data=response.data.model_copy(update={
                "introduction": "A fixture draft attributes the actual retained evidence [S2].",
            }))

    provider = SourceProvider()
    monkeypatch.setattr(settings, "tavily_api_key", "fixture-key")
    monkeypatch.setattr("app.services.generation_service.get_provider", lambda: provider)
    monkeypatch.setattr("app.services.generation_service.retrieve_sources",
                        lambda *a, **kw: references())
    token = register_user(client)["access_token"]
    headers = auth_headers(token)
    response = client.post("/api/v1/articles", json={"query": "Current official service quotas"},
                           headers=headers)
    if malformed:
        assert response.status_code == 502
        assert response.json()["error"]["code"] == "EVIDENCE_REVIEW_UNAVAILABLE"
        assert client.get("/api/v1/articles", headers=headers).json()["items"] == []
    else:
        assert response.status_code == 201, response.text
        assert [s["id"] for s in response.json()["content"]["research"]["sources"]] == ["S2"]
        assert SECONDARY not in provider.calls[-1][1]["research_context"]
        assert "roundup.example.com" not in response.json()["html"]
