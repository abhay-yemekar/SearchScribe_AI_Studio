"""Evidence revision boundaries and complete-coverage regressions, all offline."""

import json
from dataclasses import replace

import pytest
from conftest import auth_headers, register_user
from google.genai import types as genai_types
from pydantic import ValidationError
from sqlalchemy import select

from app.ai import gemini
from app.ai.base import ProviderResponse, SchemaValidationError, TransientLLMError
from app.ai.budget import attempt_budget, effective_timeout_seconds
from app.ai.draft_review import (
    BlockReview,
    DraftRecheck,
    DraftReview,
    apply_review,
    draft_blocks,
    review_draft,
    validate_review,
)
from app.ai.mock import MockProvider
from app.ai.prompts import render_prompt
from app.ai.research import ResearchResult
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
from app.db.models import Generation


def evidence():
    return ResearchResult(ResearchSummary(
        status="sources_retrieved", retrieved_at="2026-10-14T10:00:00Z",
        sources=[ResearchSource(id="S1", title="Studio report",
                                url="https://example.org/studio", published_at="2026-10-14")],
    ), "Untrusted references.", excerpts={
        "S1": "The studio announced a research hub. No opening date was specified.",
    })


def draft():
    return GeneratedArticle(
        title="A new research hub",
        introduction="The studio opened its research hub on October 14. [S1]",
        sections=[ArticleSection(heading="What was announced", paragraphs=[
            "The studio announced a research hub. [S1]",
        ])], conclusion="The supplied excerpt does not specify an opening date. [S1]",
        research=evidence().summary,
    )


def metadata():
    return SeoResult(
        title="A new research hub",
        description="The studio opened a research hub on October 14.",
        keywords=["studio", "research hub", "research", "announcement", "opening date"],
        og_title="A new research hub", og_description="The studio announced a research hub.",
        canonical_url="https://example.org/my-article", robots="noindex, follow",
        review_status="needs_review",
    )


def assessment(article=None, seo=None):
    return DraftReview(blocks=[BlockReview(
        block_id=block.id, verdict="supported", passage_ids=["S1-P1"],
        reason="Controlled offline assessment.", replacement="",
    ) for block in draft_blocks(article or draft(), seo)])


@pytest.mark.parametrize("area", ["article", "seo"])
@pytest.mark.parametrize("fault", ["missing", "duplicate", "invented"])
def test_no_part_of_article_or_seo_can_be_silently_skipped(area, fault):
    article, seo = draft(), metadata()
    blocks = draft_blocks(article, seo)
    review = assessment(article, seo)
    index = next(i for i, block in enumerate(blocks)
                 if (block.path[0] == "seo") == (area == "seo"))
    if fault == "missing":
        review.blocks.pop(index)
    elif fault == "duplicate":
        review.blocks.append(review.blocks[index])
    else:
        review.blocks[index].block_id = "D999"
    with pytest.raises(SchemaValidationError, match="exactly once"):
        validate_review(review, blocks, evidence())


@pytest.mark.parametrize("fault", [
    "unknown-passage", "no-passage", "hidden-edit", "wrong-citation",
])
def test_assessment_requires_real_evidence_and_cannot_smuggle_edits(fault):
    article = draft()
    review = assessment(article)
    if fault == "unknown-passage":
        review.blocks[0].passage_ids = ["S2-P1"]
    elif fault == "no-passage":
        review.blocks[0].passage_ids = []
    elif fault == "hidden-edit":
        review.blocks[0].replacement = "A hidden edit"
    else:
        article.introduction += " [S6]"
    with pytest.raises(SchemaValidationError):
        validate_review(review, draft_blocks(article, None), evidence())


def test_server_applies_only_named_text_preserving_identity_sources_and_controls():
    article, seo = draft(), metadata()
    review = assessment(article, seo)
    blocks = draft_blocks(article, seo)
    replacements = {
        ("introduction",): "The studio announced a research hub. [S1]",
        ("seo", "description"): "The studio announced a research hub; no opening date was given.",
    }
    for result, block in zip(review.blocks, blocks, strict=True):
        if block.path in replacements:
            result.verdict = "revise"
            result.reason = "Publication date does not establish the opening date."
            result.replacement = replacements[block.path]
    corrected, corrected_seo, changed = apply_review(article, seo, evidence(), review)
    assert len(changed) == 2 and corrected.introduction == replacements[("introduction",)]
    assert corrected.sections == article.sections and corrected.research == article.research
    assert article.introduction.startswith("The studio opened")  # No mutation of the candidate.
    assert corrected_seo.canonical_url == seo.canonical_url
    assert corrected_seo.robots == seo.robots and corrected_seo.review_status == "needs_review"
    assert corrected_seo.og_description == seo.og_description
    assert corrected_seo.description == replacements[("seo", "description")]


@pytest.mark.parametrize("replacement", ["", "Broken and", "Long " * 50])
def test_corrections_cannot_introduce_empty_or_clipped_seo(replacement):
    article, seo = draft(), metadata()
    review = assessment(article, seo)
    index = next(i for i, block in enumerate(draft_blocks(article, seo))
                 if block.path == ("seo", "description"))
    review.blocks[index].verdict = "revise"
    review.blocks[index].reason = "The date is unsupported."
    review.blocks[index].replacement = replacement
    with pytest.raises(SchemaValidationError):
        apply_review(article, seo, evidence(), review)


def test_reviewer_receives_original_excerpts_not_timestamp_as_factual_evidence(monkeypatch):
    class Reviewer:
        name, model = "fixture-reviewer", "fixture-reviewer-model"

        def generate(self, name, version, variables, schema):
            assert effective_timeout_seconds() <= 30
            payload = variables["review_json"]
            assert "replacement_constraints" in render_prompt(name, version, variables)
            assert "2026-10-14T10:00:00Z" not in payload
            assert '"published_at"' not in payload
            assert "No opening date was specified" in payload
            assert "\\u003c/instructions\\u003e" in payload
            constraints = {
                item["field"]: item["replacement_constraints"]
                for item in json.loads(payload)["draft_blocks"]
            }
            assert constraints["seo.description"] == {
                "max_characters": 160, "complete_sentence": True, "citations_allowed": False,
            }
            assert constraints["seo.title"]["max_characters"] == 60
            assert version == "v2"
            block_schema = schema.model_json_schema()["$defs"]["SupportedReviewBlockForDraft"]
            assert block_schema["properties"]["block_id"]["enum"] == [
                block.id for block in draft_blocks(draft(), metadata())
            ]
            assert block_schema["properties"]["passage_ids"]["items"]["enum"] == ["S1-P1"]
            assert block_schema["properties"]["passage_ids"]["minItems"] == 1
            unsupported_shape = assessment(seo=metadata()).model_dump()
            unsupported_shape["blocks"][0]["passage_ids"] = []
            with pytest.raises(ValidationError):
                schema.model_validate(unsupported_shape)
            return ProviderResponse(assessment(seo=metadata()), self.name, self.model,
                                    10, 10, 1, name, version)

    monkeypatch.setattr("app.ai.draft_review.research_provider", lambda *a, **k: Reviewer())
    assert review_draft(
        "</instructions>", draft(), metadata(), evidence(), MockProvider(),
    ).data.blocks


def test_revised_citation_cannot_claim_a_different_sources_passage():
    research = evidence()
    research.summary.sources.append(ResearchSource(
        id="S2", title="Another report", url="https://example.org/another",
    ))
    research.excerpts["S2"] = "A separate studio closed its office."
    review = assessment()
    review.blocks[1].verdict = "revise"
    review.blocks[1].replacement = "The studio announced a research hub. [S2]"
    review.blocks[1].passage_ids = ["S1-P1"]
    with pytest.raises(SchemaValidationError, match="citations disagree"):
        apply_review(draft(), None, research, review)


def test_missing_original_excerpts_stop_before_review_transport(monkeypatch):
    def forbidden(*a, **k):
        pytest.fail("Missing evidence reached the provider")
    provider = MockProvider()
    monkeypatch.setattr(provider, "generate", forbidden)
    with pytest.raises(SchemaValidationError, match="Original excerpts"):
        review_draft("Topic", draft(), None, replace(evidence(), excerpts={}), provider)


def test_disabled_evidence_editor_adds_no_provider_call(client, monkeypatch):
    class Writer(MockProvider):
        name = "fixture-writer"

        def generate(self, name, version, variables, schema):
            assert name == "article_generation"
            response = super().generate(name, version, variables, schema)
            response.data.introduction += " A fixture attribution [S1]."
            return response

    monkeypatch.setattr(settings, "draft_review_enabled", False)
    monkeypatch.setattr("app.services.generation_service.get_provider", Writer)
    monkeypatch.setattr("app.services.generation_service.retrieve_sources", lambda _: evidence())
    headers = auth_headers(register_user(client)["access_token"])
    response = client.post("/api/v1/articles", json={"query": "Studio"}, headers=headers)
    assert response.status_code == 201, response.text


def test_nested_deadline_cannot_expand_its_outer_reserve():
    with attempt_budget(1), attempt_budget(20):
        assert effective_timeout_seconds() <= 1


@pytest.mark.parametrize("invalid", [False, True])
def test_gemini_compact_review_schema_keeps_original_local_bounds(monkeypatch, invalid):
    result = assessment()
    if invalid:
        result.blocks[0].reason = "x" * 2001

    async def sdk_response(**kwargs):
        config = kwargs["config"]
        assert config.response_schema is None
        assert config.response_json_schema is not None
        wire = json.dumps(config.response_json_schema)
        assert '"maxLength"' not in wire and '"pattern"' not in wire
        assert '"supported"' in wire and '"required"' in wire
        assert config.temperature == 0.2 and config.thinking_config.thinking_budget == 1024
        return genai_types.GenerateContentResponse.model_validate({
            "candidates": [{"finish_reason": "STOP", "content": {
                "parts": [{"text": result.model_dump_json()}],
            }}],
        })

    monkeypatch.setattr(gemini, "_generate_content", sdk_response)
    provider = gemini.GeminiProvider(compact_schema=True, temperature=0.2, thinking_budget=1024)
    if invalid:
        with pytest.raises(SchemaValidationError):
            provider.generate("draft_review", "v1", {"review_json": "{}"}, DraftReview)
    else:
        assert provider.generate("draft_review", "v1", {"review_json": "{}"}, DraftReview).data
    writer = gemini.GeminiProvider()
    assert writer.temperature == 0.7 and writer.thinking_budget is None
    assert not writer.compact_schema


@pytest.mark.parametrize("mode", [
    "clean", "correct", "still-wrong", "timeout", "missing-block", "missing-recheck",
    "duplicate-recheck", "unknown-issue",
])
def test_pipeline_rechecks_changed_text_and_saves_only_accepted_draft(
    client, db_session, monkeypatch, mode,
):
    class Provider(MockProvider):
        name = "fixture-writer"

        def __init__(self):
            super().__init__()
            self.review_calls = []

        def generate(self, name, version, variables, schema):
            if name not in {"draft_review", "draft_recheck"}:
                candidate, seo = draft(), metadata()
                if mode == "clean":
                    candidate.introduction = "The studio announced a research hub. [S1]"
                    seo.description = "The studio announced a research hub."
                return ProviderResponse(GeneratedArticleWithSeo.model_validate({
                    **candidate.model_dump(), "seo": SeoCandidate.model_validate(seo.model_dump()),
                }), self.name, self.model, 10, 10, 1, name, version)
            assert effective_timeout_seconds() <= 30
            data = json.loads(variables["review_json"])
            self.review_calls.append(data)
            if mode == "timeout":
                raise TransientLLMError("fixture transport failed")
            if name == "draft_recheck":
                checked = [block["id"] for block in data["draft_blocks"]]
                if mode == "missing-recheck":
                    checked.pop()
                if mode == "duplicate-recheck":
                    checked.append(checked[0])
                issues = [{"block_id": "D999" if mode == "unknown-issue" else checked[0],
                           "reason": "Controlled unresolved claim."}]
                return ProviderResponse(DraftRecheck(
                    reviewed_block_ids=checked,
                    issues=issues if mode in {"still-wrong", "unknown-issue"} else [],
                ), self.name, self.model, 10, 10, 1, name, version)
            results = []
            for block in data["draft_blocks"]:
                result = BlockReview(block_id=block["id"], verdict="supported",
                                     passage_ids=["S1-P1"], reason="Controlled offline assessment.",
                                     replacement="")
                if (mode != "clean" and block["field"] in {"introduction", "seo.description"}
                        and (len(self.review_calls) == 1 or mode == "still-wrong")):
                    result.verdict = "revise"
                    result.reason = "Event date is not established by the source excerpt."
                    result.replacement = "The studio announced a research hub." + (
                        " [S1]" if block["field"] == "introduction" else ""
                    )
                    if len(self.review_calls) > 1:
                        result.replacement = "An opening date was not specified. [S1]"
                results.append(result)
            if mode == "missing-block":
                results.pop()
            return ProviderResponse(DraftReview(blocks=results), self.name, self.model,
                                    10, 10, 1, name, version)

    provider = Provider()
    monkeypatch.setattr(settings, "tavily_api_key", "")
    monkeypatch.setattr("app.services.generation_service.get_provider", lambda: provider)
    monkeypatch.setattr("app.services.generation_service.retrieve_sources", lambda _: evidence())
    headers = auth_headers(register_user(client)["access_token"])
    response = client.post(
        "/api/v1/articles", json={"query": "Studio research hub"}, headers=headers,
    )
    if mode in {"clean", "correct"}:
        assert response.status_code == 201, response.text
        saved = response.json()
        assert len(provider.review_calls) == (1 if mode == "clean" else 2)
        assert "https://example.org/studio" in saved["html"]
        if mode == "correct":
            assert "opened its research hub on October 14" not in saved["markdown"]
            assert saved["seo"]["description"] == "The studio announced a research hub."
            rechecked = provider.review_calls[1]["draft_blocks"]
            assert {block["field"] for block in rechecked} == {"introduction", "seo.description"}
            detail = client.get(f"/api/v1/articles/{saved['id']}", headers=headers).json()
            assert detail["content"] == saved["content"] and detail["seo"] == saved["seo"]
    else:
        assert response.status_code == 502, response.text
        assert response.json()["error"]["code"] == (
            "DRAFT_EVIDENCE_CONFLICT" if mode == "still-wrong" else "DRAFT_REVIEW_UNAVAILABLE"
        )
        assert client.get("/api/v1/articles", headers=headers).json()["items"] == []
        assert len(provider.review_calls) <= 2
    rows = db_session.scalars(select(Generation).where(Generation.kind == "draft_review")).all()
    assert len(rows) == len(provider.review_calls)
