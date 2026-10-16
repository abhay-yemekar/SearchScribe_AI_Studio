"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..core.exceptions import AuthenticationError
from ..core.rate_limit import enforce
from ..core.security import decode_access_token
from ..db.models import User
from ..db.session import get_db
from ..repositories.user_repo import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise AuthenticationError("Missing bearer token.")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (ValueError, KeyError, TypeError):
        raise AuthenticationError("Invalid or expired token.") from None

    user = UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Invalid or expired token.")
    # Tokens issued before this migration have version zero. A password reset
    # increments the stored version, immediately invalidating prior access JWTs.
    if type(payload.get("sv", 0)) is not int or payload.get("sv", 0) != user.session_version:
        raise AuthenticationError("Invalid or expired token.")
    return user


def user_rate_limit(scope: str, limit: int) -> Any:
    """Per-account minute limit for authenticated routes, so users never share a bucket.

    FastAPI caches ``get_current_user`` per request, so the route's own
    ``current_user`` parameter reuses this lookup.
    """

    def dependency(current_user: User = Depends(get_current_user)) -> None:
        enforce(f"{scope}:user:{current_user.id}", limit)

    return Depends(dependency)


__all__ = ["get_current_user", "get_db", "user_rate_limit"]
