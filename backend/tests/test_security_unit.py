"""Unit tests for password hashing and token primitives."""

from __future__ import annotations

import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_argon2id_hash_format() -> None:
    hashed = hash_password("hunter2-secret-1")
    assert hashed.startswith("$argon2id$")


def test_hash_has_unique_salts() -> None:
    assert hash_password("same-password-1") != hash_password("same-password-1")


def test_verify_password_roundtrip() -> None:
    hashed = hash_password("roundtrip-pass-1")
    assert verify_password("roundtrip-pass-1", hashed)
    assert not verify_password("other-password-1", hashed)


def test_verify_rejects_garbage_hash() -> None:
    assert not verify_password("whatever-1", "not-a-hash")


def test_access_token_roundtrip() -> None:
    token = create_access_token(42)
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["type"] == "access"


def test_decode_rejects_garbage_token() -> None:
    with pytest.raises(ValueError):
        decode_access_token("garbage.token.here")


def test_refresh_tokens_are_random_and_hashable() -> None:
    a, b = generate_refresh_token(), generate_refresh_token()
    assert a != b and len(a) >= 32
    assert hash_refresh_token(a) != hash_refresh_token(b)
    assert len(hash_refresh_token(a)) == 64
