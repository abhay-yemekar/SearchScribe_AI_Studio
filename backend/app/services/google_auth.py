"""Google ID-token verification and explicit provider linking."""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any

import jwt
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.exceptions import AuthenticationError, ConflictError, ServiceUnavailableError
from ..core.security import verify_password
from ..db.base import utc_now
from ..db.models import ProviderIdentity, User


def new_challenge() -> tuple[str, str]:
    nonce = secrets.token_urlsafe(32)
    signed = jwt.encode(
        {"nonce": nonce, "aud": "google-challenge", "exp": utc_now() + timedelta(minutes=5)},
        settings.secret_key,
        algorithm="HS256",
    )
    return nonce, signed


def verify_google(credential: str, challenge: str | None) -> dict[str, Any]:
    if not settings.google_client_id:
        raise ServiceUnavailableError("Google sign-in is not configured yet.")
    try:
        nonce = jwt.decode(
            challenge or "",
            settings.secret_key,
            algorithms=["HS256"],
            audience="google-challenge",
            options={"require": ["exp", "nonce"]},
        )["nonce"]

        # Bound Google's certificate-fetch request; never follow token-supplied URLs.
        class BoundedRequest(GoogleRequest):
            def __call__(self, *args: Any, **kwargs: Any) -> Any:
                kwargs["timeout"] = 10
                return super().__call__(*args, **kwargs)

        claims = id_token.verify_oauth2_token(
            credential, BoundedRequest(), settings.google_client_id
        )
        if (
            not isinstance(claims.get("nonce"), str)
            or not secrets.compare_digest(claims["nonce"], nonce)
            or claims.get("email_verified") is not True
            or not isinstance(claims.get("sub"), str)
            or not claims["sub"]
            or len(claims["sub"]) > 255
            or not isinstance(claims.get("email"), str)
        ):
            raise ValueError("Invalid Google identity")
        return claims
    except (ValueError, KeyError, TypeError, jwt.PyJWTError):
        raise AuthenticationError(
            "Google sign-in could not be verified. Please try again."
        ) from None
    except GoogleAuthError:
        raise ServiceUnavailableError(
            "Google verification is unavailable. Please try again."
        ) from None


def google_user(
    db: Session, claims: dict[str, Any], *, current: User | None = None, password: str | None = None
) -> User:
    if current:
        expected_version = current.session_version
        current = db.scalar(
            select(User).where(User.id == current.id).with_for_update()
            .execution_options(populate_existing=True)
        )
        if current is None or not current.is_active or current.session_version != expected_version:
            raise AuthenticationError("Account changed. Please sign in again.")
    subject = claims["sub"]
    identity = db.scalar(
        select(ProviderIdentity).where(
            ProviderIdentity.provider == "google", ProviderIdentity.subject == subject
        )
    )
    if identity:
        if current and identity.user_id != current.id:
            raise ConflictError("This Google identity is already linked to another account.")
        if not identity.user.is_active:
            raise AuthenticationError("This account is disabled.")
        if claims["email"].strip().lower() == identity.user.email:
            identity.user.email_verified = True
            db.commit()
        return identity.user
    email = claims["email"].strip().lower()
    if current:
        if (
            not current.password_hash
            or not password
            or not verify_password(password, current.password_hash)
            or email != current.email
        ):
            raise AuthenticationError(
                "Confirm your password and select Google with the same email."
            )
        user = current
        user.email_verified = True
    else:
        if db.scalar(select(User).where(User.email == email)):
            raise ConflictError(
                "An account with this email exists. Sign in with your password, "
                "then link Google from Account.",
                code="GOOGLE_LINK_REQUIRED",
            )
        user = User(
            email=email,
            name=str(claims.get("name") or email.split("@")[0])[:100],
            password_hash=None,
            email_verified=True,
        )
        db.add(user)
    try:
        db.flush()
        db.add(ProviderIdentity(user_id=user.id, provider="google", subject=subject))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Account changed during sign-in. Please try again.") from None
    db.refresh(user)
    return user
