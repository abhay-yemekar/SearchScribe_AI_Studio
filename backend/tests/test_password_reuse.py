"""A new password must differ from the current one; a rejected reset keeps its link."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from conftest import TEST_PASSWORD, auth_headers, register_user
from fastapi.testclient import TestClient

from app.core.config import settings

CHANGE = "/api/v1/auth/password/change"
FORGOT = "/api/v1/auth/password/forgot"
RESET = "/api/v1/auth/password/reset"
NEW_PASSWORD = "new-correct-horse-2"


@pytest.fixture
def security_mail(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    monkeypatch.setattr(settings, "mail_provider", "brevo")
    monkeypatch.setattr(settings, "security_email_requests_per_hour", 10)
    monkeypatch.setattr(settings, "security_ip_requests_per_hour", 100)
    with patch("app.services.account_recovery.send_security_email") as sender:
        yield sender


def _reset_code(client: TestClient, sender: MagicMock) -> str:
    assert client.post(FORGOT, json={"email": "user@example.com"}).status_code == 202
    return next(
        call.kwargs["token"]
        for call in reversed(sender.call_args_list)
        if call.args[0] == "password_reset"
    )


def _still_signed_in(client: TestClient, session: dict[str, Any]) -> bool:
    me = client.get("/api/v1/auth/me", headers=auth_headers(session["access_token"]))
    return me.status_code == 200


def test_changing_to_the_current_password_is_rejected(client: TestClient) -> None:
    session = register_user(client)

    response = client.post(
        CHANGE,
        json={"current_password": TEST_PASSWORD, "password": TEST_PASSWORD},
        headers=auth_headers(session["access_token"]),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PASSWORD_REUSED"
    # Nothing changed: no sign-out, and the old password still works.
    assert _still_signed_in(client, session)
    login = client.post(
        "/api/v1/auth/login", json={"email": "user@example.com", "password": TEST_PASSWORD}
    )
    assert login.status_code == 200


def test_resetting_to_the_current_password_keeps_the_link_usable(
    client: TestClient, security_mail: MagicMock
) -> None:
    session = register_user(client)
    code = _reset_code(client, security_mail)

    reused = client.post(RESET, json={"token": code, "password": TEST_PASSWORD})

    assert reused.status_code == 422
    assert reused.json()["error"]["code"] == "PASSWORD_REUSED"
    assert _still_signed_in(client, session)  # The reset did not happen.
    # The same link still works with a different password.
    retried = client.post(RESET, json={"token": code, "password": NEW_PASSWORD})
    assert retried.status_code == 200
    assert not _still_signed_in(client, session)
