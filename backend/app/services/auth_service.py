"""Authentication business logic: signup, login, session issuance and rotation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select, update
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
from ..db.models import RefreshToken, User
from ..repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SessionTokens:
    access_token: str
    refresh_token: str  # raw value; only its hash is persisted
    expires_in: int


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
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
        if not user.password_hash or not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password.")
        if not user.is_active:
            raise AuthenticationError("This account is disabled.")
        logger.info("auth.login.success", extra={"user_id": user.id})
        return user

    def issue_session(self, user: User) -> SessionTokens:
        """Create an access JWT and a new rotating refresh-token session."""
        expected_version = user.session_version
        locked = self.users.lock_by_id(user.id)
        if locked is None or not locked.is_active or locked.session_version != expected_version:
            self.db.rollback()
            raise AuthenticationError("Account changed. Please sign in again.")
        return self._issue_locked_session(locked)

    def _issue_locked_session(self, user: User) -> SessionTokens:
        """Caller holds the user lock until this transaction commits."""
        raw_refresh = generate_refresh_token()
        self.db.add(RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            session_version=user.session_version,
            expires_at=utc_now()
            + timedelta(days=settings.refresh_token_expire_days),
        ))
        user.last_login_at = utc_now()
        tokens = SessionTokens(
            access_token=create_access_token(user.id, user.session_version),
            refresh_token=raw_refresh,
            expires_in=settings.access_token_expire_minutes * 60,
        )
        self.db.commit()
        return tokens

    def rotate_refresh_session(self, raw_refresh_token: str) -> tuple[User, SessionTokens]:
        """Exchange a valid refresh token for new tokens, revoking the old one.

        Presenting an already-revoked token is treated as theft: every session
        belonging to that user is revoked.
        """
        token = self.users.find_refresh_token(hash_refresh_token(raw_refresh_token))
        if token is None:
            raise AuthenticationError("Invalid session.")
        # The user lock is also held by password reset and session issuance.
        # Reload both rows after acquiring it; a stale identity-map row could
        # otherwise resurrect a session that a concurrent reset revoked.
        user = self.users.lock_by_id(token.user_id)
        token = self.db.scalar(
            select(RefreshToken).where(RefreshToken.id == token.id)
            .execution_options(populate_existing=True)
        )
        if token is None or user is None or not user.is_active:
            raise AuthenticationError("Account not available.")
        if token.revoked_at is not None:
            self.users.revoke_all_refresh_tokens(token.user_id)
            logger.warning(
                "auth.refresh.reuse_detected", extra={"user_id": token.user_id}
            )
            raise AuthenticationError("Session no longer valid.")
        if not token.is_active or token.session_version != user.session_version:
            raise AuthenticationError("Session expired.")
        consumed = self.db.scalar(
            update(RefreshToken).where(
                RefreshToken.id == token.id, RefreshToken.revoked_at.is_(None),
                RefreshToken.session_version == user.session_version,
            ).values(revoked_at=utc_now()).returning(RefreshToken.id)
        )
        if consumed is None:
            self.db.rollback()
            raise AuthenticationError("Session no longer valid.")
        return user, self._issue_locked_session(user)

    def logout(self, raw_refresh_token: str | None) -> None:
        if not raw_refresh_token:
            return
        token = self.users.find_refresh_token(hash_refresh_token(raw_refresh_token))
        if token is not None and token.revoked_at is None:
            self.users.revoke_refresh_token(token)
