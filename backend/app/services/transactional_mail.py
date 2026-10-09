"""Branded security emails over HTTPS, with secrets outside tracked links.

Brevo does not document per-message tracking controls. Security codes therefore
appear as text, while every clickable destination is a token-free site page.
Provider acceptance is not evidence of inbox delivery. No payload is logged.
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
    origin = settings.public_site_url.rstrip("/")
    parsed = urlsplit(origin)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
        or (settings.is_production and parsed.scheme != "https")
    ):
        raise MailDeliveryError("Email service is unavailable.")
    return origin


def render_security_email(
    kind: SecurityMailKind, name: str, *, token: str | None = None,
) -> RenderedSecurityEmail:
    """Render deterministic HTML/plain text; caller owns token creation/expiry."""
    origin = _site_origin()
    greeting = re.sub(r"[\x00-\x1f\x7f]", "", name).strip().split(" ")[0][:60] or "there"
    if kind == "password_reset":
        subject = "Reset your SearchScribe AI password"
        heading = "Reset your password."
        intro = "We received a request to reset the password for your SearchScribe AI account."
        instruction = "Open SearchScribe, paste the code below, and choose a new password."
        action, path, label = "Reset password", "/reset-password", "YOUR RESET CODE"
        expiry = f"This code expires in {settings.password_reset_expire_minutes} minutes."
        notice = "If you didn't request this, ignore this email. Your password hasn't changed."
    elif kind == "email_verification":
        subject = "Verify your email for SearchScribe AI"
        heading = "Verify your email."
        intro = "Confirm this email address belongs to you to complete your account setup."
        instruction = "Open SearchScribe and paste the verification code below."
        action, path, label = "Verify email", "/verify-email", "YOUR VERIFICATION CODE"
        expiry = f"This code expires in {settings.email_verification_expire_hours} hours."
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
        token is None or re.fullmatch(r"[A-Za-z0-9_-]{20,512}", token) is None
    ):
        raise ValueError("A valid opaque security code is required")
    action_url = origin + path
    html = _TEMPLATES.get_template("security.html").render(
        subject=subject, heading=heading, greeting=greeting, intro=intro,
        instruction=instruction, action=action, action_url=action_url,
        origin=origin, code=token, label=label, expiry=expiry, notice=notice,
        logo_url=origin + "/brand/email-wordmark.png",
        support_email=settings.mail_from_email,
    )
    lines = ["SearchScribe AI", "", f"Hi {greeting},", "", heading, intro, "", instruction]
    if token:
        lines.extend(["", label, token, "", expiry, "Use this code only on SearchScribe."])
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
        "to": [{"email": to_email}],
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
