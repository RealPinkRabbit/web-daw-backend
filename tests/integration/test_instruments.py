"""
악기 API 통합 테스트.
오디오 샘플 업로드는 S3 Mock을 사용하고, 악기 CRUD/공유는 실제 DB로 테스트한다.
"""

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient


class TestInstrumentsHelper:
    """테스트에서 공통으로 사용하는 헬퍼 메서드."""

    def _register_and_login(
        self,
        client: TestClient,
        email: str = "inst@example.com",
        username: str = "instuser",
    ) -> str:
        """사용자를 등록하고 Access Token을 반환한다."""
        client.post(
            "/api/v1/auth/register",
            json={"email": email, "username": username, "password": "password123"},
        )
        res = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "password123"},
        )
        return res.json()["access_token"]

    def _auth(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def _upload_audio(self, client: TestClient, token: str) -> dict:
        """S3를 모킹하여 오디오 샘플을 업로드하고 응답 데이터를 반환한다."""
        with patch("app.services.audio_service.upload_file_to_s3") as mock:
            mock.return_value = f"audio/{uuid.uuid4()}.wav"
            res = client.post(
                "/api/v1/audio/upload",
                files={"file": ("kick.wav", b"fake content", "audio/wav")},
                headers=self._auth(token),
            )
        return res.json()

    def _create_instrument(self, client: TestClient, token: str, name: str = "My Drum Kit") -> dict:
        """악기를 생성하고 응답 데이터를 반환한다."""
        res = client.post(
            "/api/v1/instruments/",
            json={"name": name, "instrument_type": "drum_kit"},
            headers=self._auth(token),
        )
        return res.json()


class TestInstrumentCRUD(TestInstrumentsHelper):
    """악기 CRUD 테스트."""

    def test_create_instrument_success(self, client: TestClient):
        """악기를 성공적으로 생성할 수 있어야 한다."""
        token = self._register_and_login(client)
        res = client.post(
            "/api/v1/instruments/",
            json={
                "name": "My Drum Kit",
                "description": "A basic drum kit",
                "instrument_type": "drum_kit",
                "is_public": False,
                "config_json": {"bpm": 120},
            },
            headers=self._auth(token),
        )
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "My Drum Kit"
        assert data["instrument_type"] == "drum_kit"
        assert data["config_json"] == {"bpm": 120}
        assert data["instrument_samples"] == []

    def test_create_instrument_without_token_fails(self, client: TestClient):
        """토큰 없이 악기 생성 시 401 에러가 반환되어야 한다."""
        res = client.post("/api/v1/instruments/", json={"name": "test"})
        assert res.status_code == 401

    def test_list_instruments_empty(self, client: TestClient):
        """악기가 없으면 빈 목록이 반환되어야 한다."""
        token = self._register_and_login(client)
        res = client.get("/api/v1/instruments/", headers=self._auth(token))
        assert res.status_code == 200
        assert res.json()["total"] == 0
        assert res.json()["items"] == []

    def test_list_instruments_after_create(self, client: TestClient):
        """악기 생성 후 목록에 포함되어야 한다."""
        token = self._register_and_login(client)
        self._create_instrument(client, token, "Kit A")
        self._create_instrument(client, token, "Kit B")

        res = client.get("/api/v1/instruments/", headers=self._auth(token))
        assert res.json()["total"] == 2

    def test_list_only_own_instruments(self, client: TestClient):
        """다른 사용자의 악기는 목록에 포함되지 않아야 한다."""
        token1 = self._register_and_login(client, "u1@ex.com", "user1")
        token2 = self._register_and_login(client, "u2@ex.com", "user2")
        self._create_instrument(client, token1)

        res = client.get("/api/v1/instruments/", headers=self._auth(token2))
        assert res.json()["total"] == 0

    def test_get_instrument_success(self, client: TestClient):
        """자신의 악기를 성공적으로 조회할 수 있어야 한다."""
        token = self._register_and_login(client)
        instrument = self._create_instrument(client, token)

        res = client.get(
            f"/api/v1/instruments/{instrument['id']}",
            headers=self._auth(token),
        )
        assert res.status_code == 200
        assert res.json()["id"] == instrument["id"]

    def test_get_other_users_instrument_returns_404(self, client: TestClient):
        """다른 사용자의 악기 조회 시 404가 반환되어야 한다."""
        token1 = self._register_and_login(client, "u1@ex.com", "user1")
        token2 = self._register_and_login(client, "u2@ex.com", "user2")
        instrument = self._create_instrument(client, token1)

        res = client.get(
            f"/api/v1/instruments/{instrument['id']}",
            headers=self._auth(token2),
        )
        assert res.status_code == 404

    def test_update_instrument_success(self, client: TestClient):
        """악기 이름과 설정을 수정할 수 있어야 한다."""
        token = self._register_and_login(client)
        instrument = self._create_instrument(client, token)

        res = client.patch(
            f"/api/v1/instruments/{instrument['id']}",
            json={"name": "Updated Kit", "is_public": True},
            headers=self._auth(token),
        )
        assert res.status_code == 200
        assert res.json()["name"] == "Updated Kit"
        assert res.json()["is_public"] is True

    def test_update_other_users_instrument_returns_404(self, client: TestClient):
        """다른 사용자의 악기 수정 시 404가 반환되어야 한다."""
        token1 = self._register_and_login(client, "u1@ex.com", "user1")
        token2 = self._register_and_login(client, "u2@ex.com", "user2")
        instrument = self._create_instrument(client, token1)

        res = client.patch(
            f"/api/v1/instruments/{instrument['id']}",
            json={"name": "Hacked"},
            headers=self._auth(token2),
        )
        assert res.status_code == 404

    def test_delete_instrument_success(self, client: TestClient):
        """악기를 성공적으로 삭제할 수 있어야 한다."""
        token = self._register_and_login(client)
        instrument = self._create_instrument(client, token)

        res = client.delete(
            f"/api/v1/instruments/{instrument['id']}",
            headers=self._auth(token),
        )
        assert res.status_code == 200

    def test_deleted_instrument_is_gone(self, client: TestClient):
        """삭제 후 조회 시 404가 반환되어야 한다."""
        token = self._register_and_login(client)
        instrument = self._create_instrument(client, token)

        client.delete(
            f"/api/v1/instruments/{instrument['id']}",
            headers=self._auth(token),
        )
        res = client.get(
            f"/api/v1/instruments/{instrument['id']}",
            headers=self._auth(token),
        )
        assert res.status_code == 404


class TestSampleMapping(TestInstrumentsHelper):
    """오디오 샘플 매핑 테스트."""

    def test_add_sample_success(self, client: TestClient):
        """오디오 샘플을 악기에 성공적으로 매핑할 수 있어야 한다."""
        token = self._register_and_login(client)
        instrument = self._create_instrument(client, token)
        audio = self._upload_audio(client, token)

        res = client.post(
            f"/api/v1/instruments/{instrument['id']}/samples",
            json={
                "audio_sample_id": audio["id"],
                "note_key": "C4",
                "velocity_min": 0,
                "velocity_max": 127,
            },
            headers=self._auth(token),
        )
        assert res.status_code == 201
        assert res.json()["note_key"] == "C4"
        assert res.json()["audio_sample_id"] == audio["id"]

    def test_add_sample_appears_in_instrument(self, client: TestClient):
        """매핑 후 악기 조회 시 샘플 목록에 포함되어야 한다."""
        token = self._register_and_login(client)
        instrument = self._create_instrument(client, token)
        audio = self._upload_audio(client, token)

        client.post(
            f"/api/v1/instruments/{instrument['id']}/samples",
            json={"audio_sample_id": audio["id"], "note_key": "D4"},
            headers=self._auth(token),
        )
        res = client.get(
            f"/api/v1/instruments/{instrument['id']}",
            headers=self._auth(token),
        )
        assert len(res.json()["instrument_samples"]) == 1
        assert res.json()["instrument_samples"][0]["note_key"] == "D4"

    def test_add_other_users_audio_sample_fails(self, client: TestClient):
        """다른 사용자의 오디오 샘플 추가 시 404가 반환되어야 한다."""
        token1 = self._register_and_login(client, "u1@ex.com", "user1")
        token2 = self._register_and_login(client, "u2@ex.com", "user2")

        instrument = self._create_instrument(client, token1)
        audio_of_user2 = self._upload_audio(client, token2)

        res = client.post(
            f"/api/v1/instruments/{instrument['id']}/samples",
            json={"audio_sample_id": audio_of_user2["id"], "note_key": "C4"},
            headers=self._auth(token1),
        )
        assert res.status_code == 404

    def test_remove_sample_mapping_success(self, client: TestClient):
        """샘플 매핑을 성공적으로 제거할 수 있어야 한다."""
        token = self._register_and_login(client)
        instrument = self._create_instrument(client, token)
        audio = self._upload_audio(client, token)

        mapping = client.post(
            f"/api/v1/instruments/{instrument['id']}/samples",
            json={"audio_sample_id": audio["id"], "note_key": "C4"},
            headers=self._auth(token),
        ).json()

        res = client.delete(
            f"/api/v1/instruments/{instrument['id']}/samples/{mapping['id']}",
            headers=self._auth(token),
        )
        assert res.status_code == 200

        # 악기 조회 시 샘플 없음
        inst_res = client.get(
            f"/api/v1/instruments/{instrument['id']}",
            headers=self._auth(token),
        )
        assert inst_res.json()["instrument_samples"] == []

    def test_remove_nonexistent_mapping_returns_404(self, client: TestClient):
        """존재하지 않는 매핑 제거 시 404가 반환되어야 한다."""
        token = self._register_and_login(client)
        instrument = self._create_instrument(client, token)

        res = client.delete(
            f"/api/v1/instruments/{instrument['id']}/samples/{uuid.uuid4()}",
            headers=self._auth(token),
        )
        assert res.status_code == 404


class TestInstrumentShare(TestInstrumentsHelper):
    """악기 공유 테스트."""

    def test_create_share_link_success(self, client: TestClient):
        """공유 링크를 성공적으로 생성할 수 있어야 한다."""
        token = self._register_and_login(client)
        instrument = self._create_instrument(client, token)

        res = client.post(
            f"/api/v1/instruments/{instrument['id']}/share",
            headers=self._auth(token),
        )
        assert res.status_code == 200
        data = res.json()
        assert "share_token" in data
        assert "share_url" in data
        assert data["share_token"] in data["share_url"]

    def test_access_shared_instrument_without_auth(self, client: TestClient):
        """공유 토큰으로 인증 없이 악기를 조회할 수 있어야 한다."""
        token = self._register_and_login(client)
        instrument = self._create_instrument(client, token, "Shared Kit")

        share = client.post(
            f"/api/v1/instruments/{instrument['id']}/share",
            headers=self._auth(token),
        ).json()

        # 인증 없이 조회
        res = client.get(f"/api/v1/instruments/shared/{share['share_token']}")
        assert res.status_code == 200
        assert res.json()["name"] == "Shared Kit"

    def test_invalid_share_token_returns_404(self, client: TestClient):
        """존재하지 않는 토큰으로 조회 시 404가 반환되어야 한다."""
        res = client.get("/api/v1/instruments/shared/nonexistent-token-xyz")
        assert res.status_code == 404

    def test_create_share_twice_rotates_token(self, client: TestClient):
        """공유 링크를 두 번 생성하면 토큰이 갱신되어야 한다."""
        token = self._register_and_login(client)
        instrument = self._create_instrument(client, token)

        share1 = client.post(
            f"/api/v1/instruments/{instrument['id']}/share",
            headers=self._auth(token),
        ).json()
        share2 = client.post(
            f"/api/v1/instruments/{instrument['id']}/share",
            headers=self._auth(token),
        ).json()

        assert share1["share_token"] != share2["share_token"]

        # 이전 토큰은 무효화
        res = client.get(f"/api/v1/instruments/shared/{share1['share_token']}")
        assert res.status_code == 404

    def test_share_other_users_instrument_returns_404(self, client: TestClient):
        """다른 사용자의 악기에 공유 링크 생성 시 404가 반환되어야 한다."""
        token1 = self._register_and_login(client, "u1@ex.com", "user1")
        token2 = self._register_and_login(client, "u2@ex.com", "user2")
        instrument = self._create_instrument(client, token1)

        res = client.post(
            f"/api/v1/instruments/{instrument['id']}/share",
            headers=self._auth(token2),
        )
        assert res.status_code == 404
