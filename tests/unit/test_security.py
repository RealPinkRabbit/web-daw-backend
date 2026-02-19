"""
security.py 함수들에 대한 단위 테스트.
JWT 생성/검증, 비밀번호 해싱이 올바르게 동작하는지 확인한다.
"""

import pytest
from jose import JWTError

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    """비밀번호 해싱 테스트."""

    def test_hash_password_returns_different_string(self):
        """해싱된 비밀번호는 원본과 달라야 한다."""
        plain = "mypassword123"
        hashed = hash_password(plain)
        assert hashed != plain

    def test_verify_correct_password(self):
        """올바른 비밀번호는 검증을 통과해야 한다."""
        plain = "mypassword123"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password(self):
        """틀린 비밀번호는 검증에 실패해야 한다."""
        plain = "mypassword123"
        hashed = hash_password(plain)
        assert verify_password("wrongpassword", hashed) is False

    def test_same_password_produces_different_hashes(self):
        """같은 비밀번호라도 bcrypt는 매번 다른 해시를 생성한다 (salt 때문)."""
        plain = "mypassword123"
        hash1 = hash_password(plain)
        hash2 = hash_password(plain)
        assert hash1 != hash2


class TestJWT:
    """JWT 토큰 테스트."""

    def test_create_and_decode_access_token(self):
        """Access Token 생성 후 디코딩 시 동일한 sub 값이 나와야 한다."""
        data = {"sub": "user-uuid-123"}
        token = create_access_token(data)
        payload = decode_token(token)

        assert payload["sub"] == "user-uuid-123"
        assert payload["type"] == "access"

    def test_create_and_decode_refresh_token(self):
        """Refresh Token 생성 후 디코딩 시 type이 'refresh'여야 한다."""
        data = {"sub": "user-uuid-123"}
        token = create_refresh_token(data)
        payload = decode_token(token)

        assert payload["sub"] == "user-uuid-123"
        assert payload["type"] == "refresh"

    def test_decode_invalid_token_raises_error(self):
        """유효하지 않은 토큰 디코딩 시 JWTError가 발생해야 한다."""
        with pytest.raises(JWTError):
            decode_token("this.is.not.a.valid.token")

    def test_decode_tampered_token_raises_error(self):
        """변조된 토큰 디코딩 시 JWTError가 발생해야 한다."""
        data = {"sub": "user-uuid-123"}
        token = create_access_token(data)
        # 토큰 마지막 문자를 변경하여 변조
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

        with pytest.raises(JWTError):
            decode_token(tampered)
