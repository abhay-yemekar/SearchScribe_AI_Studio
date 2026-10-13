"""Dynamic search transport, budgets, safe source URLs and freshness failure states."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from app.ai import research
from app.ai.schemas import GeneratedArticle, ResearchSource
from app.core.config import Settings

EXCERPT = (
    "The report describes the post and its context, identifies the author and provides "
    "a dated account of the statements with links to supporting source material."
)


@pytest.fixture(autouse=True)
def _query_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    class QueryClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 13, 8, 30, tzinfo=UTC)

    monkeypatch.setattr(research, "datetime", QueryClock)


def _result(**updates: object) -> dict[str, object]:
    return {
        "url": "https://news.example.com/article", "title": "A dated report",
        "content": EXCERPT, "score": 0.9, "published_date": "Tue, 13 Oct 2026 04:00:00 GMT",
        **updates,
    }


def _response(results: list[object], status: int = 200) -> httpx.Response:
    return httpx.Response(
        status, headers={"content-type": "application/json"},
        stream=httpx.ByteStream(json.dumps({"results": results}).encode()),
    )


def _client(monkeypatch: pytest.MonkeyPatch, handler: Callable) -> list[dict[str, Any]]:
    options = []
    real = httpx.AsyncClient

    def client(**kwargs: Any) -> httpx.AsyncClient:
        options.append(kwargs.copy())
        return real(**kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(research.httpx, "AsyncClient", client)
    monkeypatch.setattr(research.settings, "tavily_api_key", "fixture-key")
    return options


@pytest.mark.parametrize("query", [
    "Elon Musk latest tweet", "latest gardening methods", "आज की खबर", "current Claude models",
])
def test_actual_query_uses_only_fixed_basic_search_endpoint(
    monkeypatch: pytest.MonkeyPatch, query: str,
) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _response([_result()])

    options = _client(monkeypatch, handler)
    found = research.retrieve_sources(query)
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert str(requests[0].url) == research.TAVILY_SEARCH_URL
    payload = json.loads(requests[0].content)
    assert payload["query"] == query
    assert payload["search_depth"] == "basic" and payload["auto_parameters"] is False
    assert payload["max_results"] <= 5
    assert payload["include_answer"] is False and payload["include_raw_content"] is False
    assert found.summary.status == "sources_retrieved"
    assert found.summary.sources[0].published_at == "2026-10-13T04:00:00+00:00"
    assert found.summary.retrieved_at != found.summary.sources[0].published_at
    assert "not a publication date" in found.context and "provider estimates" in found.context
    assert options[0]["trust_env"] is False and options[0]["follow_redirects"] is False


def test_missing_key_does_not_request_or_leak_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    options = _client(monkeypatch, lambda _: pytest.fail("Unexpected network request"))
    monkeypatch.setattr(research.settings, "tavily_api_key", " ")
    found = research.retrieve_sources("latest news")
    assert found.failure == "not_configured" and options == []


@pytest.mark.parametrize("url", [
    "http://example.com", "https://localhost/private", "https://foo.local/private",
    "https://127.0.0.1/", "https://10.0.0.1/", "https://[::1]/", "https://2130706433/",
    "https://user:secret@example.com/", "https://example.com:8000/", "https://example.com:bad/",
    "javascript:alert(1)", "https://example.com/\nprivate", "https://example.com\\@localhost/",
])
def test_unsafe_sources_are_not_exposed_or_fetched(
    monkeypatch: pytest.MonkeyPatch, url: str,
) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return _response([_result(url=url)])

    _client(monkeypatch, handler)
    assert research.retrieve_sources("any topic").failure == "no_evidence"
    assert requests == [research.TAVILY_SEARCH_URL]
    with pytest.raises(ValidationError):
        ResearchSource(id="S1", title="Unsafe", url=url)


def test_duplicate_low_score_short_invalid_results_are_filtered(monkeypatch: pytest.MonkeyPatch):
    _client(monkeypatch, lambda _: _response([
        _result(score=0.01), _result(content="Too short"), _result(), _result(),
        _result(url="https://other.example.com/report", published_date="not a date"),
    ]))
    found = research.retrieve_sources("any topic")
    assert [s.id for s in found.summary.sources] == ["S1", "S2"]
    assert found.summary.sources[1].published_at is None


def test_context_and_result_counts_are_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    _client(monkeypatch, lambda _: _response([
        _result(url=f"https://news.example.com/{index}", content=EXCERPT * 40)
        for index in range(10)
    ]))
    found = research.retrieve_sources("any topic")
    assert len(found.summary.sources) <= 5
    assert len(found.context) <= research.settings.research_max_context_chars
    records = [json.loads(line) for line in found.context.splitlines()[1:]]
    assert [r["id"] for r in records] == [s.id for s in found.summary.sources]
    assert all(len(r["excerpt"]) <= research.settings.research_max_excerpt_chars for r in records)


@pytest.mark.parametrize("status", [301, 401, 429, 432, 500])
def test_provider_errors_do_not_retry_or_expose_body(monkeypatch: pytest.MonkeyPatch, status: int):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return _response([_result(title="fixture-key")], status)

    _client(monkeypatch, handler)
    found = research.retrieve_sources("latest news")
    assert found.failure == "unavailable" and len(calls) == 1
    assert "fixture-key" not in found.context


def test_oversized_response_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _client(monkeypatch, lambda _: _response([_result(content="x" * 20_000)]))
    monkeypatch.setattr(research.settings, "research_max_response_bytes", 16_384)
    assert research.retrieve_sources("latest news").failure == "unavailable"


def test_outer_deadline_closes_slow_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    class SlowStream(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self) -> AsyncIterator[bytes]:
            await asyncio.sleep(0.1)
            yield b'{"results": []}'

        async def aclose(self) -> None:
            self.closed = True

    stream = SlowStream()
    _client(monkeypatch, lambda _: httpx.Response(
        200, headers={"content-type": "application/json"}, stream=stream,
    ))
    monkeypatch.setattr(research.settings, "research_timeout_seconds", 0.01)
    assert research.retrieve_sources("latest news").failure == "unavailable"
    assert stream.closed


def test_untrusted_source_title_cannot_inject_markdown_links() -> None:
    article = GeneratedArticle(
        title="A report", introduction="A useful introduction.",
        sections=[{"heading": "Context", "paragraphs": ["Supporting context."]}],
        conclusion="Read the sources.",
        research={"status": "sources_retrieved", "sources": [{
            "id": "S1", "title": "] (javascript:alert(1)) [malicious",
            "url": "https://news.example.com/post_(context)",
        }]},
    )
    markdown = article.to_markdown()
    assert "\\] \\(javascript:alert\\(1\\)\\) \\[malicious" in markdown
    assert "https://news.example.com/post_%28context%29" in markdown


@pytest.mark.parametrize("query,start,end", [
    ("Elon Musk latest tweet", "2026-09-13", "2026-10-14"),
    ("current gardening methods", "2026-09-13", "2026-10-14"),
    ("Recent earthquakes", "2026-09-13", "2026-10-14"),
    ("Today's reports", "2026-10-12", "2026-10-14"),
    ("आज की खबर", "2026-10-12", "2026-10-14"),
    ("Space discoveries this year", "2025-12-31", "2026-10-14"),
])
def test_relative_time_payload_and_context_preserve_actual_query(
    monkeypatch: pytest.MonkeyPatch, query: str, start: str, end: str,
) -> None:
    payloads = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return _response([_result()])

    _client(monkeypatch, handler)
    found = research.retrieve_sources(query)
    assert len(payloads) == 1 and payloads[0]["query"] == query
    assert payloads[0]["start_date"] == start and payloads[0]["end_date"] == end
    assert payloads[0]["filter_by_published_date"] is True
    assert payloads[0]["search_depth"] == "basic" and payloads[0]["auto_parameters"] is False
    assert "Query UTC date: 2026-10-13" in found.context
    assert "Requested publication/update window:" in found.context
    assert "The retrieval timestamp is not a publication date" in found.context
    assert found.summary.retrieved_at == "2026-10-13T08:30:00+00:00"


@pytest.mark.parametrize("query", [
    "Latest tweets from 2024", "Current technology in 1995", "Recent discoveries of 2020",
    "Latest posts on 2026-01-01", "Forecasts for 2030", "Urban gardening basics",
    "New York history",
])
def test_historical_dates_and_general_queries_are_not_limited_to_today(
    monkeypatch: pytest.MonkeyPatch, query: str,
) -> None:
    payloads = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return _response([_result(published_date="2024-05-01")])

    _client(monkeypatch, handler)
    found = research.retrieve_sources(query)
    assert len(payloads) == 1 and payloads[0]["query"] == query
    assert "start_date" not in payloads[0] and "end_date" not in payloads[0]
    assert "filter_by_published_date" not in payloads[0]
    assert found.summary.sources[0].published_at == "2024-05-01"


def test_configured_window_filters_stale_future_and_undated_sources_locally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return _response([
            _result(url="https://news.example.com/stale", published_date="2026-09-29"),
            _result(url="https://news.example.com/future", published_date="2026-10-14"),
            _result(url="https://news.example.com/undated", published_date=None),
            _result(url="https://news.example.com/boundary", published_date="2026-09-30"),
            _result(url="https://news.example.com/today", published_date="2026-10-13"),
        ])

    _client(monkeypatch, handler)
    monkeypatch.setattr(research.settings, "research_recent_days", 14)
    found = research.retrieve_sources("latest posts")
    assert payloads[0]["start_date"] == "2026-09-29"
    assert [s.url for s in found.summary.sources] == [
        "https://news.example.com/boundary", "https://news.example.com/today",
    ]
    assert "2026-09-30 through 2026-10-13" in found.context
    assert "stale" not in found.context and "future" not in found.context


@pytest.mark.parametrize("reported_date", [None, "bad date", "2026-09-13", "2026-10-14"])
def test_relative_query_without_date_evidence_fails_closed(
    monkeypatch: pytest.MonkeyPatch, reported_date: str | None,
) -> None:
    _client(monkeypatch, lambda _: _response([_result(published_date=reported_date)]))
    found = research.retrieve_sources("latest tweet")
    assert found.failure == "no_evidence" and found.summary.sources == []
    assert "2026-09-14 through 2026-10-13 (UTC)" in (found.failure_message or "")
    assert "Undated sources were excluded" in (found.failure_message or "")


@pytest.mark.parametrize("days", [0, 91])
def test_recent_window_setting_is_bounded(days: int) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, research_recent_days=days)
