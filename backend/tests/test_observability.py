"""Unhandled errors stay traceable, and the API reports what code it runs."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator

import pytest
from conftest import auth_headers, register_user
from fastapi.testclient import TestClient

from app.core.logging import JsonFormatter
from app.main import app
from app.services.article_service import ArticleService


class _Lines(logging.Handler):
    """Formats records as they happen, while the request ID is still set."""

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self.setFormatter(JsonFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


@pytest.fixture
def log_lines(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    # In-process Alembic tests call fileConfig(), which disables existing loggers and
    # sets the root level to WARNING; production runs migrations in a subprocess.
    http = logging.getLogger("http")
    monkeypatch.setattr(http, "disabled", False)
    previous = http.level
    http.setLevel(logging.INFO)
    handler = _Lines()
    root = logging.getLogger()
    root.addHandler(handler)
    yield handler.lines
    root.removeHandler(handler)
    http.setLevel(previous)


def _boom(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("database exploded: secret detail")


def test_unhandled_error_keeps_its_request_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, log_lines: list[str]
) -> None:
    headers = auth_headers(register_user(client, email="boom@example.com")["access_token"])
    monkeypatch.setattr(ArticleService, "list_articles", _boom)
    # Report the response the browser would get instead of re-raising into the test.
    raw = TestClient(app, raise_server_exceptions=False)

    response = raw.get("/api/v1/articles", headers=headers)

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "INTERNAL_ERROR"
    assert "secret detail" not in response.text
    assert re.fullmatch(r"[0-9a-f]{12}", error["request_id"])
    assert response.headers["X-Request-ID"] == error["request_id"]
    # The 500 passes back through the outer middleware like any other response.
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"
    logged = [line for line in log_lines if "unhandled.exception" in line]
    assert logged and f'"request_id": "{error["request_id"]}"' in logged[0]
    assert any(
        '"status": 500' in line and error["request_id"] in line
        for line in log_lines
        if "http.request" in line
    )


def test_version_reports_code_and_database_revisions(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from app.core.config import settings

    monkeypatch.setattr(settings, "git_sha", "abc1234def")
    expected_head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()

    body = client.get("/api/v1/version").json()

    assert body["git_sha"] == "abc1234def"
    assert body["alembic_head"] == expected_head
    # Tests build the schema with create_all, so no revision is recorded.
    assert body["alembic_revision"] is None
    assert body["environment"] == "test"


def test_version_defaults_when_the_host_gives_no_commit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "git_sha", "")

    assert client.get("/api/v1/version").json()["git_sha"] == "unknown"


def test_sentry_stays_off_without_a_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    import sentry_sdk

    from app.core import observability
    from app.core.config import settings

    monkeypatch.setattr(settings, "sentry_dsn", "")
    calls: list[object] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(sentry_sdk, "capture_exception", calls.append)

    assert observability.init_sentry() is False
    observability.report_exception(RuntimeError("x"))
    assert calls == []


def test_sentry_sends_errors_only_and_no_personal_data(monkeypatch: pytest.MonkeyPatch) -> None:
    import sentry_sdk

    from app.core import observability
    from app.core.config import settings

    monkeypatch.setattr(settings, "sentry_dsn", "https://key@o0.ingest.sentry.io/0")
    monkeypatch.setattr(settings, "git_sha", "abc1234")
    options: dict[str, object] = {}
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: options.update(kwargs))

    assert observability.init_sentry() is True
    assert options["send_default_pii"] is False
    assert options["traces_sample_rate"] == 0.0
    assert options["max_request_body_size"] == "never"
    assert options["include_local_variables"] is False
    assert options["release"] == "abc1234"
    assert options["environment"] == "test"


def test_a_crash_reaches_sentry_tagged_with_its_request_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sentry_sdk

    from app.core.config import settings

    headers = auth_headers(register_user(client, email="sentry@example.com")["access_token"])
    monkeypatch.setattr(ArticleService, "list_articles", _boom)
    monkeypatch.setattr(settings, "sentry_dsn", "https://key@o0.ingest.sentry.io/0")
    captured: list[BaseException] = []
    tags: dict[str, str] = {}
    monkeypatch.setattr(sentry_sdk, "capture_exception", captured.append)

    class Scope:
        def set_tag(self, key: str, value: str) -> None:
            tags[key] = value

    monkeypatch.setattr(sentry_sdk, "get_isolation_scope", Scope)

    response = TestClient(app, raise_server_exceptions=False).get(
        "/api/v1/articles", headers=headers
    )

    assert response.status_code == 500
    assert len(captured) == 1 and isinstance(captured[0], RuntimeError)
    assert tags["request_id"] == response.headers["X-Request-ID"]


def test_the_real_sdk_sends_one_event_without_credentials(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sentry_sdk
    from sentry_sdk.envelope import Envelope
    from sentry_sdk.transport import Transport

    from app.core import observability
    from app.core.config import settings

    class Capture(Transport):
        """Keeps events in memory instead of sending them."""

        def __init__(self) -> None:
            super().__init__()
            self.events: list[dict[str, object]] = []

        def capture_envelope(self, envelope: Envelope) -> None:
            if (event := envelope.get_event()) is not None:
                self.events.append(event)

    token = register_user(client, email="real-sentry@example.com")["access_token"]
    monkeypatch.setattr(ArticleService, "list_articles", _boom)
    monkeypatch.setattr(settings, "sentry_dsn", "https://key@o0.ingest.sentry.io/0")
    transport = Capture()
    real_init = sentry_sdk.init
    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: real_init(transport=transport, **kw))
    try:
        assert observability.init_sentry() is True
        response = TestClient(app, raise_server_exceptions=False).get(
            "/api/v1/articles",
            headers={**auth_headers(token), "Cookie": "refresh_token=secret-cookie-value"},
        )
        sentry_sdk.flush()
    finally:
        real_init()  # An inactive client again for the rest of the suite.

    assert response.status_code == 500
    # The FastAPI integration must not report the same crash a second time.
    assert len(transport.events) == 1
    event = transport.events[0]
    assert event["tags"]["request_id"] == response.headers["X-Request-ID"]  # type: ignore[index]
    sent = json.dumps(event)
    assert "RuntimeError" in sent
    # Booleans, not `in` asserts: on failure pytest would diff a huge event.
    # Frame locals once carried the raw ASGI headers here, token and cookie included.
    token_sent, cookie_sent = token in sent, "secret-cookie-value" in sent
    assert not token_sent
    assert not cookie_sent


TEST_TOKEN = "t" * 40
SENTRY_TEST = "/api/v1/debug/sentry-test"


@pytest.mark.parametrize(
    ("configured", "sent"),
    [
        ("", ""),  # Off by default.
        ("", "anything"),
        (TEST_TOKEN, ""),
        (TEST_TOKEN, "t" * 39),
        ("short-token", "short-token"),  # Too short to count as configured.
    ],
)
def test_sentry_test_route_looks_like_an_unknown_path_without_its_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, configured: str, sent: str
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "sentry_test_token", configured)
    unknown = client.post("/api/v1/no-such-path")

    response = client.post(SENTRY_TEST, headers={"X-Sentry-Test-Token": sent})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == unknown.json()["error"]["code"]
    assert response.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_sentry_test_route_crashes_and_reports_with_the_right_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import middleware
    from app.core.config import settings

    monkeypatch.setattr(settings, "sentry_test_token", TEST_TOKEN)
    reported: list[BaseException] = []
    monkeypatch.setattr(middleware, "report_exception", reported.append)

    response = TestClient(app, raise_server_exceptions=False).post(
        SENTRY_TEST, headers={"X-Sentry-Test-Token": TEST_TOKEN}
    )

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "INTERNAL_ERROR"
    assert error["request_id"] == response.headers["X-Request-ID"]
    assert len(reported) == 1 and "Deliberate Sentry test" in str(reported[0])


def test_sentry_test_route_is_not_in_the_public_schema(client: TestClient) -> None:
    assert SENTRY_TEST.removeprefix("/api/v1") not in str(app.openapi()["paths"])
