"""Rate limits are per client, account or session, never one bucket shared by all users."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from itertools import count

import pytest
from conftest import TEST_PASSWORD, auth_headers, register_user
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core import rate_limit
from app.core.config import Settings, settings
from app.core.rate_limit import (
    CLIENT_IP_HEADER,
    PROXY_SECRET_HEADER,
    SlidingWindowLimiter,
    limiter,
)
from app.db.base import utc_now

LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
SECRET = "proxy-secret-for-tests-only-0123456789"
_emails = count()


@pytest.fixture
def proxy_secret(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch.setattr(settings, "proxy_shared_secret", SECRET)
    yield SECRET


def via_proxy(ip: str, secret: str = SECRET) -> dict[str, str]:
    """Headers frontend/proxy.ts adds for a visitor at ``ip``."""
    return {CLIENT_IP_HEADER: ip, PROXY_SECRET_HEADER: secret}


def wrong_login(client: TestClient, headers: dict[str, str] | None = None) -> int:
    # A fresh address each time, so only the per-client limit can trigger.
    email = f"nobody-{next(_emails)}@example.com"
    payload = {"email": email, "password": "wrong-password-9"}
    return client.post(LOGIN, json=payload, headers=headers or {}).status_code


def login(client: TestClient, email: str, password: str, ip: str | None = None) -> int:
    payload = {"email": email, "password": password}
    return client.post(LOGIN, json=payload, headers=via_proxy(ip) if ip else {}).status_code


def refresh_with(client: TestClient, cookie: str) -> int:
    return client.post(REFRESH, headers={"Cookie": f"ss_refresh_token={cookie}"}).status_code


# --- Trusted client IP -----------------------------------------------------


def test_clients_behind_the_proxy_get_separate_login_buckets(
    client: TestClient, proxy_secret: str
) -> None:
    register_user(client, email="second@example.com")
    client.cookies.clear()
    first = via_proxy("203.0.113.1")

    statuses = [wrong_login(client, first) for _ in range(11)]

    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429
    assert login(client, "second@example.com", TEST_PASSWORD, ip="203.0.113.2") == 200


@pytest.mark.parametrize(
    "spoof",
    [
        lambda n: {CLIENT_IP_HEADER: f"198.51.100.{n}"},
        lambda n: via_proxy(f"198.51.100.{n}", secret="wrong-secret-of-a-similar-length-000"),
        lambda n: {"x-forwarded-for": f"198.51.100.{n}", "x-real-ip": f"198.51.100.{n}"},
    ],
    ids=["no-secret", "wrong-secret", "forwarded-for"],
)
def test_spoofed_client_ip_shares_the_peer_bucket(
    client: TestClient, proxy_secret: str, spoof
) -> None:
    statuses = [wrong_login(client, spoof(n)) for n in range(11)]

    assert statuses[-1] == 429


def test_client_ip_header_is_ignored_when_no_secret_is_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "proxy_shared_secret", "")

    statuses = [wrong_login(client, via_proxy(f"198.51.100.{n}", secret="")) for n in range(11)]

    assert statuses[-1] == 429


class _Request:
    def __init__(self, headers: dict[str, str], peer: str = "10.0.0.9") -> None:
        self.headers = headers
        self.client = type("Peer", (), {"host": peer})()


@pytest.mark.parametrize(
    ("claimed", "expected"),
    [
        ("203.0.113.9", "203.0.113.9"),
        (" 2001:DB8::1 ", "2001:db8::1"),
        ("not-an-ip", "10.0.0.9"),
        ("203.0.113.9, 198.51.100.1", "10.0.0.9"),
        ("", "10.0.0.9"),
    ],
)
def test_client_ip_accepts_only_one_valid_address(
    proxy_secret: str, claimed: str, expected: str
) -> None:
    request = _Request(via_proxy(claimed))

    assert rate_limit.client_ip(request) == expected  # type: ignore[arg-type]


def test_proxy_secret_must_be_long_and_distinct() -> None:
    with pytest.raises(ValidationError, match="PROXY_SHARED_SECRET"):
        Settings(_env_file=None, proxy_shared_secret="too-short")
    key = "test-only-key-with-at-least-32-characters"
    with pytest.raises(ValidationError, match="must differ from SECRET_KEY"):
        Settings(
            _env_file=None, app_env="production", secret_key=key, proxy_shared_secret=key,
            database_url="postgresql://test:test@localhost/searchscribe_test",
            ai_provider="gemini",
        )


# --- Refresh has its own buckets -------------------------------------------


def test_refresh_does_not_spend_the_login_bucket(client: TestClient) -> None:
    register_user(client, email="tabs@example.com")  # signup spends 1 of 10

    for _ in range(12):
        assert client.post(REFRESH).status_code == 200  # rotates the cookie each time
    client.cookies.clear()
    for _ in range(12):
        assert client.post(REFRESH).status_code == 401  # cookieless page loads

    assert login(client, "tabs@example.com", TEST_PASSWORD) == 200  # same client


def test_exhausted_login_bucket_does_not_block_refresh(client: TestClient) -> None:
    register_user(client, email="busy@example.com")  # keeps its refresh cookie
    assert [wrong_login(client) for _ in range(10)][-1] == 429

    assert client.post(REFRESH).status_code == 200


def test_refresh_session_bucket_is_keyed_by_cookie(client: TestClient) -> None:
    statuses = [refresh_with(client, "replayed") for _ in range(31)]

    assert statuses[:30] == [401] * 30
    assert statuses[30] == 429
    assert refresh_with(client, "another") == 401


def test_random_refresh_cookies_hit_the_per_client_ceiling(client: TestClient) -> None:
    statuses = [refresh_with(client, f"guess-{n}") for n in range(121)]

    assert statuses[:120] == [401] * 120
    assert statuses[120] == 429


# --- Authenticated routes are per account ----------------------------------


def test_generation_limit_is_per_account_not_per_client(client: TestClient) -> None:
    first = auth_headers(register_user(client, email="writer-a@example.com")["access_token"])
    second = auth_headers(register_user(client, email="writer-b@example.com")["access_token"])

    def generate(headers: dict[str, str]) -> int:
        return client.post(
            "/api/v1/articles", json={"query": "Shared office network"}, headers=headers
        ).status_code

    assert [generate(first) for _ in range(6)] == [201] * 5 + [429]
    assert generate(second) == 201


# --- Persistent per-email sign-in budget ------------------------------------


@pytest.fixture
def three_attempts(monkeypatch: pytest.MonkeyPatch, proxy_secret: str) -> None:
    monkeypatch.setattr(settings, "login_attempts_per_email", 3)


def test_login_attempts_are_limited_per_email_across_clients(
    client: TestClient, three_attempts: None
) -> None:
    register_user(client, email="target@example.com")
    register_user(client, email="bystander@example.com")
    client.cookies.clear()

    statuses = [login(client, "target@example.com", "wrong-password-9", f"192.0.2.{n}")
                for n in range(3)]
    throttled = client.post(
        LOGIN, json={"email": " Target@Example.com ", "password": TEST_PASSWORD},
        headers=via_proxy("192.0.2.200"),
    )

    assert statuses == [401, 401, 401]
    assert throttled.status_code == 429
    assert throttled.json()["error"]["code"] == "RATE_LIMITED"
    assert "sign-in attempts" in throttled.json()["error"]["message"]
    assert 0 < throttled.json()["error"]["details"]["retry_after_seconds"] <= 15 * 60 + 1
    assert login(client, "bystander@example.com", TEST_PASSWORD, "192.0.2.201") == 200


def test_unknown_email_is_throttled_like_a_real_one(
    client: TestClient, three_attempts: None
) -> None:
    statuses = [login(client, "ghost@example.com", "wrong-password-9", f"192.0.2.{n}")
                for n in range(4)]

    assert statuses == [401, 401, 401, 429]


def test_login_budget_survives_limiter_reset_and_expires_with_window(
    client: TestClient, three_attempts: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    register_user(client, email="steady@example.com")
    client.cookies.clear()
    for n in range(3):
        login(client, "steady@example.com", "wrong-password-9", f"192.0.2.{n}")

    limiter.reset()  # A process restart does not reset the persistent budget.
    assert login(client, "steady@example.com", TEST_PASSWORD, "192.0.2.100") == 429

    later = utc_now() + timedelta(minutes=16)
    monkeypatch.setattr("app.services.auth_service.utc_now", lambda: later)
    assert login(client, "steady@example.com", TEST_PASSWORD, "192.0.2.101") == 200


def test_successful_login_resets_the_email_budget(
    client: TestClient, three_attempts: None
) -> None:
    register_user(client, email="typo@example.com")
    client.cookies.clear()
    for n in range(2):
        assert login(client, "typo@example.com", "wrong-password-9", f"192.0.2.{n}") == 401
    assert login(client, "typo@example.com", TEST_PASSWORD, "192.0.2.100") == 200

    statuses = [login(client, "typo@example.com", "wrong-password-9", f"192.0.2.{n}")
                for n in range(10, 14)]

    assert statuses == [401, 401, 401, 429]


# --- Limiter memory ----------------------------------------------------------


def test_limiter_drops_idle_keys() -> None:
    fresh = SlidingWindowLimiter(clock=iter([0.0, 0.0, 61.0]).__next__)

    assert fresh.allow("refresh:session:a", 1)
    assert fresh.allow("refresh:session:b", 1)
    assert fresh.allow("refresh:session:c", 1)

    assert set(fresh._hits) == {"refresh:session:c"}
