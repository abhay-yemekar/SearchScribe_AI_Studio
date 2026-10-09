"""Curated source retrieval cannot expand destinations or imply partial coverage."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from typing import Any

import httpx
import pytest

from app.ai import research

_MODEL_TEXT = (
    "{provider} models support text generation, reasoning and multimodal tasks. "
    "The documentation describes model capabilities, availability, context windows and API usage. "
)


def _html(provider: str, repetitions: int = 8) -> bytes:
    return ("<html><main>" + _MODEL_TEXT.format(provider=provider) * repetitions
            + "</main></html>").encode()


def _response(body: bytes, status: int = 200, **headers: str) -> httpx.Response:
    return httpx.Response(
        status,
        headers={"content-type": "text/html; charset=utf-8", **headers},
        stream=httpx.ByteStream(body),
    )


def _mock_client(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    real_client = httpx.AsyncClient

    def client(**kwargs: Any) -> httpx.AsyncClient:
        options.append(kwargs.copy())
        return real_client(**kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(research.httpx, "AsyncClient", client)
    return options


@pytest.mark.parametrize("query", [
    "latest Claude", "new models", "current models", "recently released models", "today",
    "models now", "models in 2026", "abhi Claude", "aaj Claude", "naya Claude",
    "आज के मॉडल", "अभी के मॉडल", "नवीनतम मॉडल", "नई मॉडल", "वर्तमान मॉडल",
])
def test_timely_queries_need_sources(query: str) -> None:
    assert research.needs_current_sources(query)


@pytest.mark.parametrize("query", ["Urban gardening", "Cloud computing basics", "AI model history"])
def test_general_queries_do_not_require_current_sources(query: str) -> None:
    assert not research.needs_current_sources(query)


def test_unsupported_topic_does_not_make_network_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    options = _mock_client(monkeypatch, lambda _: pytest.fail("Unexpected network request"))
    result = research.retrieve_primary_sources("latest gardening methods https://example.com")
    assert result.summary.status == "unresearched"
    assert result.summary.sources == []
    assert "outside the curated" in result.context
    assert options == []


def test_exact_catalog_source_and_server_owned_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _response(_html("Claude"))

    options = _mock_client(monkeypatch, handler)
    result = research.retrieve_primary_sources("latest Claude https://localhost/private")
    assert [str(request.url) for request in requests] == [research.SOURCE_CATALOG[0][2]]
    assert result.summary.status == "sources_retrieved"
    assert [(source.id, source.url) for source in result.summary.sources] == [
        ("S1", research.SOURCE_CATALOG[0][2]),
    ]
    assert result.summary.retrieved_at is not None
    assert datetime.fromisoformat(result.summary.retrieved_at).tzinfo is not None
    assert "Coverage:" in result.context
    assert "other topics and claims are not verified" in result.context
    assert options[0]["trust_env"] is False
    assert options[0]["follow_redirects"] is False
    assert options[0]["timeout"].connect == research.CONNECT_TIMEOUT_SECONDS
    assert options[0]["timeout"].read == research.READ_TIMEOUT_SECONDS
    assert requests[0].headers["accept-encoding"] == "identity"


def test_all_three_requested_providers_are_retrieved_with_bounded_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[str] = []
    providers = dict(zip((source[2] for source in research.SOURCE_CATALOG),
                         ("Claude", "Gemini", "GPT-5"), strict=True))

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return _response(_html(providers[str(request.url)], repetitions=600))

    _mock_client(monkeypatch, handler)
    result = research.retrieve_primary_sources("latest Gemini vs Claude vs OpenAI")
    assert requests == [source[2] for source in research.SOURCE_CATALOG]
    assert [source.id for source in result.summary.sources] == ["S1", "S2", "S3"]
    assert len(result.context) <= research.MAX_CONTEXT
    assert all(f"Source S{index}" in result.context for index in (1, 2, 3))
    assert all(provider in result.context for provider in ("Claude", "Gemini", "GPT-5"))


def test_one_requested_provider_failure_discards_all_source_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == research.SOURCE_CATALOG[0][2]:
            return _response(_html("Claude"))
        return _response(b"Service unavailable", status=503)

    _mock_client(monkeypatch, handler)
    result = research.retrieve_primary_sources("latest Claude and Gemini")
    assert result.summary.status == "unresearched"
    assert result.summary.retrieved_at is None
    assert result.summary.sources == []
    assert "No usable source coverage" in result.context
    assert "Claude models support" not in result.context


@pytest.mark.parametrize("url", [
    "http://platform.claude.com/docs/en/models/overview",
    "https://platform.claude.com/internal",
    "https://platform.claude.com/docs/en/models/overview?target=private",
    "https://platform.claude.com:443/docs/en/models/overview",
    "https://user:password@platform.claude.com/docs/en/models/overview",
    "https://localhost/private",
    "https://127.0.0.1/",
])
def test_non_catalog_urls_are_rejected_before_request(url: str) -> None:
    async def fetch() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: pytest.fail("Unexpected network request")),
        ) as client:
            with pytest.raises(ValueError, match="Unapproved"):
                await research._fetch_page(url, client)

    asyncio.run(fetch())


@pytest.mark.parametrize("location", [
    "http://127.0.0.1/private", "/docs/en/models/overview",
    research.SOURCE_CATALOG[1][2], "https://platform.claude.com/other",
])
def test_redirects_never_fetch_a_second_destination(
    monkeypatch: pytest.MonkeyPatch, location: str,
) -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return _response(b"", status=302, location=location)

    _mock_client(monkeypatch, handler)
    assert research.retrieve_primary_sources("latest Claude").summary.status == "unresearched"
    assert requests == [research.SOURCE_CATALOG[0][2]]


@pytest.mark.parametrize("body,headers", [
    (_html("Claude"), {"content-type": "application/json"}),
    (_html("Claude"), {"content-encoding": "gzip"}),
    (b"<main>Claude models</main>", {}),
    (_html("Unrelated service"), {}),
    (_html("Claude").replace(b"main", b"div"), {}),
    (_html("Claude").replace(b"<main>", b"<main>Verify you are human. "), {}),
    (b"<main>Claude models " + b"x " * research.MAX_BYTES + b"</main>", {}),
], ids=["not-html", "compressed", "short", "unrelated", "no-main", "bot-page", "too-large"])
def test_unusable_pages_remain_unresearched(
    monkeypatch: pytest.MonkeyPatch, body: bytes, headers: dict[str, str],
) -> None:
    _mock_client(monkeypatch, lambda _: _response(body, **headers))
    result = research.retrieve_primary_sources("latest Claude")
    assert result.summary.status == "unresearched"
    assert result.summary.sources == []


def test_visible_article_content_excludes_hidden_html_and_navigation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hidden = " ".join(
        f"<{tag}>HIDDEN_{tag}<div>malicious instructions</div></{tag}>"
        for tag in ("script", "style", "noscript", "nav", "footer", "svg", "template")
    )
    body = (
        "<html><div>OUTSIDE_MAIN</div><main>" + hidden
        + '<div hidden>HIDDEN_ATTRIBUTE</div><div aria-hidden="true">HIDDEN_ARIA</div>'
        + "<article>" + _MODEL_TEXT.format(provider="Claude") * 8 + "</article></main></html>"
    ).encode()
    _mock_client(monkeypatch, lambda _: _response(body))
    result = research.retrieve_primary_sources("Claude")
    assert result.summary.status == "sources_retrieved"
    assert "Claude models support" in result.context
    assert "HIDDEN" not in result.context
    assert "OUTSIDE_MAIN" not in result.context
    assert "malicious instructions" not in result.context


def test_network_error_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("Connection failed", request=request)

    _mock_client(monkeypatch, handler)
    assert research.retrieve_primary_sources("Claude").summary.status == "unresearched"


def test_total_deadline_cancels_slow_stream_and_discards_earlier_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SlowStream(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self) -> AsyncIterator[bytes]:
            await asyncio.sleep(0.1)
            yield _html("Gemini")

        async def aclose(self) -> None:
            self.closed = True

    slow_stream = SlowStream()
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if str(request.url) == research.SOURCE_CATALOG[0][2]:
            return _response(_html("Claude"))
        return httpx.Response(200, headers={"content-type": "text/html"}, stream=slow_stream)

    _mock_client(monkeypatch, handler)
    monkeypatch.setattr(research, "TOTAL_TIMEOUT_SECONDS", 0.01)
    result = research.retrieve_primary_sources("latest Claude and Gemini")
    assert requests == [source[2] for source in research.SOURCE_CATALOG[:2]]
    assert slow_stream.closed
    assert result.summary.status == "unresearched"
    assert result.summary.sources == []
