"""Federated identity boundaries and nonce-bound Google verification."""

from unittest.mock import patch

import jwt
import pytest
from conftest import TEST_PASSWORD, auth_headers, generate_article, register_user
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import User
from app.services.google_auth import new_challenge


@pytest.fixture
def google_enabled(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "test-client.apps.googleusercontent.com")


def sign_in(
    client,
    *,
    email="google@example.com",
    subject="google-sub",
    nonce_override=None,
    path="/api/v1/auth/google",
    headers=None,
    password=None,
):
    challenge = client.get("/api/v1/auth/google/challenge").json()
    claims = {
        "sub": subject,
        "email": email,
        "email_verified": True,
        "name": "Google User",
        "nonce": nonce_override or challenge["nonce"],
    }
    body = {"credential": "fake-id-token"}
    if password is not None:
        body["password"] = password
    with patch(
        "app.services.google_auth.id_token.verify_oauth2_token", return_value=claims
    ) as verifier:
        result = client.post(path, json=body, headers=headers or {})
        assert verifier.call_args.args[2] == settings.google_client_id
    return result


def test_google_disabled(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "")
    assert client.get("/api/v1/auth/google/challenge").json() == {"enabled": False}
    assert client.post("/api/v1/auth/google", json={"credential": "test"}).status_code == 503


def test_google_creates_passwordless_session_and_returns_by_sub(client, google_enabled):
    first = sign_in(client)
    assert first.status_code == 200
    original = first.json()["user"]["id"]
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "google@example.com", "password": TEST_PASSWORD}
        ).status_code
        == 401
    )
    assert client.post("/api/v1/auth/refresh").status_code == 200
    second = sign_in(client, email="changed@example.com")
    assert second.status_code == 200
    assert second.json()["user"]["id"] == original


def test_google_never_merges_matching_password_email(client, google_enabled):
    existing = register_user(client, email="google@example.com")
    article = generate_article(client, existing["access_token"])
    result = sign_in(client)
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "GOOGLE_LINK_REQUIRED"
    other = sign_in(client, email="other@example.com", subject="other-sub")
    assert (
        client.get(
            f"/api/v1/articles/{article['id']}", headers=auth_headers(other.json()["access_token"])
        ).status_code
        == 404
    )


def test_explicit_link_requires_password_and_same_email(client, google_enabled):
    existing = register_user(client, email="google@example.com")
    headers = auth_headers(existing["access_token"])
    assert (
        sign_in(
            client, path="/api/v1/auth/google/link", headers=headers, password="wrong"
        ).status_code
        == 401
    )
    assert (
        sign_in(
            client,
            email="wrong@example.com",
            path="/api/v1/auth/google/link",
            headers=headers,
            password=TEST_PASSWORD,
        ).status_code
        == 401
    )
    linked = sign_in(
        client, path="/api/v1/auth/google/link", headers=headers, password=TEST_PASSWORD
    )
    assert linked.status_code == 200
    assert sign_in(client).json()["user"]["id"] == existing["user"]["id"]
    assert client.get("/api/v1/auth/connections", headers=headers).json() == {
        "google": True,
        "password": True,
    }


def test_nonce_mismatch_and_missing_challenge_rejected(client, google_enabled):
    assert sign_in(client, nonce_override="attacker").status_code == 401
    client.cookies.clear()
    with patch("app.services.google_auth.id_token.verify_oauth2_token") as verifier:
        assert client.post("/api/v1/auth/google", json={"credential": "test"}).status_code == 401
        verifier.assert_not_called()


def test_invalid_google_signature_rejected(client, google_enabled):
    client.get("/api/v1/auth/google/challenge")
    with patch(
        "app.services.google_auth.id_token.verify_oauth2_token", side_effect=ValueError("signature")
    ):
        assert client.post("/api/v1/auth/google", json={"credential": "test"}).status_code == 401


def test_unverified_email_rejected(client, google_enabled):
    challenge = client.get("/api/v1/auth/google/challenge").json()
    with patch(
        "app.services.google_auth.id_token.verify_oauth2_token",
        return_value={
            "sub": "new",
            "email": "new@example.com",
            "email_verified": False,
            "nonce": challenge["nonce"],
        },
    ):
        assert client.post("/api/v1/auth/google", json={"credential": "test"}).status_code == 401


def test_expired_and_tampered_challenges_rejected(client, google_enabled):
    _, signed = new_challenge()
    expired = jwt.encode(
        {"nonce": "old", "aud": "google-challenge", "exp": 1},
        settings.secret_key,
        algorithm="HS256",
    )
    for cookie in [expired, signed + "tampered"]:
        client.cookies.set("ss_google_challenge", cookie)
        with patch("app.services.google_auth.id_token.verify_oauth2_token") as verifier:
            assert (
                client.post("/api/v1/auth/google", json={"credential": "test"}).status_code == 401
            )
            verifier.assert_not_called()


def test_google_identity_cannot_be_moved_between_accounts(client, google_enabled):
    owner = sign_in(client).json()
    second = register_user(client, email="second@example.com")
    result = sign_in(
        client,
        path="/api/v1/auth/google/link",
        headers=auth_headers(second["access_token"]),
        password=TEST_PASSWORD,
    )
    assert result.status_code == 409
    assert sign_in(client).json()["user"]["id"] == owner["user"]["id"]


def test_disabled_google_account_cannot_sign_in(client, google_enabled, db_session):
    first = sign_in(client).json()
    user = db_session.get(User, first["user"]["id"])
    user.is_active = False
    db_session.commit()
    assert sign_in(client).status_code == 401
