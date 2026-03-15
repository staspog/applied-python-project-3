"""Юнит-тесты: хэширование паролей и JWT."""
from __future__ import annotations

import pytest

from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_password_returns_str():
    h = hash_password("secret123")
    assert isinstance(h, str)
    assert h != "secret123"


def test_verify_password_correct():
    h = hash_password("secret123")
    assert verify_password("secret123", h) is True


def test_verify_password_wrong():
    h = hash_password("secret123")
    assert verify_password("wrong", h) is False


def test_verify_password_invalid_hash():
    """Невалидный хэш — False (ValueError перехватывается)."""
    assert verify_password("any", "not-a-valid-bcrypt-hash") is False


def test_create_and_decode_token():
    token = create_access_token(subject="42", username="alice")
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["username"] == "alice"
    assert "exp" in payload


def test_decode_token_invalid_raises():
    with pytest.raises(ValueError, match="Invalid token"):
        decode_token("invalid.jwt.here")
