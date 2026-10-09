"""One-use security email tokens and shared database-backed abuse controls."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.exceptions import BadRequestError, RateLimitError
from ..core.security import hash_password
from ..db.base import utc_now
from ..db.models import RefreshToken, SecurityRateBucket, SecurityToken, User
from ..repositories.user_repo import UserRepository
from .transactional_mail import MailDeliveryError, send_security_email

logger = logging.getLogger(__name__)

SecurityMailKind = Literal["password_reset", "email_verification", "password_changed"]
FORGOT_MESSAGE = (
    "If this email belongs to an eligible account, we will send password reset instructions."
)
VERIFICATION_MESSAGE = "If your email needs verification, we will send verification instructions."
INVALID_TOKEN_MESSAGE = (
    "This code is invalid, expired, or already used. Request a new email."  # noqa: S105
)


@dataclass(frozen=True, repr=False)
class SecurityEmail:
    kind: SecurityMailKind
    recipient: str
    name: str
    token: str | None = None


def deliver_security_email(message: SecurityEmail) -> None:
    """Run after the HTTP response/DB commit; provider failures never disclose accounts."""
    try:
        send_security_email(message.kind, message.recipient, message.name, token=message.token)
    except MailDeliveryError:
        # Never log provider exception text, recipient, plaintext tokens or mail payloads.
        logger.warning("auth.security_email.delivery_failed", extra={"kind": message.kind})


def hash_security_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AccountRecoveryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)

    def _take_bucket(
        self, scope: str, value: str, start: datetime, end: datetime, limit: int
    ) -> bool:
        key = hmac.new(
            settings.secret_key.encode(),
            f"{scope}:{value}:{start.isoformat()}".encode(),
            hashlib.sha256,
        ).hexdigest()
        dialect = self.db.get_bind().dialect.name
        insert = postgres_insert if dialect == "postgresql" else sqlite_insert
        stmt = insert(SecurityRateBucket).values(key=key, count=1, expires_at=end)
        reserved = self.db.scalar(
            stmt.on_conflict_do_update(
                index_elements=[SecurityRateBucket.key],
                set_={"count": SecurityRateBucket.count + 1},
                where=SecurityRateBucket.count < limit,
            ).returning(SecurityRateBucket.count)
        )
        return reserved is not None

    def _allow_request(self, scope: str, client_ip: str, email: str | None = None) -> bool:
        now = utc_now()
        start = now.replace(minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=1)
        self.db.execute(delete(SecurityRateBucket).where(SecurityRateBucket.expires_at < now))
        # The IP budget is shared by all security email requests, including unknown
        # addresses. Do not allocate attacker-controlled email rows after it fills.
        allowed = self._take_bucket(
            f"ip:{scope}",
            client_ip,
            start,
            end,
            settings.security_ip_requests_per_hour,
        )
        if allowed and email is not None:
            allowed = self._take_bucket(
                f"email:{scope}",
                email,
                start,
                end,
                settings.security_email_requests_per_hour,
            )
        self.db.commit()
        return allowed

    def _reserve_mail(self, kind: SecurityMailKind) -> bool:
        now = utc_now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        limit = settings.mail_daily_limit
        if kind == "email_verification":
            limit -= settings.mail_recovery_reserve
        return self._take_bucket("mail:daily", "all", start, start + timedelta(days=1), limit)

    def _request_email(
        self, user: User, kind: Literal["password_reset", "email_verification"]
    ) -> SecurityEmail | None:
        if settings.mail_provider == "disabled":
            return None
        locked = self.users.lock_by_id(user.id)
        if (
            locked is None
            or not locked.is_active
            or (kind == "password_reset" and not locked.password_hash)
            or (kind == "email_verification" and locked.email_verified)
        ):
            self.db.rollback()
            return None
        if not self._reserve_mail(kind):
            self.db.rollback()
            return None
        token = secrets.token_urlsafe(32)
        expires = utc_now() + (
            timedelta(minutes=settings.password_reset_expire_minutes)
            if kind == "password_reset"
            else timedelta(hours=settings.email_verification_expire_hours)
        )
        self.db.add(
            SecurityToken(
                user_id=locked.id,
                purpose=kind,
                token_hash=hash_security_token(token),
                session_version=locked.session_version,
                expires_at=expires,
            )
        )
        message = SecurityEmail(kind=kind, recipient=locked.email, name=locked.name, token=token)
        # Even failed/ambiguous provider requests spend the reservation. Retrying
        # must never exceed the configured ceiling or the provider's free quota.
        self.db.commit()
        return message

    def request_password_reset(self, email: str, client_ip: str) -> SecurityEmail | None:
        normalized = email.strip().lower()
        if not self._allow_request("security_email", client_ip, normalized):
            return None
        user = self.users.get_by_email(normalized)
        if user is None or not user.is_active or not user.password_hash:
            return None
        return self._request_email(user, "password_reset")

    def request_verification(self, user: User, client_ip: str) -> SecurityEmail | None:
        if not self._allow_request("security_email", client_ip, user.email):
            return None
        return self._request_email(user, "email_verification")

    def _token_user(self, token: str, purpose: str) -> tuple[SecurityToken, User]:
        candidate = self.db.scalar(
            select(SecurityToken).where(
                SecurityToken.token_hash == hash_security_token(token),
                SecurityToken.purpose == purpose,
            )
        )
        if candidate is None:
            raise BadRequestError(INVALID_TOKEN_MESSAGE, code="INVALID_SECURITY_TOKEN")
        user = self.users.lock_by_id(candidate.user_id)
        if (
            user is None
            or not user.is_active
            or candidate.session_version != user.session_version
            or (purpose == "password_reset" and not user.password_hash)
        ):
            self.db.rollback()
            raise BadRequestError(INVALID_TOKEN_MESSAGE, code="INVALID_SECURITY_TOKEN")
        consumed = self.db.scalar(
            update(SecurityToken)
            .where(
                SecurityToken.id == candidate.id,
                SecurityToken.consumed_at.is_(None),
                SecurityToken.expires_at > utc_now(),
                SecurityToken.purpose == purpose,
                SecurityToken.session_version == user.session_version,
            )
            .values(consumed_at=utc_now())
            .returning(SecurityToken.id)
        )
        if consumed is None:
            self.db.rollback()
            raise BadRequestError(INVALID_TOKEN_MESSAGE, code="INVALID_SECURITY_TOKEN")
        return candidate, user

    def reset_password(self, token: str, password: str, client_ip: str) -> SecurityEmail | None:
        if not self._allow_request("token_submit", client_ip):
            raise RateLimitError()
        # Hash before locking the account to keep the critical transaction short.
        password_hash = hash_password(password)
        candidate, user = self._token_user(token, "password_reset")
        changed = self.db.scalar(
            update(User)
            .where(
                User.id == user.id,
                User.session_version == candidate.session_version,
                User.password_hash.is_not(None),
                User.is_active.is_(True),
            )
            .values(
                password_hash=password_hash,
                session_version=User.session_version + 1,
                updated_at=utc_now(),
            )
            .returning(User.id)
        )
        if changed is None:
            self.db.rollback()
            raise BadRequestError(INVALID_TOKEN_MESSAGE, code="INVALID_SECURITY_TOKEN")
        self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user.id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=utc_now())
        )
        self.db.execute(
            update(SecurityToken)
            .where(
                SecurityToken.user_id == user.id,
                SecurityToken.consumed_at.is_(None),
            )
            .values(consumed_at=utc_now())
        )
        notification = None
        if settings.mail_provider != "disabled" and self._reserve_mail("password_changed"):
            notification = SecurityEmail(
                kind="password_changed", recipient=user.email, name=user.name
            )
        self.db.commit()
        logger.info("auth.password_reset.success", extra={"user_id": user.id})
        return notification

    def verify_email(self, token: str, client_ip: str) -> None:
        if not self._allow_request("token_submit", client_ip):
            raise RateLimitError()
        _, user = self._token_user(token, "email_verification")
        self.db.execute(update(User).where(User.id == user.id).values(email_verified=True))
        self.db.execute(
            update(SecurityToken)
            .where(
                SecurityToken.user_id == user.id,
                SecurityToken.purpose == "email_verification",
                SecurityToken.consumed_at.is_(None),
            )
            .values(consumed_at=utc_now())
        )
        self.db.commit()
        logger.info("auth.email_verification.success", extra={"user_id": user.id})
