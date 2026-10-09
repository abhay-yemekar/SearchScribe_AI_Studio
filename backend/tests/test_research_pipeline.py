"""Research provenance, freshness failures and SEO repair orchestration."""

from dataclasses import replace

import pytest
from conftest import auth_headers, register_user
from fastapi.testclient import TestClient

from app.ai.base import PermanentLLMError
from app.ai.mock import MockProvider
from app.ai.research import ResearchResult
from app.ai.schemas import GeneratedArticle, ResearchSource, ResearchSummary, SeoResult

SOURCE_URL = "https://platform.claude.com/docs/en/models/overview"


class _Provider(MockProvider):
    name = "fixture-gemini"

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def generate(self, prompt_name, prompt_version, variables, schema):
        self.calls.append((prompt_name, prompt_version, variables))
        return super().generate(prompt_name, prompt_version, variables, schema)


def _sources() -> ResearchResult:
    return ResearchResult(
        ResearchSummary(
            status="sources_retrieved",
            retrieved_at="2026-10-09T00:00:00+00:00",
            sources=[ResearchSource(id="S1", title="Official model docs", url=SOURCE_URL)],
        ),
        "Source S1: current model documentation from the primary publisher.",
    )


def _install(
    monkeypatch: pytest.MonkeyPatch, provider: _Provider, research: ResearchResult
) -> None:
    monkeypatch.setattr("app.services.generation_service.get_provider", lambda: provider)
    monkeypatch.setattr(
        "app.services.generation_service.retrieve_primary_sources", lambda _: research
    )


def test_latest_query_without_sources_fails_before_provider_or_persistence(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = register_user(client)["access_token"]
    provider = _Provider()
    _install(monkeypatch, provider, ResearchResult(ResearchSummary(), "Retrieval unavailable."))
    response = client.post(
        "/api/v1/articles",
        json={"query": "Claude latest model capabilities"},
        headers=auth_headers(token),
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "CURRENT_SOURCES_UNAVAILABLE"
    assert not provider.calls
    assert client.get("/api/v1/articles", headers=auth_headers(token)).json()["items"] == []


def test_sources_survive_edit_rewrite_restore_and_export(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = register_user(client)["access_token"]
    provider = _Provider()
    _install(monkeypatch, provider, _sources())
    response = client.post(
        "/api/v1/articles",
        json={"query": "Claude latest capabilities"},
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text
    article = response.json()
    assert provider.calls[0][1] == "v2"
    assert "Source S1" in provider.calls[0][2]["research_context"]
    assert article["content"]["research"] == _sources().summary.model_dump()
    assert SOURCE_URL in article["markdown"] and SOURCE_URL in article["html"]

    # The client cannot erase or replace server-owned provenance during an edit.
    content = article["content"]
    content["research"] = ResearchSummary().model_dump()
    content["introduction"] = "An edited introduction."
    saved = client.put(
        f"/api/v1/articles/{article['id']}/content",
        json={"base_version": 1, "content": content, "seo": article["seo"]},
        headers=auth_headers(token),
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["content"]["research"] == _sources().summary.model_dump()
    rewritten = client.post(
        f"/api/v1/articles/{article['id']}/rewrite",
        json={"style": "professional"},
        headers=auth_headers(token),
    )
    assert rewritten.status_code == 200, rewritten.text
    assert rewritten.json()["content"]["research"] == _sources().summary.model_dump()
    restored = client.post(
        f"/api/v1/articles/{article['id']}/versions/1/restore", headers=auth_headers(token)
    )
    assert restored.status_code == 200, restored.text
    detail = client.get(f"/api/v1/articles/{article['id']}", headers=auth_headers(token)).json()
    assert SOURCE_URL in detail["html"]
    assert detail["content"]["research"] == _sources().summary.model_dump()


def test_general_unresearched_draft_is_explicit(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = register_user(client)["access_token"]
    provider = _Provider()
    _install(monkeypatch, provider, ResearchResult(ResearchSummary(), "No source coverage."))
    response = client.post(
        "/api/v1/articles", json={"query": "Urban gardening basics"}, headers=auth_headers(token)
    )
    assert response.status_code == 201
    assert "Unresearched draft" in response.json()["html"]
    assert "Unresearched draft" in response.json()["markdown"]


@pytest.mark.parametrize("retrieved", [False, True])
def test_model_fabricated_metadata_is_ignored_during_generation_and_rewrite(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    retrieved: bool,
) -> None:
    token = register_user(client)["access_token"]
    forged = ResearchSummary(
        status="sources_retrieved",
        retrieved_at="2099-01-01T00:00:00+00:00",
        sources=[ResearchSource(id="S6", title="Fabricated model source", url=SOURCE_URL)],
    )

    class ForgingProvider(_Provider):
        def generate(self, prompt_name, prompt_version, variables, schema):
            response = super().generate(prompt_name, prompt_version, variables, schema)
            if isinstance(response.data, GeneratedArticle):
                if retrieved:
                    response.data.introduction += " A supported model claim [S1]."
                response = replace(
                    response, data=response.data.model_copy(update={"research": forged})
                )
            return response

    actual = _sources() if retrieved else ResearchResult(ResearchSummary(), "No live sources.")
    _install(monkeypatch, ForgingProvider(), actual)
    created = client.post(
        "/api/v1/articles", json={"query": "Claude model capabilities"}, headers=auth_headers(token)
    )
    assert created.status_code == 201, created.text
    article_id = created.json()["id"]
    rewritten = client.post(
        f"/api/v1/articles/{article_id}/rewrite",
        json={"style": "professional"},
        headers=auth_headers(token),
    )
    assert rewritten.status_code == 200, rewritten.text
    for response in (created, rewritten):
        data = response.json()
        assert data["content"]["research"] == actual.summary.model_dump()
        assert "Fabricated model source" not in data["html"]
        assert "2099-01-01" not in data["markdown"]
        assert "[S6]" not in data["markdown"]
    detail = client.get(f"/api/v1/articles/{article_id}", headers=auth_headers(token)).json()
    assert detail["content"]["research"] == actual.summary.model_dump()
    assert detail["current_version"] == 2


@pytest.mark.parametrize("citation", ["[S6]", "[S1, S6]"])
def test_unknown_inline_citation_rejects_generation_before_article_persistence(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    citation: str,
) -> None:
    token = register_user(client)["access_token"]

    class UnknownCitationProvider(_Provider):
        def generate(self, prompt_name, prompt_version, variables, schema):
            response = super().generate(prompt_name, prompt_version, variables, schema)
            if isinstance(response.data, GeneratedArticle):
                response.data.introduction += f" An unsupported model claim {citation}."
            return response

    provider = UnknownCitationProvider()
    _install(monkeypatch, provider, _sources())
    response = client.post(
        "/api/v1/articles", json={"query": "Claude model capabilities"}, headers=auth_headers(token)
    )
    assert response.status_code == 502, response.text
    assert response.json()["error"]["code"] == "GENERATION_FAILED"
    assert [call[0] for call in provider.calls] == ["article_generation"]
    assert client.get("/api/v1/articles", headers=auth_headers(token)).json()["items"] == []


@pytest.mark.parametrize("citation", ["[S6]", "[S1, S6]"])
def test_unknown_inline_citation_rejects_rewrite_without_persisting_a_new_version(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    citation: str,
) -> None:
    token = register_user(client)["access_token"]

    class UnknownCitationProvider(_Provider):
        def generate(self, prompt_name, prompt_version, variables, schema):
            response = super().generate(prompt_name, prompt_version, variables, schema)
            if prompt_name == "rewrite" and isinstance(response.data, GeneratedArticle):
                response.data.introduction += f" An unsupported model claim {citation}."
            return response

    provider = UnknownCitationProvider()
    _install(monkeypatch, provider, _sources())
    created = client.post(
        "/api/v1/articles", json={"query": "Claude model capabilities"}, headers=auth_headers(token)
    )
    assert created.status_code == 201, created.text
    original = created.json()
    article_id = original["id"]
    response = client.post(
        f"/api/v1/articles/{article_id}/rewrite",
        json={"style": "professional"},
        headers=auth_headers(token),
    )
    assert response.status_code == 502, response.text
    assert response.json()["error"]["code"] == "REWRITE_FAILED"
    detail = client.get(f"/api/v1/articles/{article_id}", headers=auth_headers(token)).json()
    assert detail["current_version"] == 1
    assert detail["content"] == original["content"]
    versions = client.get(
        f"/api/v1/articles/{article_id}/versions", headers=auth_headers(token)
    ).json()["items"]
    assert [version["version"] for version in versions] == [1]


@pytest.mark.parametrize("repair_fails", [False, True])
def test_seo_repair_is_bounded_and_never_returns_clipped_description(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    repair_fails: bool,
) -> None:
    token = register_user(client)["access_token"]

    class RepairProvider(_Provider):
        seo_calls = 0

        def generate(self, prompt_name, prompt_version, variables, schema):
            response = super().generate(prompt_name, prompt_version, variables, schema)
            if schema is SeoResult:
                self.seo_calls += 1
                if self.seo_calls == 2 and repair_fails:
                    raise PermanentLLMError("Repair unavailable")
                description = (
                    "Explore capabilities and " * 10
                    if self.seo_calls == 1
                    else ("Explore the model's capabilities and practical uses.")
                )
                response = replace(
                    response,
                    data=SeoResult(
                        title="Model capabilities",
                        description=description,
                        keywords=["models"],
                        og_description=description,
                    ),
                )
            return response

    provider = RepairProvider()
    _install(monkeypatch, provider, _sources())
    response = client.post(
        "/api/v1/articles", json={"query": "Claude capabilities"}, headers=auth_headers(token)
    )
    assert response.status_code == 201, response.text
    description = response.json()["seo"]["description"]
    assert provider.seo_calls == 2
    assert len(description) <= 160 and description.endswith(".")
    assert not description.endswith("and.")
