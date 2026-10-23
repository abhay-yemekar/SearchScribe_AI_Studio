"""Authentication business logic: signup, login, session issuance and rotation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.exceptions import AuthenticationError, ConflictError, RateLimitError
from ..core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    password_needs_rehash,
    verify_password,
)
from ..db.base import utc_now
from ..db.models import RefreshToken, User
from ..repositories.user_repo import UserRepository
from .security_buckets import clear_bucket, delete_expired_buckets, take_bucket

logger = logging.getLogger(__name__)

LOGIN_ATTEMPT_SCOPE = "login_attempt:email"
SIGNUP_SCOPE = "signup:ip"
LOGIN_THROTTLED_MESSAGE = (
    "Too many sign-in attempts for this email. Wait a few minutes or reset your password."
)


def _login_window(now: datetime) -> tuple[datetime, datetime]:
    size = timedelta(minutes=settings.login_attempt_window_minutes)
    start = datetime.min + (now - datetime.min) // size * size
    return start, start + size


@dataclass(frozen=True)
class SessionTokens:
    access_token: str
    refresh_token: str  # raw value; only its hash is persisted
    expires_in: int


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)

    def limit_signups(self, client_ip: str) -> None:
        """Spend this network's daily new-account budget, before any hashing.

        Attempts count, not only successes, and the use is committed at once.
        """
        now = utc_now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        delete_expired_buckets(self.db, now)
        allowed = take_bucket(
            self.db, SIGNUP_SCOPE, client_ip, start, end, settings.signups_per_ip_per_day
        )
        self.db.commit()
        if not allowed:
            logger.warning("auth.signup.throttled")
            raise RateLimitError(
                "Too many new accounts from this network today. "
                "Try again tomorrow, or continue with Google.",
                details={"retry_after_seconds": int((end - now).total_seconds()) + 1},
            )

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
        now = utc_now()
        start, end = _login_window(now)
        # A persistent per-address budget, spent before any password hashing and
        # committed now so a failed attempt still counts. Unknown addresses spend
        # it too, so a 429 never reveals whether an account exists.
        delete_expired_buckets(self.db, now)
        allowed = take_bucket(
            self.db, LOGIN_ATTEMPT_SCOPE, normalized, start, end,
            settings.login_attempts_per_email,
        )
        self.db.commit()
        if not allowed:
            logger.warning("auth.login.throttled")
            raise RateLimitError(
                LOGIN_THROTTLED_MESSAGE,
                details={"retry_after_seconds": int((end - now).total_seconds()) + 1},
            )
        user = self.users.get_by_email(normalized)
        # Hash even when the user is missing to keep timing roughly uniform.
        if user is None:
            hash_password(password)
            raise AuthenticationError("Invalid email or password.")
        if not user.password_hash or not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password.")
        if not user.is_active:
            raise AuthenticationError("This account is disabled.")
        if password_needs_rehash(user.password_hash):
            # Flushed now: issue_session re-reads the row under a lock, and
            # commits it with the new session.
            user.password_hash = hash_password(password)
            self.db.flush()
        logger.info("auth.login.success", extra={"user_id": user.id})
        return user

    def clear_login_attempts(self, email: str) -> None:
        """Refund an address's attempts once its password sign-in has issued a session."""
        start, _ = _login_window(utc_now())
        clear_bucket(self.db, LOGIN_ATTEMPT_SCOPE, email.strip().lower(), start)
        self.db.commit()

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

        Presenting an already-revoked token for the current session version is
        treated as theft: every session belonging to that user is revoked.
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
        # Earlier account versions must not revoke sessions created after a reset.
        if token.session_version != user.session_version:
            raise AuthenticationError("Session expired.")
        if token.revoked_at is not None:
            self.users.revoke_all_refresh_tokens(token.user_id)
            logger.warning(
                "auth.refresh.reuse_detected", extra={"user_id": token.user_id}
            )
            raise AuthenticationError("Session no longer valid.")
        if not token.is_active:
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
