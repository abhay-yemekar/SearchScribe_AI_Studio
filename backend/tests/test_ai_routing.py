"""Offline provider routing, real adapter boundaries and request-budget regression tests."""

from __future__ import annotations

import asyncio
import time
from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest
from conftest import auth_headers, offline_review_response, register_user
from fastapi.testclient import TestClient
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import base, budget, gemini, routing
from app.ai.base import (
    DeadlineExceededLLMError,
    PermanentLLMError,
    SchemaValidationError,
    TransientLLMError,
)
from app.ai.mock import MockProvider
from app.ai.research import ResearchResult
from app.ai.schemas import (
    GeneratedArticleWithSeo,
    ResearchSource,
    ResearchSummary,
    SeoCandidate,
    SeoResult,
)
from app.core.config import Settings, settings
from app.db.models import Generation


class FixtureProvider(MockProvider):
    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name
        self.model = f"{name}-model"
        self.calls: list[str] = []
        self.variables: list[dict[str, str]] = []

    def generate(self, prompt_name, prompt_version, variables, schema):
        self.calls.append(prompt_name)
        self.variables.append(variables.copy())
        if prompt_name == "draft_review":
            return offline_review_response(self, prompt_name, prompt_version, variables)
        response = super().generate(prompt_name, prompt_version, variables, schema)
        if variables.get("research_status") == "sources_retrieved":
            response.data.introduction += " A supported fixture claim [S1]."
        return response


def install_routes(monkeypatch: pytest.MonkeyPatch):
    primary, fallback = FixtureProvider("primary"), FixtureProvider("fallback")
    monkeypatch.setattr(routing, "get_fallback_provider", lambda: fallback)
    monkeypatch.setattr(base.random, "uniform", lambda *_: 0)
    return primary, fallback


def test_primary_success_never_calls_configured_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    primary, fallback = install_routes(monkeypatch)
    result = routing.call_with_fallback(primary, lambda provider: provider.generate(
        "article_generation", "v3", {"topic": "Plants"}, GeneratedArticleWithSeo,
    ))
    assert result.provider == "primary"
    assert primary.calls == ["article_generation"]
    assert fallback.calls == []


@pytest.mark.parametrize("error", [PermanentLLMError, SchemaValidationError])
def test_auth_safety_bad_request_and_invalid_schema_never_fallback(
    monkeypatch: pytest.MonkeyPatch, error: type[Exception],
) -> None:
    primary, fallback = install_routes(monkeypatch)
    calls = []

    def fail(provider):
        calls.append(provider.name)
        raise error("sanitized failure")

    with pytest.raises(error):
        routing.call_with_fallback(primary, fail)
    assert calls == ["primary"]
    assert fallback.calls == []


def test_transient_primary_exhaustion_uses_exactly_one_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary, fallback = install_routes(monkeypatch)
    monkeypatch.setattr("app.ai.base.time.sleep", lambda _: None)
    primary.transient_failures_remaining = 99
    response = routing.call_with_fallback(primary, lambda provider: provider.generate(
        "article_generation", "v3", {"topic": "Plants"}, GeneratedArticleWithSeo,
    ))
    assert primary.calls == ["article_generation"] * 3
    assert fallback.calls == ["article_generation"]
    assert (response.provider, response.model) == ("fallback", "fallback-model")


def test_failed_fallback_is_not_retried_and_identifies_actual_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary, fallback = install_routes(monkeypatch)
    monkeypatch.setattr(settings, "ai_max_retries", 0)
    primary.transient_failures_remaining = fallback.transient_failures_remaining = 99
    with pytest.raises(TransientLLMError) as caught:
        routing.call_with_fallback(primary, lambda provider: provider.generate(
            "article_generation", "v3", {"topic": "Plants"}, GeneratedArticleWithSeo,
        ))
    assert len(primary.calls) == len(fallback.calls) == 1
    assert (caught.value.provider, caught.value.model) == ("fallback", "fallback-model")


def test_primary_budget_reserves_time_for_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    primary, _ = install_routes(monkeypatch)
    clock = [1000.0]
    monkeypatch.setattr(budget.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr("app.ai.base.time.sleep", lambda seconds: clock.__setitem__(
        0, clock[0] + seconds,
    ))
    observed: list[tuple[str, float]] = []

    def generate(provider):
        timeout = budget.effective_timeout_seconds()
        observed.append((provider.name, timeout))
        if provider.name == "primary":
            clock[0] += timeout
            raise TransientLLMError("timeout")
        return provider.name

    @budget.within_operation_budget
    def operation():
        return routing.call_with_fallback(primary, generate)

    assert operation() == "fallback"
    assert observed == [("primary", 60), ("primary", pytest.approx(19.6)), ("fallback", 20)]
    assert budget.remaining_operation_seconds() == settings.ai_operation_timeout_seconds


def test_exhausted_operation_never_starts_another_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    primary = FixtureProvider("primary")
    clock = [1000.0]
    monkeypatch.setattr(budget.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(settings, "ai_operation_timeout_seconds", 10)
    monkeypatch.setattr(routing, "get_fallback_provider", lambda: None)
    calls = []

    @budget.within_operation_budget
    def operation():
        def generate(provider):
            calls.append(provider.name)
            clock[0] += 10
            raise TransientLLMError("timeout")

        return routing.call_with_fallback(primary, generate)

    with pytest.raises(DeadlineExceededLLMError):
        operation()
    assert calls == ["primary"]


def test_mock_cannot_cross_to_a_live_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbid():
        raise AssertionError("Mock must not resolve live fallback")

    monkeypatch.setattr(routing, "get_fallback_provider", forbid)
    result = routing.call_with_fallback(MockProvider(), lambda provider: provider.name)
    assert result == "mock"


@pytest.mark.parametrize("overrides", [
    {"ai_fallback_provider": "groq"},
    {"ai_fallback_model": "configured-model"},
    {"ai_fallback_provider": "gemini", "ai_fallback_model": "gemini-2.5-flash"},
    {"ai_fallback_provider": "groq", "ai_fallback_model": "configured-model"},
    {"ai_provider": "mock", "ai_fallback_provider": "groq", "ai_fallback_model": "model"},
    {"ai_model": "model\nwith control"},
    {"ai_max_retries": 3},
])
def test_invalid_or_unsafe_routing_configuration_is_rejected(overrides: dict) -> None:
    values = {"app_env": "test", "ai_provider": "gemini", "ai_model": "gemini-2.5-flash",
              "_env_file": None, **overrides}
    with pytest.raises(ValidationError):
        Settings(**values)


def test_configured_model_id_is_not_limited_to_a_catalog() -> None:
    configured = Settings(
        _env_file=None, app_env="test", ai_provider="gemini", ai_model="future-provider/model",
        ai_fallback_provider="groq", ai_fallback_model="future-fallback/model", groq_api_key="test",
    )
    assert configured.ai_fallback_model == "future-fallback/model"
    assert "groq_api_key" not in repr(configured)


@pytest.mark.parametrize("failure", [
    httpx.ReadTimeout("private prompt data"), httpx.ConnectError("private token"),
    genai_errors.APIError(403, {"error": {"message": "private token"}}),
    genai_errors.APIError(429, {"error": {"message": "private prompt"}}),
])
def test_gemini_sanitizes_transport_and_api_errors(
    monkeypatch: pytest.MonkeyPatch, failure: Exception,
) -> None:
    async def fail(**_):
        raise failure

    monkeypatch.setattr(gemini, "_generate_content", fail)
    expected = PermanentLLMError if isinstance(failure, genai_errors.APIError) and (
        failure.code == 403
    ) else TransientLLMError
    with pytest.raises(expected) as caught:
        gemini.GeminiProvider().generate(
            "seo_generation", "v1", {"title": "Title", "introduction": "Intro"}, SeoResult,
        )
    assert "private" not in str(caught.value)
    assert caught.value.__suppress_context__


def test_gemini_schema_failure_does_not_expose_provider_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def invalid(**_):
        return SimpleNamespace(text='{"title":"private source excerpt"}', usage_metadata=None)

    monkeypatch.setattr(gemini, "_generate_content", invalid)
    with pytest.raises(SchemaValidationError) as caught:
        gemini.GeminiProvider().generate(
            "seo_generation", "v1", {"title": "Title", "introduction": "Intro"}, SeoResult,
        )
    assert "private source excerpt" not in str(caught.value)
    assert caught.value.__suppress_context__


@pytest.mark.parametrize("finish,block,expected", [
    ("STOP", "SAFETY", PermanentLLMError),
    ("STOP", "PROHIBITED_CONTENT", PermanentLLMError),
    ("SAFETY", None, PermanentLLMError),
    ("RECITATION", None, PermanentLLMError),
    ("BLOCKLIST", None, PermanentLLMError),
    ("PROHIBITED_CONTENT", None, PermanentLLMError),
    ("SPII", None, PermanentLLMError),
    ("MAX_TOKENS", None, SchemaValidationError),
    ("OTHER", None, SchemaValidationError),
    (None, None, SchemaValidationError),
])
def test_actual_sdk_refusals_and_truncation_reject_even_valid_json_without_fallback(
    monkeypatch: pytest.MonkeyPatch, finish: str | None, block: str | None,
    expected: type[Exception],
) -> None:
    payload = SeoResult(
        title="A complete title", description="A complete sentence.", keywords=["seo"],
    )
    sdk_response = genai_types.GenerateContentResponse.model_validate({
        "candidates": [{"finish_reason": finish, "content": {
            "parts": [{"text": payload.model_dump_json()}],
        }}],
        "prompt_feedback": {"block_reason": block} if block else None,
    })

    async def response(**_):
        return sdk_response

    monkeypatch.setattr(gemini, "_generate_content", response)
    fallback = FixtureProvider("fallback")
    monkeypatch.setattr(routing, "get_fallback_provider", lambda: fallback)
    with pytest.raises(expected):
        routing.call_with_fallback(gemini.GeminiProvider(), lambda provider: provider.generate(
            "seo_generation", "v1", {"title": "Title", "introduction": "Intro"}, SeoResult,
        ))
    assert fallback.calls == []


def test_actual_sdk_natural_completion_accepts_valid_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = SeoResult(
        title="A complete title", description="A complete sentence.", keywords=["seo"],
    )
    sdk_response = genai_types.GenerateContentResponse.model_validate({
        "candidates": [{"finish_reason": "STOP", "content": {
            "parts": [{"text": payload.model_dump_json()}],
        }}],
    })

    async def response(**_):
        return sdk_response

    monkeypatch.setattr(gemini, "_generate_content", response)
    actual = gemini.GeminiProvider().generate(
        "seo_generation", "v1", {"title": "Title", "introduction": "Intro"}, SeoResult,
    )
    assert actual.data == payload


def test_actual_gemini_async_transport_deadline_cancels_and_closes_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = {}

    class FakeAio:
        models: object

        def __init__(self):
            self.models = self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            observed["closed"] = True

        async def generate_content(self, **kwargs):
            observed["config"] = kwargs["config"]
            try:
                await asyncio.sleep(10)
            finally:
                observed["cancelled"] = True

    class FakeSdk:
        def __init__(self, **kwargs):
            observed["http_options"] = kwargs["http_options"]
            self.aio = FakeAio()

        def __enter__(self):
            return self

        def __exit__(self, *_):
            observed["sync_closed"] = True

    def fake_client(**kwargs):
        observed["http_options"] = kwargs["http_options"]
        return FakeSdk(**kwargs)

    monkeypatch.setattr(gemini.genai, "Client", fake_client)
    monkeypatch.setattr(settings, "ai_timeout_seconds", 0.01)
    started = time.perf_counter()
    with pytest.raises(TransientLLMError):
        gemini.GeminiProvider().generate(
            "seo_generation", "v1", {"title": "Title", "introduction": "Intro"}, SeoResult,
        )
    assert time.perf_counter() - started < 0.5
    assert observed["closed"] and observed["cancelled"] and observed["sync_closed"]
    assert observed["http_options"].retry_options.attempts == 1
    assert observed["http_options"].timeout == 10
    assert observed["config"].response_schema is SeoResult
    assert observed["config"].automatic_function_calling.disable is True


def test_pipeline_fallback_preserves_sources_and_repairs_seo_once_on_actual_provider(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary, _ = install_routes(monkeypatch)
    primary.transient_failures_remaining = 99
    monkeypatch.setattr(settings, "ai_max_retries", 0)

    class RepairFailingFallback(FixtureProvider):
        def generate(self, prompt_name, prompt_version, variables, schema):
            if schema is SeoCandidate:
                self.calls.append(prompt_name)
                raise TransientLLMError("repair unavailable")
            response = super().generate(prompt_name, prompt_version, variables, schema)
            return replace(response, data=response.data.model_copy(update={"seo": None}))

    fallback = RepairFailingFallback("fallback")
    monkeypatch.setattr(routing, "get_fallback_provider", lambda: fallback)
    monkeypatch.setattr("app.services.generation_service.get_provider", lambda: primary)
    research = ResearchResult(ResearchSummary(
        status="sources_retrieved", sources=[ResearchSource(
            id="S1", title="Fixture research", url="https://example.com/research",
        )],
    ), "Source S1: untrusted reference evidence.", excerpts={"S1": "Untrusted reference evidence."})
    monkeypatch.setattr("app.services.generation_service.retrieve_sources", lambda _: research)
    token = register_user(client)["access_token"]
    response = client.post(
        "/api/v1/articles", json={"query": "Growing plants"}, headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text
    assert response.json()["content"]["research"] == research.summary.model_dump()
    assert response.json()["seo"]["review_status"] == "needs_review"
    assert fallback.calls == ["article_generation", "seo_generation", "draft_review"]
    assert primary.variables[0] == fallback.variables[0]
    assert "https://example.com/research" in response.json()["html"]
    rows = db_session.scalars(select(Generation).order_by(Generation.id)).all()
    assert [(row.kind, row.provider, row.model, row.status) for row in rows] == [
        ("article", "fallback", "fallback-model", "success"),
        ("seo", "fallback", "fallback-model", "failed"),
        ("draft_review", "fallback", "fallback-model", "success"),
    ]


def test_fallback_rewrite_retains_saved_evidence_and_actual_provider_metadata(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary, fallback = install_routes(monkeypatch)
    primary.transient_failures_remaining = 99
    monkeypatch.setattr(settings, "ai_max_retries", 0)
    monkeypatch.setattr("app.services.generation_service.get_provider", lambda: primary)
    research = ResearchResult(ResearchSummary(
        status="sources_retrieved", sources=[ResearchSource(
            id="S1", title="Fixture research", url="https://example.com/research",
        )],
    ), "Source S1: untrusted reference evidence.", excerpts={"S1": "Untrusted reference evidence."})
    monkeypatch.setattr("app.services.generation_service.retrieve_sources", lambda _: research)
    token = register_user(client)["access_token"]
    created = client.post(
        "/api/v1/articles", json={"query": "Growing plants"}, headers=auth_headers(token),
    )
    assert created.status_code == 201
    rewritten = client.post(
        f"/api/v1/articles/{created.json()['id']}/rewrite",
        json={"style": "professional"}, headers=auth_headers(token),
    )
    assert rewritten.status_code == 200, rewritten.text
    assert rewritten.json()["content"]["research"] == research.summary.model_dump()
    assert rewritten.json()["seo"]["review_status"] == "needs_review"
    assert "https://example.com/research" in rewritten.json()["html"]
    assert fallback.calls == ["article_generation", "draft_review", "rewrite"]
    row = db_session.scalar(select(Generation).where(Generation.kind == "rewrite"))
    assert row is not None
    assert (row.provider, row.model) == ("fallback", "fallback-model")


def test_expired_budget_keeps_valid_article_without_starting_seo_repair(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.repositories.generation_repo import GenerationRepository

    clock = [1000.0]
    monkeypatch.setattr(routing, "get_fallback_provider", lambda: None)

    class MissingSeoProvider(FixtureProvider):
        def generate(self, prompt_name, prompt_version, variables, schema):
            response = super().generate(prompt_name, prompt_version, variables, schema)
            return replace(response, data=response.data.model_copy(update={"seo": None}))

    provider = MissingSeoProvider("primary")
    monkeypatch.setattr("app.services.generation_service.get_provider", lambda: provider)
    monkeypatch.setattr("app.services.generation_service.retrieve_sources", lambda _: (
        ResearchResult(ResearchSummary(), "No sources in offline fixture.")
    ))
    original_record = GenerationRepository.record

    def record(self, **kwargs):
        row = original_record(self, **kwargs)
        if kwargs["kind"] == "article":
            clock[0] += 100
        return row

    monkeypatch.setattr(GenerationRepository, "record", record)
    token = register_user(client)["access_token"]
    # Freeze only the service's monotonic budget; the TestClient event loop needs
    # its real clock to complete the request while this fixture advances time.
    monkeypatch.setattr(budget, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    response = client.post(
        "/api/v1/articles", json={"query": "Growing plants"}, headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text
    assert response.json()["seo"]["review_status"] == "needs_review"
    assert provider.calls == ["article_generation"]


@pytest.mark.parametrize("kind", ["article", "rewrite"])
def test_invalid_citation_after_fallback_records_actual_provider_without_another_attempt(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch, kind: str,
) -> None:
    primary, _ = install_routes(monkeypatch)
    primary.transient_failures_remaining = 99
    monkeypatch.setattr(settings, "ai_max_retries", 0)

    class InvalidCitationFallback(FixtureProvider):
        def generate(self, prompt_name, prompt_version, variables, schema):
            response = super().generate(prompt_name, prompt_version, variables, schema)
            if (kind == "article" and prompt_name == "article_generation") or (
                kind == "rewrite" and prompt_name == "rewrite"
            ):
                response.data.introduction += " An unsupported source [S9]."
            return response

    fallback = InvalidCitationFallback("fallback")
    monkeypatch.setattr(routing, "get_fallback_provider", lambda: fallback)
    monkeypatch.setattr("app.services.generation_service.get_provider", lambda: primary)
    monkeypatch.setattr("app.services.generation_service.retrieve_sources", lambda _: (
        ResearchResult(ResearchSummary(), "No sources in offline fixture.")
    ))
    token = register_user(client)["access_token"]
    response = client.post(
        "/api/v1/articles", json={"query": "Growing plants"}, headers=auth_headers(token),
    )
    if kind == "rewrite":
        assert response.status_code == 201
        article_id = response.json()["id"]
        response = client.post(
            f"/api/v1/articles/{article_id}/rewrite",
            json={"style": "professional"}, headers=auth_headers(token),
        )
        saved = client.get(f"/api/v1/articles/{article_id}", headers=auth_headers(token)).json()
        assert saved["current_version"] == 1
    else:
        assert client.get("/api/v1/articles", headers=auth_headers(token)).json()["items"] == []
    assert response.status_code == 502, response.text
    failed = db_session.scalar(select(Generation).where(
        Generation.kind == kind, Generation.status == "failed",
    ))
    assert failed is not None
    assert (failed.provider, failed.model) == ("fallback", "fallback-model")
    assert failed.error_code == "SchemaValidationError"
    assert fallback.calls == (["article_generation", "rewrite"] if kind == "rewrite" else [
        "article_generation",
    ])
