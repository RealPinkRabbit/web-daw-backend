"""
인증 API 통합 테스트.
실제 HTTP 요청을 보내고 응답을 검증한다.
"""

from fastapi.testclient import TestClient


class TestRegister:
    """POST /api/v1/auth/register 테스트."""

    def test_register_success(self, client: TestClient):
        """정상적인 회원가입이 성공해야 한다."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "securepassword123",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["username"] == "testuser"
        assert "hashed_password" not in data  # 비밀번호 절대 노출 금지
        assert "id" in data

    def test_register_duplicate_email(self, client: TestClient):
        """중복 이메일로 회원가입 시 409 에러가 반환되어야 한다."""
        client.post(
            "/api/v1/auth/register",
            json={"email": "dup@example.com", "username": "user1", "password": "password123"},
        )
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "dup@example.com", "username": "user2", "password": "password123"},
        )
        assert response.status_code == 409

    def test_register_duplicate_username(self, client: TestClient):
        """중복 사용자명으로 회원가입 시 409 에러가 반환되어야 한다."""
        client.post(
            "/api/v1/auth/register",
            json={"email": "a@example.com", "username": "sameuser", "password": "password123"},
        )
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "b@example.com", "username": "sameuser", "password": "password123"},
        )
        assert response.status_code == 409

    def test_register_invalid_email(self, client: TestClient):
        """잘못된 이메일 형식으로 회원가입 시 422 에러가 반환되어야 한다."""
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "username": "user", "password": "password123"},
        )
        assert response.status_code == 422

    def test_register_short_password(self, client: TestClient):
        """8자 미만 비밀번호로 회원가입 시 422 에러가 반환되어야 한다."""
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "username": "user", "password": "short"},
        )
        assert response.status_code == 422


class TestLogin:
    """POST /api/v1/auth/login 테스트."""

    def _register_user(self, client: TestClient, email: str = "login@example.com") -> None:
        client.post(
            "/api/v1/auth/register",
            json={"email": email, "username": "loginuser", "password": "mypassword123"},
        )

    def test_login_success(self, client: TestClient):
        """올바른 자격증명으로 로그인 시 토큰이 반환되어야 한다."""
        self._register_user(client)
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "login@example.com", "password": "mypassword123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client: TestClient):
        """틀린 비밀번호로 로그인 시 401 에러가 반환되어야 한다."""
        self._register_user(client)
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "login@example.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client: TestClient):
        """존재하지 않는 이메일로 로그인 시 401 에러가 반환되어야 한다."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "password123"},
        )
        assert response.status_code == 401


class TestRefreshToken:
    """POST /api/v1/auth/refresh 테스트."""

    def _register_and_login(self, client: TestClient) -> dict:
        client.post(
            "/api/v1/auth/register",
            json={"email": "refresh@example.com", "username": "refreshuser", "password": "password123"},
        )
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "refresh@example.com", "password": "password123"},
        )
        return login_response.json()

    def test_refresh_returns_new_access_token(self, client: TestClient):
        """유효한 Refresh Token으로 새 Access Token을 받아야 한다."""
        tokens = self._register_and_login(client)
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        # 새로 발급된 Access Token은 기존과 달라야 한다 (exp 등 차이)

    def test_refresh_with_access_token_fails(self, client: TestClient):
        """Access Token을 Refresh Token 자리에 사용하면 401 에러가 반환되어야 한다."""
        tokens = self._register_and_login(client)
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["access_token"]},
        )
        assert response.status_code == 401

    def test_refresh_with_invalid_token_fails(self, client: TestClient):
        """유효하지 않은 토큰으로 갱신 시 401 에러가 반환되어야 한다."""
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.value"},
        )
        assert response.status_code == 401

    def test_new_access_token_is_usable(self, client: TestClient):
        """갱신된 Access Token으로 보호된 엔드포인트에 접근할 수 있어야 한다."""
        tokens = self._register_and_login(client)
        refresh_response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        new_access_token = refresh_response.json()["access_token"]
        me_response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {new_access_token}"},
        )
        assert me_response.status_code == 200
        assert me_response.json()["email"] == "refresh@example.com"


class TestProtectedEndpoint:
    """인증이 필요한 엔드포인트 테스트."""

    def _get_token(self, client: TestClient) -> str:
        """테스트용 사용자를 만들고 Access Token을 반환한다."""
        client.post(
            "/api/v1/auth/register",
            json={"email": "auth@example.com", "username": "authuser", "password": "password123"},
        )
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "auth@example.com", "password": "password123"},
        )
        return login_response.json()["access_token"]

    def test_get_me_with_valid_token(self, client: TestClient):
        """유효한 토큰으로 /auth/me 호출 시 사용자 정보가 반환되어야 한다."""
        token = self._get_token(client)
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["email"] == "auth@example.com"

    def test_get_me_without_token(self, client: TestClient):
        """토큰 없이 /auth/me 호출 시 401 에러가 반환되어야 한다."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_get_me_with_invalid_token(self, client: TestClient):
        """유효하지 않은 토큰으로 /auth/me 호출 시 401 에러가 반환되어야 한다."""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401
