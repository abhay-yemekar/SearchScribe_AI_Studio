"""Email provider contract and privacy boundaries, without sending real mail."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
import pytest

from app.services import transactional_mail as mail

CODE = "test_security_code_" + "A" * 40


@pytest.fixture(autouse=True)
def mail_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for field, value in {
        "public_site_url": "https://searchscribe.example",
        "mail_from_name": "SearchScribe AI",
        "mail_from_email": "support@example.com",
        "mail_provider": "brevo",
        "brevo_api_key": "fake-key-for-tests",
    }.items():
        monkeypatch.setattr(mail.settings, field, value)


@pytest.mark.parametrize("kind,path", [
    ("password_reset", "/reset-password"),
    ("email_verification", "/verify-email"),
])
def test_codes_are_in_text_but_never_in_clickable_links(kind: Any, path: str) -> None:
    rendered = mail.render_security_email(kind, "<script>alert(1)</script>", token=CODE)
    assert CODE in rendered.html and CODE in rendered.text
    assert "<script>" not in rendered.html
    assert "&lt;script&gt;" in rendered.html
    links = re.findall(r'href="([^"]+)"', rendered.html)
    assert "https://searchscribe.example" + path in links
    assert all(CODE not in link and "#token=" not in link for link in links)
    assert "Use this code only on SearchScribe." in rendered.text
    assert "expires in" in rendered.html
    assert "mailing list signup" in rendered.html


def test_password_change_notice_contains_no_security_code() -> None:
    rendered = mail.render_security_email("password_changed", "Abhay", token=CODE)
    assert CODE not in rendered.html and CODE not in rendered.text
    assert "Previous sessions have been signed out." in rendered.text
    assert "https://searchscribe.example/login" in rendered.text


@pytest.mark.parametrize("code", [None, "short", "x" * 513, "<script>" + "x" * 30])
def test_renderer_rejects_missing_or_malformed_codes(code: str | None) -> None:
    with pytest.raises(ValueError):
        mail.render_security_email("password_reset", "Name", token=code)


@pytest.mark.parametrize("origin", [
    "https://user:password@site.example", "https://site.example/subpath",
    "https://site.example?token=x", "https://site.example#token=x",
    "javascript:alert(1)",
])
def test_renderer_rejects_noncanonical_origins(
    origin: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mail.settings, "public_site_url", origin)
    with pytest.raises(mail.MailDeliveryError, match="unavailable"):
        mail.render_security_email("password_reset", "Name", token=CODE)


def intercept(monkeypatch: pytest.MonkeyPatch, handler: Any) -> dict[str, Any]:
    original_client = httpx.Client
    options: dict[str, Any] = {}

    def create_client(**kwargs: Any) -> httpx.Client:
        options.update(kwargs)
        return original_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(mail.httpx, "Client", create_client)
    return options


def test_provider_uses_https_and_approved_sender_with_plain_text_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[httpx.Request] = []

    def accept(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(201, json={"messageId": "not-inbox-proof"})

    options = intercept(monkeypatch, accept)
    mail.send_security_email("password_reset", "reader@example.com", "Reader", token=CODE)
    assert len(calls) == 1
    request = calls[0]
    assert str(request.url) == "https://api.brevo.com/v3/smtp/email"
    assert request.headers["api-key"] == "fake-key-for-tests"
    payload = json.loads(request.content)
    assert payload["sender"] == {"name": "SearchScribe AI", "email": "support@example.com"}
    assert payload["replyTo"] == payload["sender"]
    assert CODE in payload["htmlContent"] and CODE in payload["textContent"]
    assert options["follow_redirects"] is False
    assert options["trust_env"] is False
    assert options["timeout"].connect == 3
    assert options["timeout"].read <= 30


@pytest.mark.parametrize("status", [302, 400, 401, 429, 500])
def test_failed_or_redirected_delivery_is_opaque_and_not_retried(
    status: int, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[httpx.Request] = []

    def reject(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, text="recipient/token/api-key details must stay private")

    intercept(monkeypatch, reject)
    with pytest.raises(mail.MailDeliveryError) as failure:
        mail.send_security_email("password_reset", "reader@example.com", "Reader", token=CODE)
    assert len(calls) == 1
    assert str(failure.value) == "Email delivery could not be confirmed."


def test_ambiguous_timeout_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[httpx.Request] = []

    def timeout(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ReadTimeout("Unknown delivery outcome", request=request)

    intercept(monkeypatch, timeout)
    with pytest.raises(mail.MailDeliveryError, match="could not be confirmed"):
        mail.send_security_email("password_reset", "reader@example.com", "Reader", token=CODE)
    assert len(calls) == 1


def test_disabled_provider_does_not_open_network_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mail.settings, "mail_provider", "disabled")

    def unexpected(**kwargs: Any) -> httpx.Client:
        pytest.fail("Disabled email must never open a network client")

    monkeypatch.setattr(mail.httpx, "Client", unexpected)
    with pytest.raises(mail.MailDeliveryError, match="unavailable"):
        mail.send_security_email("password_reset", "reader@example.com", "Reader", token=CODE)
