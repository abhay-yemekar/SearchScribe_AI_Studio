"""Authentication flows: signup, login, refresh rotation, logout, /me."""

from __future__ import annotations

from conftest import TEST_PASSWORD, register_user
from fastapi.testclient import TestClient


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_signup_creates_user_and_sets_refresh_cookie(client: TestClient) -> None:
    payload = register_user(client, email="new@example.com", name="New User")

    assert payload["user"]["email"] == "new@example.com"
    assert payload["user"]["name"] == "New User"
    assert payload["access_token"]
    assert payload["token_type"] == "bearer"
    assert any(c.name == "ss_refresh_token" for c in client.cookies.jar)


def test_signup_duplicate_email_conflicts(client: TestClient) -> None:
    register_user(client, email="dup@example.com")
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "dup@example.com", "name": "Second", "password": TEST_PASSWORD},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


def test_signup_rejects_weak_password(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "weak@example.com", "name": "Weak", "password": "short"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_login_success_and_failure(client: TestClient) -> None:
    register_user(client, email="login@example.com")

    ok = client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": TEST_PASSWORD},
    )
    assert ok.status_code == 200
    assert ok.json()["access_token"]

    bad = client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "wrong-password-9"},
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_login_normalizes_email_case(client: TestClient) -> None:
    register_user(client, email="case@example.com")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "  CASE@example.COM ", "password": TEST_PASSWORD},
    )
    assert response.status_code == 200


def test_me_requires_token(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401

    garbage = client.get(
        "/api/v1/auth/me", headers=auth_headers("not-a-jwt")
    )
    assert garbage.status_code == 401


def test_me_returns_current_user(client: TestClient) -> None:
    tokens = register_user(client, email="me@example.com", name="Me Myself")
    response = client.get("/api/v1/auth/me", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"
    assert response.json()["name"] == "Me Myself"


def test_refresh_rotates_cookie_and_revokes_old_token(client: TestClient) -> None:
    register_user(client, email="refresh@example.com")
    old_cookie = client.cookies.get("ss_refresh_token")

    first = client.post("/api/v1/auth/refresh")
    assert first.status_code == 200
    new_cookie = client.cookies.get("ss_refresh_token")
    assert new_cookie and new_cookie != old_cookie

    # Replaying the consumed token must fail and, because it looks like theft,
    # revoke every session for the user (including the fresh one).
    replay = client.post(
        "/api/v1/auth/refresh", cookies={"ss_refresh_token": old_cookie}
    )
    assert replay.status_code == 401


def test_logout_revokes_session(client: TestClient) -> None:
    register_user(client, email="bye@example.com")

    assert client.post("/api/v1/auth/logout").status_code == 200

    refreshed = client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 401


def test_auth_rate_limit_blocks_brute_force(client: TestClient) -> None:
    register_user(client, email="brute@example.com")
    client.cookies.clear()

    statuses = []
    for _ in range(12):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "brute@example.com", "password": "wrong-password-9"},
        )
        statuses.append(response.status_code)

    assert 429 in statuses
    assert statuses[-1] == 429
