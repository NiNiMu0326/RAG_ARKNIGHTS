"""
Tests for backend.auth: validation, password hashing, JWT encode/decode.
Usage: cd test && python -m pytest test_auth.py -v
"""
import os
import sys
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Must set JWT_SECRET before importing auth module
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-unit-tests")

import backend.auth as auth


# ============================================================
# Account validation
# ============================================================

class TestValidateAccount:
    def test_valid_english(self):
        assert auth.validate_account("hello") is None
        assert auth.validate_account("Test123") is None
        assert auth.validate_account("a") is None

    def test_valid_with_underscore(self):
        assert auth.validate_account("user_name") is None
        assert auth.validate_account("test_123") is None

    def test_valid_boundary_length(self):
        assert auth.validate_account("a") is None  # 1 char
        assert auth.validate_account("a" * 16) is None  # 16 chars

    def test_too_long(self):
        assert auth.validate_account("a" * 17) is not None

    def test_empty(self):
        assert auth.validate_account("") is not None

    def test_chinese_characters(self):
        assert auth.validate_account("中文名") is not None

    def test_special_chars(self):
        assert auth.validate_account("hello world") is not None
        assert auth.validate_account("hello@world") is not None
        assert auth.validate_account("hello-world") is not None


# ============================================================
# Username validation
# ============================================================

class TestValidateUsername:
    def test_valid_ascii(self):
        assert auth.validate_username("Alice") is None
        assert auth.validate_username("Test_User") is None

    def test_valid_chinese(self):
        assert auth.validate_username("德克萨斯") is None
        assert auth.validate_username("用户1") is None

    def test_valid_boundary(self):
        assert auth.validate_username("a") is None  # 1 char
        assert auth.validate_username("a" * 16) is None  # 16 chars

    def test_too_long(self):
        assert auth.validate_username("a" * 17) is not None

    def test_empty(self):
        assert auth.validate_username("") is not None
        assert auth.validate_username("   ") is not None  # stripped to empty


# ============================================================
# Password validation
# ============================================================

class TestValidatePassword:
    def test_valid_simple(self):
        assert auth.validate_password("abcdefgh") is None
        assert auth.validate_password("12345678") is None

    def test_valid_complex(self):
        assert auth.validate_password("Abc123!@") is None
        assert auth.validate_password("P@ssw0rd!") is None

    def test_valid_boundary(self):
        assert auth.validate_password("a" * 8) is None  # 8 chars min
        assert auth.validate_password("a" * 16) is None  # 16 chars max

    def test_too_short(self):
        assert auth.validate_password("a" * 7) is not None

    def test_too_long(self):
        assert auth.validate_password("a" * 17) is not None

    def test_empty(self):
        assert auth.validate_password("") is not None

    def test_spaces(self):
        assert auth.validate_password("a b c d e f g h") is not None


# ============================================================
# Password hashing
# ============================================================

class TestPasswordHashing:
    def test_hash_returns_string(self):
        result = auth.hash_password("testpass")
        assert isinstance(result, str)
        assert result.startswith("$2b$")

    def test_verify_correct_password(self):
        pw = "MyP@ssw0rd!"
        hashed = auth.hash_password(pw)
        assert auth.verify_password(pw, hashed) is True

    def test_verify_wrong_password(self):
        hashed = auth.hash_password("correct")
        assert auth.verify_password("wrong", hashed) is False

    def test_hash_is_salted(self):
        """Same password twice should produce different hashes."""
        h1 = auth.hash_password("samepass")
        h2 = auth.hash_password("samepass")
        assert h1 != h2
        assert auth.verify_password("samepass", h1)
        assert auth.verify_password("samepass", h2)


# ============================================================
# JWT
# ============================================================

class TestJWT:
    def test_create_and_decode(self):
        token = auth.create_jwt(1, "testuser", "TestUser", "2024-01-01T00:00:00")
        payload = auth.decode_jwt(token)
        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["account"] == "testuser"
        assert payload["username"] == "TestUser"
        assert payload["pw_changed_at"] == "2024-01-01T00:00:00"

    def test_decode_invalid_token(self):
        assert auth.decode_jwt("not.a.valid.token") is None
        assert auth.decode_jwt("") is None
        assert auth.decode_jwt("abc.def.ghi") is None

    def test_decode_garbage(self):
        assert auth.decode_jwt("garbage") is None

    def test_token_has_expiry(self):
        token = auth.create_jwt(1, "u", "n", "2024-01-01T00:00:00")
        payload = auth.decode_jwt(token)
        assert "exp" in payload
        assert "iat" in payload
