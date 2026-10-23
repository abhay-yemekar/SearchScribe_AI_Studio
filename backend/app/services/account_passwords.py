"""Authenticated password management with fresh, one-use Google authorization."""

from __future__ import annotations

import secrets
from datetime import timedelta

import jwt
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.exceptions import AuthenticationError, ConflictError
from ..core.security import hash_password, verify_password
from ..db.base import utc_now
from ..db.models import ProviderIdentity, RefreshToken, SecurityToken, User
from ..repositories.user_repo import UserRepository
from .account_recovery import AccountRecoveryService, SecurityEmail, hash_security_token
from .google_auth import verify_google

PASSWORD_ADD_AUDIENCE = "google-password-add"  # noqa: S105 - JWT purpose, not a secret
_CHALLENGE_ERROR = "Confirm your linked Google account again to add a password."


def _google_proof_error() -> AuthenticationError:
    return AuthenticationError(_CHALLENGE_ERROR, code="PASSWORD_GOOGLE_VERIFICATION_FAILED")


class AccountPasswordService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.recovery = AccountRecoveryService(db)

    def _lock_current(self, user_id: int, version: int) -> User:
        user = self.users.lock_by_id(user_id)
        if user is None or not user.is_active or user.session_version != version:
            self.db.rollback()
            raise AuthenticationError("Account changed. Please sign in again.")
        return user

    def _identity(self, user_id: int) -> ProviderIdentity | None:
        return self.db.scalar(
            select(ProviderIdentity)
            .where(ProviderIdentity.user_id == user_id, ProviderIdentity.provider == "google")
            .execution_options(populate_existing=True)
        )

    def add_challenge(self, current: User, client_ip: str) -> tuple[str, str]:
        user_id, version = current.id, current.session_version
        self.recovery.limit_password_request(current, client_ip)
        user = self._lock_current(user_id, version)
        if user.password_hash or self._identity(user.id) is None:
            self.db.rollback()
            raise ConflictError("Adding a password requires a Google-only account.")
        nonce = secrets.token_urlsafe(32)
        expires = utc_now() + timedelta(minutes=5)
        signed = jwt.encode(
            {
                "aud": PASSWORD_ADD_AUDIENCE,
                "nonce": nonce,
                "uid": user.id,
                "sv": version,
                "exp": expires,
            },
            settings.secret_key,
            algorithm="HS256",
        )
        # Only the latest challenge can authorize adding a password, including
        # across tabs/workers. A process restart does not reset consumption.
        self.db.execute(
            update(SecurityToken)
            .where(
                SecurityToken.user_id == user.id,
                SecurityToken.purpose == "password_add",
                SecurityToken.consumed_at.is_(None),
            )
            .values(consumed_at=utc_now())
        )
        self.db.add(
            SecurityToken(
                user_id=user.id,
                purpose="password_add",
                token_hash=hash_security_token(nonce),
                session_version=version,
                expires_at=expires,
            )
        )
        self.db.commit()
        return nonce, signed

    def add_password(
        self,
        current: User,
        credential: str,
        challenge: str | None,
        password: str,
        client_ip: str,
    ) -> SecurityEmail | None:
        user_id, version = current.id, current.session_version
        self.recovery.limit_password_request(current, client_ip)
        try:
            bound = jwt.decode(
                challenge or "",
                settings.secret_key,
                algorithms=["HS256"],
                audience=PASSWORD_ADD_AUDIENCE,
                options={"require": ["exp", "nonce", "uid", "sv"]},
            )
            if (
                type(bound["uid"]) is not int
                or bound["uid"] != user_id
                or type(bound["sv"]) is not int
                or bound["sv"] != version
                or not isinstance(bound["nonce"], str)
            ):
                raise ValueError("Invalid bound account")
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            raise _google_proof_error() from None
        try:
            claims = verify_google(credential, challenge, expected_audience=PASSWORD_ADD_AUDIENCE)
        except AuthenticationError:
            raise _google_proof_error() from None
        password_hash = hash_password(password)
        user = self._lock_current(user_id, version)
        identity = self._identity(user.id)
        if user.password_hash or identity is None or identity.subject != claims["sub"]:
            self.db.rollback()
            raise _google_proof_error()
        consumed = self.db.scalar(
            update(SecurityToken)
            .where(
                SecurityToken.user_id == user.id,
                SecurityToken.purpose == "password_add",
                SecurityToken.token_hash == hash_security_token(bound["nonce"]),
                SecurityToken.session_version == version,
                SecurityToken.consumed_at.is_(None),
                SecurityToken.expires_at > utc_now(),
            )
            .values(consumed_at=utc_now())
            .returning(SecurityToken.id)
        )
        if consumed is None:
            self.db.rollback()
            raise _google_proof_error()
        return self._finish(user, version, password_hash, adding=True)

    def change_password(
        self,
        current: User,
        current_password: str,
        password: str,
        client_ip: str,
    ) -> SecurityEmail | None:
        user_id, version = current.id, current.session_version
        self.recovery.limit_password_request(current, client_ip)
        # Check the current password before hashing the new one, so wrong guesses
        # never cost a hash. The lock below re-checks that it hasn't changed since.
        verified_hash = current.password_hash
        if not verified_hash or not verify_password(current_password, verified_hash):
            raise AuthenticationError(
                "Your current password could not be verified.", code="PASSWORD_CURRENT_INVALID"
            )
        password_hash = hash_password(password)
        user = self._lock_current(user_id, version)
        if user.password_hash != verified_hash:
            self.db.rollback()
            raise AuthenticationError(
                "Your current password could not be verified.", code="PASSWORD_CURRENT_INVALID"
            )
        return self._finish(user, version, password_hash, adding=False)

    def _finish(
        self,
        user: User,
        version: int,
        password_hash: str,
        *,
        adding: bool,
    ) -> SecurityEmail | None:
        changed = self.db.scalar(
            update(User)
            .where(
                User.id == user.id,
                User.session_version == version,
                User.is_active.is_(True),
                User.password_hash.is_(None) if adding else User.password_hash.is_not(None),
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
            raise AuthenticationError("Account changed. Please sign in again.")
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
        notice = self.recovery.password_notification(
            user, "password_added" if adding else "password_changed"
        )
        self.db.commit()
        return notice
