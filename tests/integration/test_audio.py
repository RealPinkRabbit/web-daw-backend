"""
오디오 샘플 API 통합 테스트.
S3 호출은 unittest.mock으로 모킹하여 실제 AWS 없이 테스트한다.
"""

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient


class TestAudioHelper:
    """테스트에서 공통으로 사용하는 헬퍼 메서드."""

    def _register_and_login(
        self,
        client: TestClient,
        email: str = "audio@example.com",
        username: str = "audiouser",
    ) -> str:
        """사용자를 등록하고 Access Token을 반환한다."""
        client.post(
            "/api/v1/auth/register",
            json={"email": email, "username": username, "password": "password123"},
        )
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "password123"},
        )
        return login_response.json()["access_token"]

    def _auth_header(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def _upload_sample(self, client: TestClient, token: str, filename: str = "kick.wav") -> dict:
        """S3를 모킹하여 오디오 샘플을 업로드하고 응답 데이터를 반환한다."""
        with patch("app.services.audio_service.upload_file_to_s3") as mock_upload:
            mock_upload.return_value = f"audio/{uuid.uuid4()}.wav"
            response = client.post(
                "/api/v1/audio/upload",
                files={"file": (filename, b"fake audio content", "audio/wav")},
                headers=self._auth_header(token),
            )
        return response.json()


class TestAudioUpload(TestAudioHelper):
    """POST /api/v1/audio/upload 테스트."""

    def test_upload_wav_success(self, client: TestClient):
        """WAV 파일 업로드가 성공해야 한다."""
        token = self._register_and_login(client)
        with patch("app.services.audio_service.upload_file_to_s3") as mock_upload:
            mock_upload.return_value = "audio/test-uuid.wav"
            response = client.post(
                "/api/v1/audio/upload",
                files={"file": ("kick_drum.wav", b"fake wav content", "audio/wav")},
                headers=self._auth_header(token),
            )
        assert response.status_code == 201
        data = response.json()
        assert data["filename_original"] == "kick_drum.wav"
        assert data["mime_type"] == "audio/wav"
        assert data["file_size_bytes"] == len(b"fake wav content")
        assert "id" in data
        assert "hashed_password" not in data

    def test_upload_mp3_success(self, client: TestClient):
        """MP3 파일 업로드가 성공해야 한다."""
        token = self._register_and_login(client)
        with patch("app.services.audio_service.upload_file_to_s3") as mock_upload:
            mock_upload.return_value = "audio/test-uuid.mp3"
            response = client.post(
                "/api/v1/audio/upload",
                files={"file": ("melody.mp3", b"fake mp3 content", "audio/mpeg")},
                headers=self._auth_header(token),
            )
        assert response.status_code == 201
        assert response.json()["mime_type"] == "audio/mpeg"

    def test_upload_invalid_mime_type_fails(self, client: TestClient):
        """지원하지 않는 형식(이미지 등) 업로드 시 415 에러가 반환되어야 한다."""
        token = self._register_and_login(client)
        response = client.post(
            "/api/v1/audio/upload",
            files={"file": ("photo.jpg", b"fake image content", "image/jpeg")},
            headers=self._auth_header(token),
        )
        assert response.status_code == 415

    def test_upload_without_token_fails(self, client: TestClient):
        """토큰 없이 업로드 시 401 에러가 반환되어야 한다."""
        response = client.post(
            "/api/v1/audio/upload",
            files={"file": ("test.wav", b"content", "audio/wav")},
        )
        assert response.status_code == 401


class TestListAudioSamples(TestAudioHelper):
    """GET /api/v1/audio/ 테스트."""

    def test_list_empty(self, client: TestClient):
        """샘플이 없으면 빈 목록이 반환되어야 한다."""
        token = self._register_and_login(client)
        response = client.get("/api/v1/audio/", headers=self._auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1

    def test_list_after_upload(self, client: TestClient):
        """업로드 후 목록에 샘플이 포함되어야 한다."""
        token = self._register_and_login(client)
        self._upload_sample(client, token, "kick.wav")
        self._upload_sample(client, token, "snare.wav")

        response = client.get("/api/v1/audio/", headers=self._auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_without_token_fails(self, client: TestClient):
        """토큰 없이 목록 조회 시 401 에러가 반환되어야 한다."""
        response = client.get("/api/v1/audio/")
        assert response.status_code == 401

    def test_list_only_own_samples(self, client: TestClient):
        """다른 사용자의 샘플은 목록에 포함되지 않아야 한다."""
        token1 = self._register_and_login(client, email="u1@example.com", username="user1")
        token2 = self._register_and_login(client, email="u2@example.com", username="user2")

        # user1이 업로드
        self._upload_sample(client, token1, "kick.wav")

        # user2 목록 조회 → 빈 목록
        response = client.get("/api/v1/audio/", headers=self._auth_header(token2))
        assert response.json()["total"] == 0


class TestGetAudioSample(TestAudioHelper):
    """GET /api/v1/audio/{id} 테스트."""

    def test_get_sample_success(self, client: TestClient):
        """자신의 샘플을 성공적으로 조회할 수 있어야 한다."""
        token = self._register_and_login(client)
        sample = self._upload_sample(client, token)

        response = client.get(
            f"/api/v1/audio/{sample['id']}",
            headers=self._auth_header(token),
        )
        assert response.status_code == 200
        assert response.json()["id"] == sample["id"]

    def test_get_other_users_sample_returns_404(self, client: TestClient):
        """다른 사용자의 샘플 조회 시 404가 반환되어야 한다 (존재 노출 방지)."""
        token1 = self._register_and_login(client, email="u1@example.com", username="user1")
        token2 = self._register_and_login(client, email="u2@example.com", username="user2")

        sample = self._upload_sample(client, token1)

        response = client.get(
            f"/api/v1/audio/{sample['id']}",
            headers=self._auth_header(token2),
        )
        assert response.status_code == 404

    def test_get_nonexistent_sample_returns_404(self, client: TestClient):
        """존재하지 않는 샘플 조회 시 404가 반환되어야 한다."""
        token = self._register_and_login(client)
        response = client.get(
            f"/api/v1/audio/{uuid.uuid4()}",
            headers=self._auth_header(token),
        )
        assert response.status_code == 404


class TestDownloadAudioSample(TestAudioHelper):
    """GET /api/v1/audio/{id}/download 테스트."""

    def test_download_returns_redirect(self, client: TestClient):
        """다운로드 요청 시 Pre-signed URL로 302 리다이렉트해야 한다."""
        token = self._register_and_login(client)
        sample = self._upload_sample(client, token)

        with patch("app.services.audio_service.generate_presigned_url") as mock_url:
            mock_url.return_value = "https://s3.amazonaws.com/bucket/audio/test.wav?signature=abc"
            response = client.get(
                f"/api/v1/audio/{sample['id']}/download",
                headers=self._auth_header(token),
                follow_redirects=False,
            )
        assert response.status_code == 302
        assert "s3.amazonaws.com" in response.headers["location"]

    def test_download_other_users_sample_returns_404(self, client: TestClient):
        """다른 사용자의 샘플 다운로드 시 404가 반환되어야 한다."""
        token1 = self._register_and_login(client, email="u1@example.com", username="user1")
        token2 = self._register_and_login(client, email="u2@example.com", username="user2")

        sample = self._upload_sample(client, token1)

        response = client.get(
            f"/api/v1/audio/{sample['id']}/download",
            headers=self._auth_header(token2),
        )
        assert response.status_code == 404


class TestUpdateAudioSample(TestAudioHelper):
    """PATCH /api/v1/audio/{id} 테스트."""

    def test_update_filename_success(self, client: TestClient):
        """파일명을 성공적으로 변경할 수 있어야 한다."""
        token = self._register_and_login(client)
        sample = self._upload_sample(client, token)

        response = client.patch(
            f"/api/v1/audio/{sample['id']}",
            json={"filename_original": "renamed_kick.wav"},
            headers=self._auth_header(token),
        )
        assert response.status_code == 200
        assert response.json()["filename_original"] == "renamed_kick.wav"

    def test_update_is_public_success(self, client: TestClient):
        """공개 여부를 변경할 수 있어야 한다."""
        token = self._register_and_login(client)
        sample = self._upload_sample(client, token)

        response = client.patch(
            f"/api/v1/audio/{sample['id']}",
            json={"is_public": True},
            headers=self._auth_header(token),
        )
        assert response.status_code == 200
        assert response.json()["is_public"] is True

    def test_update_other_users_sample_returns_404(self, client: TestClient):
        """다른 사용자의 샘플 수정 시 404가 반환되어야 한다."""
        token1 = self._register_and_login(client, email="u1@example.com", username="user1")
        token2 = self._register_and_login(client, email="u2@example.com", username="user2")

        sample = self._upload_sample(client, token1)

        response = client.patch(
            f"/api/v1/audio/{sample['id']}",
            json={"filename_original": "hacked.wav"},
            headers=self._auth_header(token2),
        )
        assert response.status_code == 404


class TestDeleteAudioSample(TestAudioHelper):
    """DELETE /api/v1/audio/{id} 테스트."""

    def test_delete_success(self, client: TestClient):
        """자신의 샘플을 성공적으로 삭제할 수 있어야 한다."""
        token = self._register_and_login(client)
        sample = self._upload_sample(client, token)

        with patch("app.services.audio_service.delete_file_from_s3"):
            response = client.delete(
                f"/api/v1/audio/{sample['id']}",
                headers=self._auth_header(token),
            )
        assert response.status_code == 200
        assert response.json()["message"] == "삭제되었습니다."

    def test_deleted_sample_is_gone(self, client: TestClient):
        """삭제 후 조회 시 404가 반환되어야 한다."""
        token = self._register_and_login(client)
        sample = self._upload_sample(client, token)

        with patch("app.services.audio_service.delete_file_from_s3"):
            client.delete(
                f"/api/v1/audio/{sample['id']}",
                headers=self._auth_header(token),
            )

        response = client.get(
            f"/api/v1/audio/{sample['id']}",
            headers=self._auth_header(token),
        )
        assert response.status_code == 404

    def test_delete_other_users_sample_returns_404(self, client: TestClient):
        """다른 사용자의 샘플 삭제 시 404가 반환되어야 한다."""
        token1 = self._register_and_login(client, email="u1@example.com", username="user1")
        token2 = self._register_and_login(client, email="u2@example.com", username="user2")

        sample = self._upload_sample(client, token1)

        response = client.delete(
            f"/api/v1/audio/{sample['id']}",
            headers=self._auth_header(token2),
        )
        assert response.status_code == 404

    def test_delete_without_token_fails(self, client: TestClient):
        """토큰 없이 삭제 시 401 에러가 반환되어야 한다."""
        response = client.delete(f"/api/v1/audio/{uuid.uuid4()}")
        assert response.status_code == 401
