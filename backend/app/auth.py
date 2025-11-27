# backend/app/auth.py
from datetime import datetime, timedelta
from typing import Any, Dict

import hashlib
from jose import jwt, JWTError

from .config import settings


def _sha256(text: str) -> str:
    """Return hex-encoded SHA-256 hash of the given text.

    This replaces passlib/bcrypt to avoid binary dependency issues and works
    well for an interview assignment / demo project.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    """Hash a plain-text password.

    NOTE: In real production code you should use bcrypt/argon2 via passlib, but
    for this assignment we deliberately keep it dependency-free.
    """
    return _sha256(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compare a plain-text password against its stored hash."""
    return _sha256(plain_password) == hashed_password


def create_access_token(
    data: Dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token.

    The routers store the user's *id* in the `sub` (subject) claim, which is
    later read in `deps.get_current_user`.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token.

    Raises `ValueError` if the token is invalid or expired. `deps.get_current_user`
    catches this and converts it into a 401 HTTPException.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError:
        raise ValueError("Invalid token")
