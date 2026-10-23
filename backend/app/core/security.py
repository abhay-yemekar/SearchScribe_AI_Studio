"""Password hashing (Argon2id), JWT access tokens, and refresh-token utils."""

from __future__ import annotations

import hashlib
import secrets
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from .config import settings
from .exceptions import ServiceUnavailableError

# Argon2id at OWASP's minimum (19 MiB, t=2, p=1), not the library default of
# 64 MiB and p=4: on a 512 MB instance a handful of parallel default hashes runs
# the process out of memory. Hashes made with other settings still verify.
_hasher = PasswordHasher(memory_cost=19_456, time_cost=2, parallelism=1)

# At most two hashes or verifications at once; the rest wait their turn, and give
# up with a 503 rather than pile up unbounded.
_hash_slots = threading.BoundedSemaphore(2)
HASH_SLOT_TIMEOUT_SECONDS = 10.0


@contextmanager
def _hash_slot() -> Iterator[None]:
    if not _hash_slots.acquire(timeout=HASH_SLOT_TIMEOUT_SECONDS):
        raise ServiceUnavailableError(
            "The server is busy. Please try again in a moment.", code="SERVER_BUSY"
        )
    try:
        yield
    finally:
        _hash_slots.release()


def hash_password(password: str) -> str:
    """Hash a plaintext password with Argon2id + random salt."""
    with _hash_slot():
        return _hasher.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Constant-time verification of a plaintext password against a stored hash."""
    try:
        with _hash_slot():
            return _hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    """True for hashes made with older, more expensive settings."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return False


def create_access_token(user_id: int, session_version: int = 0) -> str:
    """Short-lived signed JWT identifying the user (sent as Bearer token)."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "access",
        "sv": session_version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate an access JWT. Raises ValueError when invalid."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError as exc:
        raise ValueError("Invalid or expired token") from exc
    if payload.get("type") != "access":
        raise ValueError("Wrong token type")
    return payload


def generate_refresh_token() -> str:
    """Opaque 256-bit refresh token. Only its SHA-256 hash is stored."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
