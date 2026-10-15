"""Email provider contract and privacy boundaries, without sending real mail."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

import httpx
import pytest

from app.core.config import Settings
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
        "resend_api_key": "fake-resend-key-for-tests",
        "mail_reply_to_email": "",
        "security_email_links_enabled": False,
        "password_reset_expire_minutes": 30,
        "email_verification_expire_hours": 24,
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


class ParsedEmail(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []
        self.attributes: list[tuple[str, str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.attributes.extend((tag, key, value) for key, value in attrs if value is not None)

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def test_security_email_links_default_to_disabled() -> None:
    assert Settings.model_fields["security_email_links_enabled"].default is False


@pytest.mark.parametrize("enabled", [False, True])
def test_renderer_normalizes_optional_origin_slash(
    enabled: bool, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mail.settings, "public_site_url", "https://searchscribe.example/")
    monkeypatch.setattr(mail.settings, "security_email_links_enabled", enabled)
    rendered = mail.render_security_email("email_verification", "Reader", token=CODE)
    destination = "https://searchscribe.example/verify-email" + (
        "#token=" + CODE if enabled else ""
    )
    assert f'href="{destination}"' in rendered.html
    assert destination in rendered.text
    assert "https://searchscribe.example//" not in rendered.html


@pytest.mark.parametrize("kind,path,expiry", [
    ("password_reset", "/reset-password", "30 minutes"),
    ("email_verification", "/verify-email", "24 hours"),
])
def test_enabled_links_are_fragment_only_and_do_not_display_codes(
    kind: Any, path: str, expiry: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mail.settings, "security_email_links_enabled", True)
    rendered = mail.render_security_email(kind, "Reader", token=CODE)
    parser = ParsedEmail()
    parser.feed(rendered.html)
    page = "https://searchscribe.example" + path
    destination = page + "#token=" + CODE
    secret_attributes = [
        (tag, key, value) for tag, key, value in parser.attributes if CODE in value
    ]
    assert secret_attributes == [("a", "href", destination), ("a", "href", destination)]
    for _, attribute, value in parser.attributes:
        if attribute in {"href", "src"}:
            url = urlsplit(value)
            assert url.scheme == "https" and url.netloc == "searchscribe.example"
            assert not url.query
            assert not url.fragment or value == destination
    visible_text = " ".join(parser.text)
    assert CODE not in visible_text and "YOUR RESET CODE" not in visible_text
    assert "YOUR VERIFICATION CODE" not in visible_text
    assert "This link expires in " + expiry in visible_text
    assert "Use it once, only on SearchScribe." in visible_text
    assert page in visible_text
    assert rendered.text.count(CODE) == 1
    assert destination in rendered.text
    assert "This link expires in " + expiry in rendered.text
    assert "Use this link once, only on SearchScribe." in rendered.text
    assert "paste" not in rendered.text.lower()
    assert CODE not in rendered.subject


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("kind", ["password_changed", "password_added"])
def test_password_change_notice_contains_no_security_code(
    enabled: bool, kind: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mail.settings, "security_email_links_enabled", enabled)
    rendered = mail.render_security_email(kind, "Abhay", token=CODE)
    assert CODE not in rendered.html and CODE not in rendered.text
    assert "Previous sessions have been signed out." in rendered.text
    assert "https://searchscribe.example/login" in rendered.text
    if kind == "password_added":
        assert "A password was just added" in rendered.text
        assert "continue using your linked Google account" in rendered.text
        assert "was changed" not in rendered.subject


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("code", [
    None, "short", "x" * 201, "x" * 513, "<script>" + "x" * 30,
    CODE + "#token=other", CODE + "&redirect=other", CODE + "%2Fother",
    CODE + "?token=other", CODE + "/other",
])
def test_renderer_rejects_missing_or_malformed_codes(
    code: str | None, enabled: bool, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mail.settings, "security_email_links_enabled", enabled)
    with pytest.raises(ValueError):
        mail.render_security_email("password_reset", "Name", token=code)


@pytest.mark.parametrize("origin", [
    "https://user:password@site.example", "https://site.example/subpath",
    "https://site.example?token=x", "https://site.example#token=x",
    "javascript:alert(1)", "https://@site.example", "https://site.example:wrong",
    "https://site.example/path/", "https://site.example//", "http://site.example",
    "https://site.example\n", "https://[malformed",
    "https://site.example?", "https://site.example#", "https://site.example\\suffix",
])
@pytest.mark.parametrize("enabled", [False, True])
def test_renderer_rejects_noncanonical_origins(
    origin: str, enabled: bool, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mail.settings, "security_email_links_enabled", enabled)
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


@pytest.mark.parametrize("kind", [
    "password_reset", "email_verification", "password_changed", "password_added",
])
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("provider", ["brevo", "resend"])
def test_provider_uses_https_and_approved_sender_with_plain_text_fallback(
    kind: Any, enabled: bool, provider: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mail.settings, "mail_provider", provider)
    monkeypatch.setattr(mail.settings, "security_email_links_enabled", enabled)
    calls: list[httpx.Request] = []

    def accept(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200 if provider == "resend" else 201,
                              json={"id": "not-inbox-proof"})

    options = intercept(monkeypatch, accept)
    if provider == "brevo" and enabled and kind in {"password_reset", "email_verification"}:
        with pytest.raises(mail.MailDeliveryError):
            mail.send_security_email(kind, "reader@example.com", "Reader", token=CODE)
        assert not calls
        return
    mail.send_security_email(kind, "reader@example.com", "Reader", token=CODE)
    assert len(calls) == 1
    request = calls[0]
    payload = json.loads(request.content)
    if provider == "resend":
        assert str(request.url) == "https://api.resend.com/emails"
        assert request.headers["authorization"] == "Bearer fake-resend-key-for-tests"
        assert "api-key" not in request.headers
        assert payload["from"] == "SearchScribe AI <support@example.com>"
        assert payload["reply_to"] == "support@example.com"
        assert payload["to"] == ["reader@example.com"]
        html, plain = payload["html"], payload["text"]
    else:
        assert str(request.url) == "https://api.brevo.com/v3/smtp/email"
        assert request.headers["api-key"] == "fake-key-for-tests"
        assert "authorization" not in request.headers
        assert payload["sender"] == {"name": "SearchScribe AI", "email": "support@example.com"}
        assert payload["replyTo"] == payload["sender"]
        assert payload["to"] == [
            {"email": "reader@example.com", "contactPixelTrackingConsent": False},
        ]
        html, plain = payload["htmlContent"], payload["textContent"]
    if kind in {"password_changed", "password_added"}:
        assert CODE not in html and CODE not in plain
    else:
        assert CODE in html and CODE in plain
    assert not any("tracking" in key.lower() for key in request.headers)
    assert "headers" not in payload
    assert options["follow_redirects"] is False
    assert options["trust_env"] is False
    assert options["timeout"].connect == 3
    assert options["timeout"].read <= 30


@pytest.mark.parametrize("provider", ["brevo", "resend"])
@pytest.mark.parametrize("status", [302, 400, 401, 429, 500])
def test_failed_or_redirected_delivery_is_opaque_and_not_retried(
    status: int, provider: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mail.settings, "mail_provider", provider)
    calls: list[httpx.Request] = []

    def reject(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, text="recipient/token/api-key details must stay private")

    intercept(monkeypatch, reject)
    with pytest.raises(mail.MailDeliveryError) as failure:
        mail.send_security_email("password_reset", "reader@example.com", "Reader", token=CODE)
    assert len(calls) == 1
    assert str(failure.value) == "Email delivery could not be confirmed."


@pytest.mark.parametrize("provider", ["brevo", "resend"])
def test_ambiguous_timeout_is_not_retried(
    monkeypatch: pytest.MonkeyPatch, provider: str,
) -> None:
    monkeypatch.setattr(mail.settings, "mail_provider", provider)
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



def test_reply_to_uses_a_monitored_mailbox_in_payload_and_both_email_formats(monkeypatch):
    monkeypatch.setattr(mail.settings, "mail_provider", "resend")
    monkeypatch.setattr(mail.settings, "mail_reply_to_email", "help@example.org")
    calls = []

    def accept(request):
        calls.append(request)
        return httpx.Response(200)

    intercept(monkeypatch, accept)
    mail.send_security_email("password_added", "reader@example.com", "Reader")
    payload = json.loads(calls[0].content)
    assert payload["reply_to"] == "help@example.org"
    assert "Need help? Reply to this email." in payload["html"]
    assert "help@example.org" in payload["text"]


@pytest.mark.parametrize("provider,key", [("resend", "resend_api_key"), ("brevo", "brevo_api_key")])
def test_missing_selected_provider_key_never_falls_back(monkeypatch, provider, key):
    monkeypatch.setattr(mail.settings, "mail_provider", provider)
    monkeypatch.setattr(mail.settings, key, "")

    def forbidden(**kwargs):
        pytest.fail("A missing key attempted network access or provider fallback")

    monkeypatch.setattr(mail.httpx, "Client", forbidden)
    with pytest.raises(mail.MailDeliveryError, match="unavailable"):
        mail.send_security_email("password_added", "reader@example.com", "Reader")
