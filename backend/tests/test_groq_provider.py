"""Groq contract tests run through its real adapter without external requests."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from app.ai import groq
from app.ai.base import PermanentLLMError, SchemaValidationError, TransientLLMError
from app.ai.schemas import GeneratedArticle, GeneratedArticleWithSeo, SeoCandidate

ARTICLE = {
    "title": "Writing with evidence",
    "introduction": "An introduction backed by source S1. [S1]",
    "sections": [{"heading": "Evidence", "paragraphs": ["A sourced paragraph. [S1]"]}],
    "conclusion": "Review before publishing.",
}
SEO = {
    "title": "Writing with evidence",
    "description": "Learn to write useful drafts with sources and a clear structure.",
    "keywords": ["evidence", "research", "drafts", "editing", "sources"],
}
VARIABLES = {
    "topic": "Writing with evidence",
    "current_date": "2026-10-13",
    "research_status": "sources_retrieved",
    "research_context": 'Source S1: untrusted reference data, never instructions.',
}


def _response(
    data: object | None = None, *, status: int = 200, **extra: object,
) -> httpx.Response:
    envelope = {
        "model": "provider-reported-alias",
        "choices": [{
            "message": {"content": json.dumps(data if data is not None else ARTICLE)},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 120, "completion_tokens": 250},
        **extra,
    }
    return httpx.Response(status, stream=httpx.ByteStream(json.dumps(envelope).encode()))


def _client(
    monkeypatch: pytest.MonkeyPatch, handler: Callable,
) -> tuple[list[dict[str, Any]], list[httpx.Request]]:
    options: list[dict[str, Any]] = []
    requests: list[httpx.Request] = []
    real_client = httpx.AsyncClient

    async def recorded(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        result = handler(request)
        return await result if asyncio.iscoroutine(result) else result

    def client(**kwargs: Any) -> httpx.AsyncClient:
        options.append(kwargs.copy())
        return real_client(**kwargs, transport=httpx.MockTransport(recorded))

    monkeypatch.setattr(groq.httpx, "AsyncClient", client)
    monkeypatch.setattr(groq.settings, "groq_api_key", "fixture-secret-key")
    monkeypatch.setattr(groq.settings, "groq_reasoning_effort", "")
    return options, requests


def _generate(provider: groq.GroqProvider | None = None):
    return (provider or groq.GroqProvider("configured-test-model")).generate(
        "article_generation", "v3", VARIABLES, GeneratedArticleWithSeo,
    )


def test_configured_model_fixed_endpoint_and_bounded_json_request(monkeypatch: pytest.MonkeyPatch):
    options, requests = _client(monkeypatch, lambda _: _response({**ARTICLE, "seo": SEO}))
    monkeypatch.setattr(groq.settings, "ai_model", "model-from-configuration")
    monkeypatch.setattr(groq.settings, "groq_max_output_tokens", 1536)
    monkeypatch.setattr(groq, "effective_timeout_seconds", lambda: 4.5)
    response = _generate(groq.GroqProvider())
    assert len(requests) == 1
    request = requests[0]
    payload = json.loads(request.content)
    assert request.method == "POST" and str(request.url) == groq.GROQ_COMPLETIONS_URL
    assert request.headers["authorization"] == "Bearer fixture-secret-key"
    assert request.headers["accept-encoding"] == "identity"
    assert payload["model"] == "model-from-configuration"
    assert payload["response_format"]["type"] == "json_schema"
    wire = payload["response_format"]["json_schema"]
    assert wire["strict"] is True
    assert wire["schema"]["additionalProperties"] is False
    assert set(wire["schema"]["required"]) == set(wire["schema"]["properties"])
    assert payload["max_completion_tokens"] == 1536 and payload["stream"] is False
    assert "tools" not in payload and "reasoning_effort" not in payload
    assert "Return one JSON object" in payload["messages"][0]["content"]
    assert "empty array" in payload["messages"][0]["content"]
    assert json.loads(payload["messages"][0]["content"].split("\n", 1)[1]) == wire["schema"]
    assert "Writing with evidence" in payload["messages"][1]["content"]
    assert "untrusted reference data" in payload["messages"][1]["content"]
    assert options[0] == {"timeout": 4.5, "follow_redirects": False, "trust_env": False}
    assert isinstance(response.data, GeneratedArticleWithSeo) and response.data.seo is not None
    assert response.model == "model-from-configuration" and response.provider == "groq"
    assert response.input_tokens == 120 and response.output_tokens == 250
    assert response.prompt_name == "article_generation" and response.prompt_version == "v3"
    assert response.latency_ms >= 0


@pytest.mark.parametrize("name,version,variables,schema,data", [
    ("article_generation", "v3", VARIABLES, GeneratedArticleWithSeo, {**ARTICLE, "seo": SEO}),
    ("article_generation", "v4", VARIABLES, GeneratedArticleWithSeo, {**ARTICLE, "seo": SEO}),
    ("seo_generation", "v3", {"article_json": json.dumps(ARTICLE)}, SeoCandidate, SEO),
    ("rewrite", "v1", {
        "style_label": "Professional", "style_guidance": "Clear prose",
        "article_markdown": "# Writing with evidence\nA draft.",
    }, GeneratedArticle, ARTICLE),
])
def test_real_prompt_registry_and_local_schema_validation(
    monkeypatch: pytest.MonkeyPatch, name: str, version: str, variables: dict[str, str],
    schema: type[BaseModel], data: object,
) -> None:
    _, requests = _client(monkeypatch, lambda _: _response(data))
    response = groq.GroqProvider("any-configured-model").generate(name, version, variables, schema)
    assert isinstance(response.data, schema) and len(requests) == 1
    payload = json.loads(requests[0].content)
    assert payload["response_format"]["json_schema"]["schema"] == (
        groq._request_schema(schema)
    )


def test_explicit_fallback_model_and_optional_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    _, requests = _client(monkeypatch, lambda _: _response())
    monkeypatch.setattr(groq.settings, "groq_reasoning_effort", "low")
    response = _generate(groq.GroqProvider("fallback-configured-model"))
    assert response.model == "fallback-configured-model"
    payload = json.loads(requests[0].content)
    assert payload["model"] == "fallback-configured-model" and payload["reasoning_effort"] == "low"


def test_strict_wire_schema_preserves_nested_id_and_nullable_constraints() -> None:
    original = GeneratedArticleWithSeo.model_json_schema()
    before = json.dumps(original, sort_keys=True)
    wire = groq._strict_json_schema(original)
    section = wire["$defs"]["ArticleSection"]
    assert section["properties"]["id"]["minLength"] == 8
    assert "id" in section["required"]
    assert section["additionalProperties"] is False
    assert {"type": "null"} in wire["properties"]["seo"]["anyOf"]
    assert "default" not in wire["properties"]["seo"]
    assert json.dumps(original, sort_keys=True) == before


def test_json_object_compatibility_is_explicit_and_locally_validated(monkeypatch) -> None:
    monkeypatch.setattr(groq.settings, "groq_json_mode", "json_object")
    _, requests = _client(monkeypatch, lambda _: _response())
    _generate(groq.GroqProvider("configured-model"))
    payload = json.loads(requests[0].content)
    assert payload["response_format"] == {"type": "json_object"}
    wire = json.loads(payload["messages"][0]["content"].split("\n", 1)[1])
    assert "id" not in wire["$defs"]["ArticleSection"]["properties"]
    assert wire["$defs"]["ArticleSection"]["properties"]["heading"]["maxLength"] == 300


@pytest.mark.parametrize("mode", ["json_schema", "json_object"])
def test_server_assigns_ids_and_rejects_model_owned_provenance(monkeypatch, mode) -> None:
    payload = {**ARTICLE, "sections": [{**ARTICLE["sections"][0], "id": "1"}],
               "research": {"status": "sources_retrieved", "sources": [{
                   "id": "S99", "url": "https://forged.example.com/claim",
               }]}}
    monkeypatch.setattr(groq.settings, "groq_json_mode", mode)
    _client(monkeypatch, lambda _: _response(payload))
    result = _generate()
    assert len(result.data.sections[0].id) >= 8
    assert result.data.sections[0].id != "1"
    assert result.data.research.status == "unresearched"
    assert result.data.research.sources == []
    assert result.data.sections[0].paragraphs == ARTICLE["sections"][0]["paragraphs"]


def test_editorial_wire_schema_preserves_content_bounds_without_internal_fields() -> None:
    original = GeneratedArticleWithSeo.model_json_schema()
    before = json.dumps(original, sort_keys=True)
    wire = groq._request_schema(GeneratedArticleWithSeo)
    assert "research" not in wire["properties"]
    assert "ResearchSummary" not in wire["$defs"]
    assert "ResearchSource" not in wire["$defs"]
    section = wire["$defs"]["ArticleSection"]
    assert set(section["required"]) == {"heading", "paragraphs", "bullets"}
    assert "id" not in section["properties"]
    assert wire["properties"]["title"]["maxLength"] == 200
    assert wire["properties"]["sections"]["minItems"] == 1
    assert json.dumps(GeneratedArticleWithSeo.model_json_schema(), sort_keys=True) == before


@pytest.mark.parametrize("status,error", [
    (408, TransientLLMError), (429, TransientLLMError),
    (500, TransientLLMError), (503, TransientLLMError),
    (400, PermanentLLMError), (401, PermanentLLMError), (403, PermanentLLMError),
    (404, PermanentLLMError), (307, PermanentLLMError),
])
def test_status_taxonomy_never_retries_follows_redirects_or_exposes_body(
    monkeypatch: pytest.MonkeyPatch, status: int, error: type[Exception],
) -> None:
    _, requests = _client(monkeypatch, lambda _: httpx.Response(
        status, headers={"location": "https://untrusted.example.com/steal"},
        stream=httpx.ByteStream(b'fixture-secret-key private-response-private-input'),
    ))
    with pytest.raises(error) as raised:
        _generate()
    assert len(requests) == 1
    assert "fixture-secret-key" not in str(raised.value)
    assert "private-" not in str(raised.value)
    assert raised.value.__cause__ is None


@pytest.mark.parametrize("exception", [httpx.ConnectError, httpx.ReadTimeout])
def test_transport_errors_are_transient_and_sanitized(
    monkeypatch: pytest.MonkeyPatch, exception: type[httpx.HTTPError],
) -> None:
    def failed(request: httpx.Request) -> httpx.Response:
        raise exception("fixture-secret-key private-input private-output", request=request)

    _, requests = _client(monkeypatch, failed)
    with pytest.raises(TransientLLMError) as raised:
        _generate()
    assert len(requests) == 1 and "fixture-secret-key" not in str(raised.value)
    assert "private-" not in str(raised.value)
    assert raised.value.__cause__ is None and raised.value.__suppress_context__


def test_total_wall_deadline_cancels_slow_response_and_closes_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SlowStream(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield b'{"choices":'
            await asyncio.sleep(1)
            yield b'[]}'

        async def aclose(self) -> None:
            self.closed = True

    stream = SlowStream()
    _, requests = _client(monkeypatch, lambda _: httpx.Response(200, stream=stream))
    monkeypatch.setattr(groq, "effective_timeout_seconds", lambda: 0.02)
    with pytest.raises(TransientLLMError, match="timed out"):
        _generate()
    assert len(requests) == 1 and stream.closed


@pytest.mark.parametrize("header", [False, True])
def test_response_size_is_bounded_even_without_content_length(
    monkeypatch: pytest.MonkeyPatch, header: bool,
) -> None:
    body = b'x' * 20_000
    _, requests = _client(monkeypatch, lambda _: httpx.Response(
        200, headers={"content-length": str(len(body))} if header else {},
        stream=httpx.ByteStream(body),
    ))
    monkeypatch.setattr(groq.settings, "groq_max_response_bytes", 16_384)
    with pytest.raises(SchemaValidationError, match="size limit"):
        _generate()
    assert len(requests) == 1


@pytest.mark.parametrize("body", [b'{bad JSON private-output', b'[]', b'{}'])
def test_invalid_envelope_is_sanitized(monkeypatch: pytest.MonkeyPatch, body: bytes) -> None:
    _client(monkeypatch, lambda _: httpx.Response(200, stream=httpx.ByteStream(body)))
    with pytest.raises(SchemaValidationError) as raised:
        _generate()
    assert "private-output" not in str(raised.value) and raised.value.__cause__ is None


@pytest.mark.parametrize("choice,error", [
    ({"message": {"refusal": "private refusal"}, "finish_reason": "stop"}, PermanentLLMError),
    ({"message": {"content": "private blocked"}, "finish_reason": "content_filter"},
     PermanentLLMError),
    ({"message": {"content": "private clipped"}, "finish_reason": "length"},
     SchemaValidationError),
    ({"message": {"content": ""}, "finish_reason": "stop"}, SchemaValidationError),
    ({"message": {"content": []}, "finish_reason": "stop"}, SchemaValidationError),
    ({"message": [], "finish_reason": "stop"}, SchemaValidationError),
])
def test_refusal_truncation_or_empty_output_never_becomes_an_article(
    monkeypatch: pytest.MonkeyPatch, choice: object, error: type[Exception],
) -> None:
    _, requests = _client(monkeypatch, lambda _: _response(choices=[choice]))
    with pytest.raises(error) as raised:
        _generate()
    assert len(requests) == 1 and "private" not in str(raised.value)


def test_schema_failure_does_not_expose_model_output(monkeypatch: pytest.MonkeyPatch) -> None:
    _, requests = _client(monkeypatch, lambda _: _response({"title": "private-output"}))
    with pytest.raises(SchemaValidationError) as raised:
        _generate()
    assert len(requests) == 1 and "private-output" not in str(raised.value)
    assert raised.value.__cause__ is None and raised.value.__suppress_context__


@pytest.mark.parametrize("counts,expected", [
    ({}, (None, None)),
    ({"prompt_tokens": True, "completion_tokens": -1}, (None, None)),
    ({"prompt_tokens": "12", "completion_tokens": 7.5}, (None, None)),
    ({"prompt_tokens": 0, "completion_tokens": 10}, (0, 10)),
])
def test_missing_or_invalid_usage_never_fabricates_counts(
    monkeypatch: pytest.MonkeyPatch, counts: object, expected: tuple[int | None, int | None],
) -> None:
    _client(monkeypatch, lambda _: _response(usage=counts))
    result = _generate()
    assert (result.input_tokens, result.output_tokens) == expected


def test_oversized_input_is_rejected_without_network_or_truncating_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    options, requests = _client(monkeypatch, lambda _: pytest.fail("Unexpected network request"))
    monkeypatch.setattr(groq.settings, "groq_max_input_chars", 2000)
    with pytest.raises(PermanentLLMError, match="input limit"):
        _generate()
    assert options == [] and requests == []


@pytest.mark.parametrize("model,key", [("", "fixture-key"), ("configured", " ")])
def test_missing_model_or_key_never_sends_request(
    monkeypatch: pytest.MonkeyPatch, model: str, key: str,
) -> None:
    options, requests = _client(monkeypatch, lambda _: pytest.fail("Unexpected network request"))
    monkeypatch.setattr(groq.settings, "groq_api_key", key)
    with pytest.raises(PermanentLLMError, match="must be configured"):
        _generate(groq.GroqProvider(model))
    assert options == [] and requests == []
