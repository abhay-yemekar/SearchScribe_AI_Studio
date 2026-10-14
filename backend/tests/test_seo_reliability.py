"""One-call generation, bounded repair, and server-owned SEO review snapshots."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from conftest import auth_headers, generate_article, register_user
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.base import TransientLLMError
from app.ai.mock import MockProvider
from app.ai.renderer import _fallback_seo
from app.ai.schemas import (
    ArticleSection,
    GeneratedArticle,
    GeneratedArticleWithSeo,
    SeoCandidate,
)
from app.ai.validation import validate_generated_seo
from app.repositories.article_repo import ArticleRepository


class CountingProvider(MockProvider):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def generate(self, prompt_name, prompt_version, variables, schema):
        self.calls.append(prompt_name)
        return super().generate(prompt_name, prompt_version, variables, schema)


def test_normal_generation_uses_one_call_and_reload_has_generated_status(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = CountingProvider()
    monkeypatch.setattr("app.services.generation_service.get_provider", lambda: provider)
    token = register_user(client)["access_token"]
    created = generate_article(client, token)
    assert provider.calls == ["article_generation"]
    assert created["seo"]["review_status"] == "generated"
    reloaded = client.get(
        f"/api/v1/articles/{created['id']}", headers=auth_headers(token)
    ).json()
    assert reloaded["seo"] == created["seo"]
    assert "seo" not in created["content"]


@pytest.mark.parametrize("bad_seo", [
    None, {"title": 25},
    {"title": "Article", "description": "An incomplete thought and", "keywords": ["topic"]},
    {"title": "Long title " * 9, "description": "A complete sentence.",
     "keywords": ["one", "two", "three", "four", "five"]},
])
def test_invalid_or_missing_seo_gets_one_repair_and_transient_failure_keeps_article(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, bad_seo: object,
) -> None:
    class RepairFails(CountingProvider):
        def generate(self, prompt_name, prompt_version, variables, schema):
            if prompt_name == "seo_generation":
                self.calls.append(prompt_name)
                raise TransientLLMError("test rate limit")
            response = super().generate(prompt_name, prompt_version, variables, schema)
            data = response.data.model_dump()
            data["introduction"] = "Planting herbs in containers needs careful watering."
            data["seo"] = bad_seo
            return replace(response, data=GeneratedArticleWithSeo.model_validate(data))

    provider = RepairFails()
    monkeypatch.setattr("app.services.generation_service.get_provider", lambda: provider)
    token = register_user(client)["access_token"]
    created = generate_article(client, token)
    assert provider.calls == ["article_generation", "seo_generation"]
    assert created["seo"]["review_status"] == "needs_review"
    assert created["seo"]["description"] == created["content"]["introduction"]
    assert "Read “" not in created["seo"]["description"]
    assert created["seo"]["keywords"] != ["a"]


def test_repaired_seo_can_be_generated_but_provider_cannot_set_review_state(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RepairSucceeds(CountingProvider):
        def generate(self, prompt_name, prompt_version, variables, schema):
            response = super().generate(prompt_name, prompt_version, variables, schema)
            if schema is GeneratedArticleWithSeo:
                return replace(response, data=response.data.model_copy(update={"seo": None}))
            assert schema is SeoCandidate
            return replace(response, data=SeoCandidate.model_validate({
                "title": "Container gardening and watering",
                "description": "Container gardening starts with careful watering and soil.",
                "keywords": ["container gardening", "watering", "soil", "herbs", "plants"],
                "review_status": "edited", "robots": "noindex, follow",
            }))

    provider = RepairSucceeds()
    monkeypatch.setattr("app.services.generation_service.get_provider", lambda: provider)
    token = register_user(client)["access_token"]
    created = generate_article(client, token)
    assert provider.calls == ["article_generation", "seo_generation"]
    assert created["seo"]["review_status"] == "generated"
    assert created["seo"]["robots"] == "index, follow"


def test_review_status_survives_edits_rewrite_restore_duplicate_and_spoof(
    client: TestClient,
) -> None:
    token = register_user(client)["access_token"]
    headers = auth_headers(token)
    detail = generate_article(client, token)
    path = f"/api/v1/articles/{detail['id']}"
    unchanged = client.put(path + "/content", json={
        "base_version": detail["current_version"], "content": detail["content"],
        "seo": {**detail["seo"], "review_status": "edited"},
    }, headers=headers).json()
    assert unchanged["seo"]["review_status"] == "generated"

    content = {**unchanged["content"], "introduction": "A different planting introduction."}
    edited = client.put(path + "/content", json={
        "base_version": unchanged["current_version"], "content": content,
        "seo": {**unchanged["seo"], "review_status": "generated"},
    }, headers=headers).json()
    assert edited["seo"]["review_status"] == "needs_review"
    spoofed = client.put(path + "/content", json={
        "base_version": edited["current_version"], "content": edited["content"],
        "seo": {**edited["seo"], "review_status": "generated"},
    }, headers=headers).json()
    assert spoofed["seo"]["review_status"] == "needs_review"
    manual = client.put(path + "/content", json={
        "base_version": spoofed["current_version"], "content": spoofed["content"],
        "seo": {**spoofed["seo"], "title": "An editor's planting guide"},
    }, headers=headers).json()
    assert manual["seo"]["review_status"] == "edited"
    duplicate = client.post(path + "/duplicate", headers=headers).json()
    assert duplicate["seo"]["review_status"] == "edited"
    rewritten = client.post(path + "/rewrite", json={"style": "professional"}, headers=headers)
    assert rewritten.status_code == 200
    assert rewritten.json()["seo"]["review_status"] == "needs_review"
    restored = client.post(path + "/versions/1/restore", headers=headers).json()
    assert restored["seo"]["review_status"] == "generated"
    assert client.get(path, headers=headers).json()["seo"] == restored["seo"]


def test_legacy_snapshot_defaults_unknown_without_changing_its_metadata(
    client: TestClient, db_session: Session,
) -> None:
    token = register_user(client)["access_token"]
    detail = generate_article(client, token)
    repo = ArticleRepository(db_session)
    latest = repo.latest_version(detail["id"])
    assert latest is not None
    latest.seo_snapshot = None
    db_session.commit()
    reloaded = client.get(
        f"/api/v1/articles/{detail['id']}", headers=auth_headers(token)
    ).json()
    assert reloaded["seo"]["review_status"] == "unknown"
    assert reloaded["seo"]["title"] == detail["seo"]["title"]


def test_failed_repair_fallback_contains_only_article_wording() -> None:
    content = GeneratedArticle(
        title="A factual title", introduction="An unfinished introduction",
        sections=[ArticleSection(heading="A heading", paragraphs=["An unfinished passage"])],
        conclusion="An unfinished conclusion",
    )
    fallback = _fallback_seo(content)
    assert fallback.description == content.title
    assert fallback.review_status == "needs_review"
    assert fallback.keywords == ["a factual title", "a heading"]


def test_strict_generated_constraints_do_not_clip_valid_manual_metadata() -> None:
    assert validate_generated_seo(SeoCandidate(
        title="Title", description="Complete.", keywords=["one"],
    )) is None
    assert validate_generated_seo(SeoCandidate(
        title="Title", description="Complete.",
        keywords=["one", "two", "three", "four", "five"],
    )) is not None


@pytest.mark.parametrize("needs_repair", [False, True])
def test_actual_gemini_adapter_renders_registered_combined_and_repair_prompts(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, needs_repair: bool,
) -> None:
    """Exercise production prompt lookup while the SDK transport stays offline.

    MockProvider does not render prompts, so it cannot catch a missing registry
    entry. Both normal combined generation and the repair use the real adapter.
    """
    from app.ai import gemini
    from app.ai.research import ResearchResult
    from app.ai.schemas import ResearchSummary

    calls: list[dict] = []

    async def generate_content(**kwargs):
        calls.append(kwargs)
        schema = kwargs["config"].response_schema
        if schema is GeneratedArticleWithSeo:
            candidate = MockProvider().generate(
                "article_generation", "v3", {"topic": "Container gardening"}, schema,
            ).data
            if needs_repair:
                candidate = candidate.model_copy(update={"seo": None})
        else:
            assert schema is SeoCandidate
            candidate = SeoCandidate(
                title="Container gardening with careful watering",
                description="Container gardening needs careful watering and suitable soil.",
                keywords=["container gardening", "watering", "soil", "herbs", "plants"],
            )
        return SimpleNamespace(text=candidate.model_dump_json(), usage_metadata=None)

    monkeypatch.setattr(gemini, "_generate_content", generate_content)
    monkeypatch.setattr(
        "app.services.generation_service.get_provider", lambda: gemini.GeminiProvider(),
    )
    monkeypatch.setattr("app.services.generation_service.retrieve_sources", lambda _: (
        ResearchResult(ResearchSummary(), "Offline unresearched test.")
    ))
    token = register_user(client)["access_token"]
    detail = generate_article(client, token, "Container gardening")
    assert detail["seo"]["review_status"] == "generated"
    assert len(calls) == (2 if needs_repair else 1)
    assert "SEO metadata (the seo object" in calls[0]["prompt"]
    if needs_repair:
        assert "Generate fresh metadata" in calls[1]["prompt"]
        assert "Container gardening" in calls[1]["prompt"]
