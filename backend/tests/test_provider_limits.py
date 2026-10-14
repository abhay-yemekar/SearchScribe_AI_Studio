"""Quota responses through adapters, retry routing and the persisted article API."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from conftest import auth_headers, generate_article, register_user
from google.genai import errors as genai_errors

from app.ai import base, budget, gemini, routing
from app.ai.base import RateLimitedLLMError
from app.ai.factory import get_provider
from app.ai.rate_limits import gemini_rate_limit, retry_seconds
from app.ai.schemas import SeoResult


@pytest.mark.parametrize("value", [
    None, True, 4, "NaN", "inf", "-2", "0", "999999", "1e5", "<script>",
])
def test_invalid_retry_guidance_is_ignored(value):
    assert retry_seconds(value) is None


@pytest.mark.parametrize("daily,delay", [(True, "44127s"), (False, "2.25s")])
def test_gemini_adapter_retains_safe_structured_quota_metadata(monkeypatch, daily, delay):
    details = {"error": {"message": "private project and prompt", "details": [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [
            {"quotaId": "GenerateRequestsPerDayPerProject" if daily else "RequestsPerMinute"},
        ]},
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": delay},
    ]}}

    async def fail(**_):
        raise genai_errors.APIError(429, details)

    monkeypatch.setattr(gemini, "_generate_content", fail)
    with pytest.raises(RateLimitedLLMError) as caught:
        gemini.GeminiProvider().generate(
            "seo_generation", "v1", {"title": "T", "introduction": "I"}, SeoResult,
        )
    assert caught.value.daily is daily
    assert caught.value.retry_after_seconds == (44127 if daily else 3)
    assert str(caught.value) == "gemini rate limit reached"
    assert caught.value.__suppress_context__


@pytest.mark.parametrize("details", [
    None, [], {"error": []}, {"error": {"details": [None, 1, {}]}},
])
def test_unknown_quota_format_stays_generic(details):
    error = gemini_rate_limit(details, "12")
    assert not error.daily and error.retry_after_seconds == 12


def test_daily_quota_skips_retries_but_allows_one_explicit_fallback(monkeypatch):
    primary = SimpleNamespace(name="primary", model="primary-model")
    fallback = SimpleNamespace(name="fallback", model="fallback-model")
    monkeypatch.setattr(routing, "get_fallback_provider", lambda: fallback)
    calls = []

    def fail(provider):
        calls.append(provider.name)
        raise RateLimitedLLMError("limited", daily=True, retry_after_seconds=3600)

    def forbid_sleep(_):
        pytest.fail("Daily quota must not wait or retry")

    monkeypatch.setattr(base.time, "sleep", forbid_sleep)
    with pytest.raises(RateLimitedLLMError) as caught:
        routing.call_with_fallback(primary, fail)
    assert calls == ["primary", "fallback"]
    assert caught.value.daily and caught.value.retry_after_seconds == 3600
    assert (caught.value.provider, caught.value.model) == ("fallback", "fallback-model")


def test_short_rate_limit_honors_provider_delay_inside_the_budget(monkeypatch):
    calls, sleeps = [], []
    monkeypatch.setattr(base.random, "uniform", lambda *_: 0)
    monkeypatch.setattr(base.time, "sleep", sleeps.append)

    def generate():
        calls.append(1)
        if len(calls) == 1:
            raise RateLimitedLLMError("limited", retry_after_seconds=3)
        return "ok"

    with budget.attempt_budget(10):
        assert base.call_with_retry(generate, max_retries=2) == "ok"
    assert len(calls) == 2 and sleeps == [3]


def test_long_rate_limit_surfaces_original_guidance_without_waiting(monkeypatch):
    calls = []

    def fail():
        calls.append(1)
        raise RateLimitedLLMError("limited", retry_after_seconds=600)

    monkeypatch.setattr(base.time, "sleep", lambda _: pytest.fail("Must not wait"))
    with budget.attempt_budget(2), pytest.raises(RateLimitedLLMError) as caught:
        base.call_with_retry(fail, max_retries=2)
    assert calls == [1] and caught.value.retry_after_seconds == 600


@pytest.mark.parametrize("operation", ["generate", "rewrite"])
@pytest.mark.parametrize("daily,delay", [(True, 3600), (False, None)])
def test_limit_response_preserves_existing_article_and_versions(
    client, monkeypatch, operation, daily, delay,
):
    tokens = register_user(client)
    headers = auth_headers(tokens["access_token"])
    original = generate_article(client, tokens["access_token"])
    calls = []

    def fail(*_):
        calls.append(1)
        raise RateLimitedLLMError("sanitized limit", daily=daily, retry_after_seconds=delay)

    monkeypatch.setattr(get_provider(), "generate", fail)
    monkeypatch.setattr(base.time, "sleep", lambda _: None)
    before = datetime.now(UTC)
    path = ("/api/v1/articles" if operation == "generate"
            else f"/api/v1/articles/{original['id']}/rewrite")
    response = client.post(path, headers=headers, json=(
        {"query": "A topic to keep"} if operation == "generate" else {"style": "genz"}
    ))
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == ("AI_DAILY_LIMIT_REACHED" if daily else "AI_SERVICE_BUSY")
    assert "saved articles are unchanged" in error["message"]
    if delay:
        assert response.headers["retry-after"] == str(delay)
        assert error["details"]["retry_after_seconds"] == delay
        suggested = datetime.fromisoformat(error["details"]["retry_at"])
        assert delay <= (suggested - before).total_seconds() < delay + 10
        assert len(calls) == 1
    else:
        assert "details" not in error and "retry-after" not in response.headers
    assert client.get(f"/api/v1/articles/{original['id']}", headers=headers).json() == original
    assert len(client.get("/api/v1/articles", headers=headers).json()["items"]) == 1
    versions = client.get(f"/api/v1/articles/{original['id']}/versions", headers=headers).json()
    assert len(versions["items"]) == 1


def test_optional_seo_quota_failure_keeps_valid_article_for_manual_review(client, monkeypatch):
    tokens = register_user(client)
    provider = get_provider()
    original_generate = provider.generate
    calls = []

    def generate(name, version, variables, schema):
        calls.append(name)
        if name == "seo_generation":
            raise RateLimitedLLMError("limited", daily=True)
        response = original_generate(name, version, variables, schema)
        return replace(response, data=response.data.model_copy(update={"seo": None}))

    monkeypatch.setattr(provider, "generate", generate)
    detail = generate_article(client, tokens["access_token"])
    assert detail["seo"]["review_status"] == "needs_review"
    assert detail["current_version"] == 1
    assert calls == ["article_generation", "seo_generation"]
