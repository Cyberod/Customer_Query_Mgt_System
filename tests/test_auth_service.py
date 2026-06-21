"""Unit tests for app/services/auth.py — no database or HTTP needed."""
import pytest
from jose import jwt

from app.config import settings
from app.services.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_produces_bcrypt_hash():
    hashed = hash_password("secret123")
    assert hashed.startswith("$2b$")


def test_hash_is_different_from_plaintext():
    hashed = hash_password("mypassword")
    assert hashed != "mypassword"


def test_verify_password_correct():
    hashed = hash_password("correct-horse")
    assert verify_password("correct-horse", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("correct-horse")
    assert verify_password("wrong-horse", hashed) is False


def test_two_hashes_of_same_password_differ():
    # bcrypt uses a random salt each time
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2
    assert verify_password("same", h1)
    assert verify_password("same", h2)


def test_create_access_token_returns_string():
    token = create_access_token({"sub": "42"})
    assert isinstance(token, str)
    assert len(token) > 0


def test_access_token_contains_sub_claim():
    token = create_access_token({"sub": "99"})
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    assert payload["sub"] == "99"


def test_access_token_contains_exp_claim():
    token = create_access_token({"sub": "1"})
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    assert "exp" in payload


def test_decode_access_token_roundtrip():
    token = create_access_token({"sub": "7", "role": "agent"})
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "7"
    assert decoded["role"] == "agent"


def test_decode_access_token_invalid_returns_none():
    result = decode_access_token("this.is.not.a.valid.token")
    assert result is None


def test_decode_access_token_wrong_secret_returns_none():
    # Sign with a different key — decode should fail
    bad_token = jwt.encode({"sub": "1"}, "wrong-secret", algorithm="HS256")
    assert decode_access_token(bad_token) is None
