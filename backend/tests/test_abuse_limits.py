"""Abuse limits: verified email for AI, signup cap, body size, field limits, saves,
and password hashing that can't exhaust memory (findings F11, F16, F17)."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest
from conftest import TEST_PASSWORD, auth_headers, generate_article, register_user
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import Settings, settings
from app.db.models import User


def _verify(db: Session, email: str, verified: bool = True) -> None:
    db.execute(update(User).where(User.email == email).values(email_verified=verified))
    db.commit()


# --- F11: a verified email (or Google account) before spending AI budget ---


@pytest.fixture
def verification_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_requires_verified_email", True)


def test_unverified_accounts_cannot_generate(
    client: TestClient,
    db_session: Session,
    verification_required: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.generation_service import GenerationService

    def must_not_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("generation ran for an unverified account")

    monkeypatch.setattr(GenerationService, "generate_article", must_not_run)
    token = register_user(client, email="unverified@example.com")["access_token"]

    response = client.post(
        "/api/v1/articles", json={"query": "Composting at home"}, headers=auth_headers(token)
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "EMAIL_VERIFICATION_REQUIRED"
    assert "account page" in response.json()["error"]["message"]


def test_unverified_accounts_cannot_rewrite(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = register_user(client, email="rewrite@example.com")["access_token"]
    article = generate_article(client, token)  # Allowed while the gate is off.
    monkeypatch.setattr(settings, "ai_requires_verified_email", True)

    response = client.post(
        f"/api/v1/articles/{article['id']}/rewrite",
        json={"style": "casual"},
        headers=auth_headers(token),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "EMAIL_VERIFICATION_REQUIRED"


def test_verified_accounts_generate(
    client: TestClient, db_session: Session, verification_required: None
) -> None:
    token = register_user(client, email="verified@example.com")["access_token"]
    _verify(db_session, "verified@example.com")

    assert generate_article(client, token)["id"] > 0


@pytest.mark.parametrize(("app_env", "required"), [("production", True), ("local", False)])
def test_verification_is_required_by_default_only_in_production(
    app_env: str, required: bool
) -> None:
    production = {
        "app_env": app_env,
        "secret_key": "s" * 48,
        "database_url": "postgresql+psycopg://u:p@db.example.com/app",
        "cors_origins": "https://app.example.com",
        "ai_provider": "gemini",
        "gemini_api_key": "fixture-key",
    }
    loaded = Settings(**(production if app_env == "production" else {"app_env": app_env}))

    assert loaded.ai_requires_verified_email is required


# --- F11: new accounts per network per day ---


def test_signups_are_capped_per_client_ip_per_day(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "signups_per_ip_per_day", 2)
    register_user(client, email="one@example.com")
    register_user(client, email="two@example.com")

    third = client.post(
        "/api/v1/auth/signup",
        json={"email": "three@example.com", "name": "Third", "password": TEST_PASSWORD},
    )

    assert third.status_code == 429
    assert third.json()["error"]["code"] == "RATE_LIMITED"
    assert third.json()["error"]["details"]["retry_after_seconds"] > 0


# --- F16: request body size ---


def test_oversized_bodies_are_rejected_before_parsing(client: TestClient) -> None:
    big = {"email": "big@example.com", "password": "x" * 300_000}

    response = client.post("/api/v1/auth/login", json=big)

    assert response.status_code == 413
    error = response.json()["error"]
    assert error["code"] == "PAYLOAD_TOO_LARGE"
    assert response.headers["X-Request-ID"] == error["request_id"]


def test_oversized_bodies_without_a_length_header_are_rejected(client: TestClient) -> None:
    def chunks() -> Iterator[bytes]:
        yield b'{"email": "stream@example.com", "password": "'
        for _ in range(40):
            yield b"x" * 10_000
        yield b'"}'

    response = client.post(
        "/api/v1/auth/login", content=chunks(), headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_normal_bodies_still_work(client: TestClient) -> None:
    token = register_user(client, email="normal@example.com")["access_token"]
    article = generate_article(client, token)

    assert article["current_version"] == 1


# --- F16: per-field limits on saved content ---


def _save_body(article: dict[str, Any], **content_changes: Any) -> dict[str, Any]:
    content = {**article["content"], **content_changes}
    content.pop("photos", None)
    return {
        "base_version": article["current_version"],
        "content": content,
        "seo": {**article["seo"], "keywords": article["seo"]["keywords"]},
    }


@pytest.mark.parametrize(
    "change",
    [
        {"introduction": "a" * 5_001},
        {"conclusion": "a" * 5_001},
        {"sections": [{"heading": "One", "paragraphs": ["p"] * 31, "bullets": []}]},
        {"sections": [{"heading": "One", "paragraphs": ["a" * 5_001], "bullets": []}]},
        {"sections": [{"heading": "One", "paragraphs": [], "bullets": ["b"] * 51}]},
        {"sections": [{"heading": "One", "paragraphs": [], "bullets": ["a" * 1_001]}]},
    ],
    ids=[
        "intro",
        "conclusion",
        "paragraph-count",
        "paragraph-length",
        "bullet-count",
        "bullet-length",
    ],
)
def test_saved_content_fields_have_limits(client: TestClient, change: dict[str, Any]) -> None:
    token = register_user(client, email="fields@example.com")["access_token"]
    article = generate_article(client, token)

    response = client.put(
        f"/api/v1/articles/{article['id']}/content",
        json=_save_body(article, **change),
        headers=auth_headers(token),
    )

    assert response.status_code == 422


def test_seo_keywords_have_a_length_limit(client: TestClient) -> None:
    token = register_user(client, email="keywords@example.com")["access_token"]
    article = generate_article(client, token)
    body = _save_body(article)
    body["seo"]["keywords"] = ["k" * 81]

    response = client.put(
        f"/api/v1/articles/{article['id']}/content", json=body, headers=auth_headers(token)
    )

    assert response.status_code == 422


# --- F16: saves are rate limited per account ---


def test_saves_are_rate_limited_per_account(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.v1 import articles

    monkeypatch.setattr(articles.settings, "rate_limit_saves_per_minute", 2)
    token = register_user(client, email="saves@example.com")["access_token"]
    article = generate_article(client, token)
    headers = auth_headers(token)
    rename = f"/api/v1/articles/{article['id']}"

    statuses = [
        client.patch(rename, json={"title": f"Title {n}"}, headers=headers).status_code
        for n in range(3)
    ]

    assert statuses == [200, 200, 429]


# --- F17: password hashing ---


def test_argon2_uses_settings_sized_for_a_small_server() -> None:
    hashed = security.hash_password("correct-horse-battery")

    assert "m=19456,t=2,p=1" in hashed
    assert security.verify_password("correct-horse-battery", hashed)


def test_at_most_two_hashes_run_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    running = 0
    peak = 0
    lock = threading.Lock()

    class SlowHasher:
        def hash(self, password: str) -> str:
            nonlocal running, peak
            with lock:
                running += 1
                peak = max(peak, running)
            time.sleep(0.05)
            with lock:
                running -= 1
            return "hashed"

    monkeypatch.setattr(security, "_hasher", SlowHasher())
    threads = [threading.Thread(target=security.hash_password, args=("pw",)) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert peak == 2


def test_a_busy_hasher_answers_503_instead_of_queueing_forever(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.exceptions import ServiceUnavailableError

    monkeypatch.setattr(security, "HASH_SLOT_TIMEOUT_SECONDS", 0.05)
    held = [security._hash_slots.acquire(), security._hash_slots.acquire()]
    try:
        with pytest.raises(ServiceUnavailableError) as raised:
            security.hash_password("pw")
    finally:
        for _ in held:
            security._hash_slots.release()

    assert raised.value.code == "SERVER_BUSY"


def _count_hashes(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    real = security.hash_password

    def counting(password: str) -> str:
        calls.append(password)
        return real(password)

    for module in ("app.services.account_passwords", "app.services.account_recovery"):
        monkeypatch.setattr(f"{module}.hash_password", counting)
    return calls


def test_a_wrong_current_password_is_rejected_before_any_hashing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = register_user(client, email="change@example.com")["access_token"]
    calls = _count_hashes(monkeypatch)

    response = client.post(
        "/api/v1/auth/password/change",
        json={"current_password": "not-the-password-1", "password": "a-brand-new-password-2"},
        headers=auth_headers(token),
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "PASSWORD_CURRENT_INVALID"
    assert calls == []


def test_a_bad_reset_token_is_rejected_before_any_hashing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _count_hashes(monkeypatch)

    response = client.post(
        "/api/v1/auth/password/reset",
        json={"token": "x" * 43, "password": "a-brand-new-password-2"},
    )

    assert response.status_code == 400
    assert calls == []


def test_signing_in_upgrades_an_old_expensive_hash(client: TestClient, db_session: Session) -> None:
    from argon2 import PasswordHasher

    register_user(client, email="legacy@example.com")
    legacy = PasswordHasher().hash(TEST_PASSWORD)  # 64 MiB, t=3, p=4
    db_session.execute(
        update(User).where(User.email == "legacy@example.com").values(password_hash=legacy)
    )
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login", json={"email": "legacy@example.com", "password": TEST_PASSWORD}
    )

    assert response.status_code == 200
    db_session.expire_all()
    stored = db_session.scalar(select(User.password_hash).where(User.email == "legacy@example.com"))
    assert stored is not None and "m=19456,t=2,p=1" in stored


# --- Mail budget default (Resend's free tier is 100 a day) ---


def test_the_daily_mail_budget_defaults_below_the_free_tier() -> None:
    assert Settings.model_fields["mail_daily_limit"].default == 90
