"""Authentication business logic: signup, login, session issuance and rotation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.exceptions import AuthenticationError, ConflictError
from ..core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from ..db.base import utc_now
from ..db.models import User
from ..repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SessionTokens:
    access_token: str
    refresh_token: str  # raw value; only its hash is persisted
    expires_in: int


class AuthService:
    def __init__(self, db: Session) -> None:
        self.users = UserRepository(db)

    def signup(self, *, email: str, name: str, password: str) -> User:
        normalized = email.strip().lower()
        if self.users.get_by_email(normalized) is not None:
            raise ConflictError("Email already registered.")
        user = self.users.create(
            email=normalized,
            name=name,
            password_hash=hash_password(password),
        )
        logger.info("auth.signup.success", extra={"user_id": user.id})
        return user

    def login(self, *, email: str, password: str) -> User:
        normalized = email.strip().lower()
        user = self.users.get_by_email(normalized)
        # Hash even when the user is missing to keep timing roughly uniform.
        if user is None:
            hash_password(password)
            raise AuthenticationError("Invalid email or password.")
        if not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password.")
        if not user.is_active:
            raise AuthenticationError("This account is disabled.")
        self.users.touch_last_login(user)
        logger.info("auth.login.success", extra={"user_id": user.id})
        return user

    def issue_session(self, user: User) -> SessionTokens:
        """Create an access JWT and a new rotating refresh-token session."""
        raw_refresh = generate_refresh_token()
        self.users.create_refresh_token(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=utc_now()
            + timedelta(days=settings.refresh_token_expire_days),
        )
        return SessionTokens(
            access_token=create_access_token(user.id),
            refresh_token=raw_refresh,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    def rotate_refresh_session(self, raw_refresh_token: str) -> tuple[User, SessionTokens]:
        """Exchange a valid refresh token for new tokens, revoking the old one.

        Presenting an already-revoked token is treated as theft: every session
        belonging to that user is revoked.
        """
        token = self.users.find_refresh_token(hash_refresh_token(raw_refresh_token))
        if token is None:
            raise AuthenticationError("Invalid session.")
        if token.revoked_at is not None:
            self.users.revoke_all_refresh_tokens(token.user_id)
            logger.warning(
                "auth.refresh.reuse_detected", extra={"user_id": token.user_id}
            )
            raise AuthenticationError("Session no longer valid.")
        if not token.is_active:
            raise AuthenticationError("Session expired.")

        user = self.users.get_by_id(token.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Account not available.")

        self.users.revoke_refresh_token(token)
        return user, self.issue_session(user)

    def logout(self, raw_refresh_token: str | None) -> None:
        if not raw_refresh_token:
            return
        token = self.users.find_refresh_token(hash_refresh_token(raw_refresh_token))
        if token is not None and token.revoked_at is None:
            self.users.revoke_refresh_token(token)
