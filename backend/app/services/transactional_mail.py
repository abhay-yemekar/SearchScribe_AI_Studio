"""Branded security emails with opt-in fragment links and tracking consent off.

Fragment links are enabled only after Brevo's account-level per-contact tracking
feature is activated and verified. Until then, emails retain manual security
codes and token-free destinations. Acceptance is not inbox proof. No payload is logged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import EmailStr, TypeAdapter, ValidationError

from ..core.config import settings

SecurityMailKind = Literal["password_reset", "email_verification", "password_changed"]
_TEMPLATES = Environment(
    loader=FileSystemLoader(Path(__file__).with_name("email_templates")),
    autoescape=select_autoescape(["html"]),
)
_EMAIL = TypeAdapter(EmailStr)


class MailDeliveryError(Exception):
    """Opaque failure; never expose response bodies, recipient, token or API key."""


@dataclass(frozen=True)
class RenderedSecurityEmail:
    subject: str
    html: str
    text: str


def _site_origin() -> str:
    origin = settings.public_site_url
    try:
        parsed = urlsplit(origin)
        _ = parsed.port
    except ValueError:
        raise MailDeliveryError("Email service is unavailable.") from None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or any(character in origin for character in "?#\\")
        or any(character.isspace() for character in origin)
        or (
            parsed.scheme == "http"
            and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        )
        or (settings.is_production and parsed.scheme != "https")
    ):
        raise MailDeliveryError("Email service is unavailable.")
    return origin.rstrip("/")


def render_security_email(
    kind: SecurityMailKind, name: str, *, token: str | None = None,
) -> RenderedSecurityEmail:
    """Render deterministic HTML/plain text; caller owns token creation/expiry."""
    origin = _site_origin()
    link_mode = settings.security_email_links_enabled
    greeting = re.sub(r"[\x00-\x1f\x7f]", "", name).strip().split(" ")[0][:60] or "there"
    if kind == "password_reset":
        subject = "Reset your SearchScribe AI password"
        heading = "Reset your password."
        intro = "We received a request to reset the password for your SearchScribe AI account."
        instruction = (
            "Use the button below to choose a new password."
            if link_mode else "Open SearchScribe, paste the code below, and choose a new password."
        )
        action, path, label = "Reset password", "/reset-password", "YOUR RESET CODE"
        expiry = (
            f"This {'link' if link_mode else 'code'} expires in "
            f"{settings.password_reset_expire_minutes} minutes."
        )
        notice = "If you didn't request this, ignore this email. Your password hasn't changed."
    elif kind == "email_verification":
        subject = "Verify your email for SearchScribe AI"
        heading = "Verify your email."
        intro = "Confirm this email address belongs to you to complete your account setup."
        instruction = (
            "Use the button below to confirm your email address."
            if link_mode else "Open SearchScribe and paste the verification code below."
        )
        action, path, label = "Verify email", "/verify-email", "YOUR VERIFICATION CODE"
        expiry = (
            f"This {'link' if link_mode else 'code'} expires in "
            f"{settings.email_verification_expire_hours} hours."
        )
        notice = "If you didn't create a SearchScribe AI account, you can ignore this email."
    elif kind == "password_changed":
        subject = "Your SearchScribe AI password was changed"
        heading = "Your password is updated."
        intro = "The password for your SearchScribe AI account was just changed."
        instruction = "Previous sessions have been signed out. Use your new password to sign in."
        action, path, label = "Open SearchScribe", "/login", ""
        expiry = ""
        notice = (
            "If you didn't make this change, reset your password immediately and contact support."
        )
        token = None
    else:
        raise ValueError("Unsupported security email")
    if kind != "password_changed" and (
        token is None or re.fullmatch(r"[A-Za-z0-9_-]{20,200}", token) is None
    ):
        raise ValueError("A valid opaque security code is required")
    action_page = origin + path
    # Tokens are constrained to URL-safe characters, so the fragment cannot
    # inject query parameters or change the canonical destination.
    action_url = action_page + (f"#token={token}" if link_mode and token else "")
    html = _TEMPLATES.get_template("security.html").render(
        subject=subject, heading=heading, greeting=greeting, intro=intro,
        instruction=instruction, action=action, action_url=action_url,
        origin=origin, code=None if link_mode else token, label=label,
        expiry=expiry, notice=notice, action_page=action_page,
        logo_url=origin + "/brand/email-wordmark-v2.png",
        support_email=settings.mail_from_email,
    )
    lines = ["SearchScribe AI", "", f"Hi {greeting},", "", heading, intro, "", instruction]
    if token and not link_mode:
        lines.extend(["", label, token, "", expiry, "Use this code only on SearchScribe."])
    elif token:
        lines.extend(["", expiry, "Use this link once, only on SearchScribe."])
    lines.extend(["", f"{action}: {action_url}", "", notice])
    if settings.mail_from_email:
        lines.extend(["", f"Need help? Reply to {settings.mail_from_email}."])
    lines.extend(["", "SearchScribe AI — your words, your workspace.", origin])
    return RenderedSecurityEmail(subject, html, "\n".join(lines))


def send_security_email(
    kind: SecurityMailKind, recipient: str, name: str, *, token: str | None = None,
) -> None:
    """Send once with bounded timeout; never retry ambiguous accepted deliveries."""
    if settings.mail_provider != "brevo" or not settings.brevo_api_key:
        raise MailDeliveryError("Email service is unavailable.")
    try:
        to_email = str(_EMAIL.validate_python(recipient))
        from_email = str(_EMAIL.validate_python(settings.mail_from_email))
        rendered = render_security_email(kind, name, token=token)
    except (ValidationError, ValueError) as exc:
        raise MailDeliveryError("Email service is unavailable.") from exc
    payload = {
        "sender": {"name": settings.mail_from_name, "email": from_email},
        # Brevo documents this recipient setting for opens and clicks after its
        # per-contact tracking consent feature is activated on the account.
        "to": [{"email": to_email, "contactPixelTrackingConsent": False}],
        "replyTo": {"name": settings.mail_from_name, "email": from_email},
        "subject": rendered.subject,
        "htmlContent": rendered.html,
        "textContent": rendered.text,
        "tags": ["searchscribe-security", kind],
    }
    try:
        with httpx.Client(
            timeout=httpx.Timeout(settings.mail_timeout_seconds, connect=3),
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response = client.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": settings.brevo_api_key, "Accept": "application/json"},
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise MailDeliveryError("Email delivery could not be confirmed.") from exc
    # Do not reflect provider bodies: they may contain recipients or submitted data.
    if response.status_code != 201:
        raise MailDeliveryError("Email delivery could not be confirmed.")
