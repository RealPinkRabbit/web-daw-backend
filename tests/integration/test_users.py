"""
사용자 프로필 API 통합 테스트.
인증된 사용자의 프로필 조회, 수정, 탈퇴를 테스트한다.
"""

from fastapi.testclient import TestClient


class TestUsersHelper:
    """테스트에서 공통으로 사용하는 헬퍼 메서드."""

    def _register_and_login(
        self,
        client: TestClient,
        email: str = "user@example.com",
        username: str = "testuser",
        password: str = "password123",
    ) -> dict:
        """사용자를 등록하고 토큰을 반환한다."""
        client.post(
            "/api/v1/auth/register",
            json={"email": email, "username": username, "password": password},
        )
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        return login_response.json()

    def _auth_header(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}


class TestGetMyProfile(TestUsersHelper):
    """GET /api/v1/users/me 테스트."""

    def test_get_profile_success(self, client: TestClient):
        """로그인한 사용자의 프로필을 조회할 수 있어야 한다."""
        tokens = self._register_and_login(client)
        response = client.get(
            "/api/v1/users/me",
            headers=self._auth_header(tokens["access_token"]),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "user@example.com"
        assert data["username"] == "testuser"
        assert "hashed_password" not in data

    def test_get_profile_without_token(self, client: TestClient):
        """토큰 없이 프로필 조회 시 401 에러가 반환되어야 한다."""
        response = client.get("/api/v1/users/me")
        assert response.status_code == 401


class TestUpdateMyProfile(TestUsersHelper):
    """PATCH /api/v1/users/me 테스트."""

    def test_update_username_success(self, client: TestClient):
        """사용자명을 성공적으로 변경할 수 있어야 한다."""
        tokens = self._register_and_login(client)
        response = client.patch(
            "/api/v1/users/me",
            json={"username": "newusername"},
            headers=self._auth_header(tokens["access_token"]),
        )
        assert response.status_code == 200
        assert response.json()["username"] == "newusername"

    def test_update_email_success(self, client: TestClient):
        """이메일을 성공적으로 변경할 수 있어야 한다."""
        tokens = self._register_and_login(client)
        response = client.patch(
            "/api/v1/users/me",
            json={"email": "new@example.com"},
            headers=self._auth_header(tokens["access_token"]),
        )
        assert response.status_code == 200
        assert response.json()["email"] == "new@example.com"

    def test_update_duplicate_username_fails(self, client: TestClient):
        """이미 사용 중인 사용자명으로 변경 시 409 에러가 반환되어야 한다."""
        # 두 번째 사용자 생성
        self._register_and_login(
            client, email="other@example.com", username="takenuser"
        )
        # 첫 번째 사용자가 두 번째 사용자의 이름으로 변경 시도
        tokens = self._register_and_login(
            client, email="first@example.com", username="firstuser"
        )
        response = client.patch(
            "/api/v1/users/me",
            json={"username": "takenuser"},
            headers=self._auth_header(tokens["access_token"]),
        )
        assert response.status_code == 409

    def test_update_duplicate_email_fails(self, client: TestClient):
        """이미 사용 중인 이메일로 변경 시 409 에러가 반환되어야 한다."""
        self._register_and_login(
            client, email="taken@example.com", username="user1"
        )
        tokens = self._register_and_login(
            client, email="mine@example.com", username="user2"
        )
        response = client.patch(
            "/api/v1/users/me",
            json={"email": "taken@example.com"},
            headers=self._auth_header(tokens["access_token"]),
        )
        assert response.status_code == 409

    def test_update_without_token_fails(self, client: TestClient):
        """토큰 없이 프로필 수정 시 401 에러가 반환되어야 한다."""
        response = client.patch("/api/v1/users/me", json={"username": "new"})
        assert response.status_code == 401


class TestDeleteMyAccount(TestUsersHelper):
    """DELETE /api/v1/users/me 테스트."""

    def test_delete_account_success(self, client: TestClient):
        """계정 탈퇴(비활성화) 후 성공 메시지가 반환되어야 한다."""
        tokens = self._register_and_login(client)
        response = client.delete(
            "/api/v1/users/me",
            headers=self._auth_header(tokens["access_token"]),
        )
        assert response.status_code == 200
        assert "비활성화" in response.json()["message"]

    def test_deleted_user_cannot_login(self, client: TestClient):
        """비활성화된 계정으로 로그인 시 401 에러가 반환되어야 한다."""
        tokens = self._register_and_login(client)
        # 계정 비활성화
        client.delete(
            "/api/v1/users/me",
            headers=self._auth_header(tokens["access_token"]),
        )
        # 재로그인 시도
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "password123"},
        )
        assert response.status_code == 401

    def test_delete_without_token_fails(self, client: TestClient):
        """토큰 없이 계정 삭제 시 401 에러가 반환되어야 한다."""
        response = client.delete("/api/v1/users/me")
        assert response.status_code == 401
