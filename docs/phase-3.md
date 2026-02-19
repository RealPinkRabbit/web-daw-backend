# Phase 3: S3 오디오 업로드 — 회고록

## 목표

오디오 파일을 AWS S3에 업로드하고, Pre-signed URL로 다운로드하는 API를 구현한다.
실제 파일 바이트는 API 서버를 통하지 않고 클라이언트가 S3에서 직접 받는 구조로 설계한다.

---

## 구현된 API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/audio/upload` | 오디오 파일 업로드 (multipart/form-data) |
| GET | `/api/v1/audio/` | 내 샘플 목록 (페이지네이션) |
| GET | `/api/v1/audio/{id}` | 단일 샘플 메타데이터 조회 |
| GET | `/api/v1/audio/{id}/download` | Pre-signed URL로 302 리다이렉트 |
| PATCH | `/api/v1/audio/{id}` | 파일명 / 공개 여부 수정 |
| DELETE | `/api/v1/audio/{id}` | 샘플 삭제 (DB + S3) |

---

## 1. AI 없이 혼자 구축하는 단계별 절차

### Step 1: boto3 S3 헬퍼 작성 (`app/core/s3.py`)

```python
import boto3
import uuid
from app.config import settings

def get_s3_client():
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )

def upload_file_to_s3(file_content: bytes, original_filename: str, content_type: str) -> str:
    extension = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "bin"
    s3_key = f"audio/{uuid.uuid4()}.{extension}"
    client = get_s3_client()
    client.put_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key, Body=file_content, ContentType=content_type)
    return s3_key

def generate_presigned_url(s3_key: str, expires_in: int = 300) -> str:
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key},
        ExpiresIn=expires_in,
    )
```

---

### Step 2: AudioSample 모델 확인 (`app/models/audio_sample.py`)

Phase 0에서 이미 작성된 모델이다. 핵심 필드:
- `filename_original`: 사용자가 올린 원본 파일명 (예: `kick_drum.wav`)
- `filename_s3`: S3에 저장된 UUID 기반 키 (예: `audio/abc123.wav`)
- `s3_bucket`: 저장된 버킷 이름
- `file_size_bytes`: 파일 크기 (바이트)
- `mime_type`: `audio/wav`, `audio/mpeg`, `audio/ogg`

---

### Step 3: 서비스 레이어 작성 (`app/services/audio_service.py`)

```python
def upload_audio(db, file_content, original_filename, content_type, owner_id) -> AudioSample:
    s3_key = upload_file_to_s3(file_content, original_filename, content_type)
    sample = AudioSample(
        owner_id=owner_id,
        filename_original=original_filename,
        filename_s3=s3_key,
        s3_bucket=settings.S3_BUCKET_NAME,
        file_size_bytes=len(file_content),
        mime_type=content_type,
    )
    db.add(sample)
    db.commit()
    return sample
```

---

### Step 4: 라우터 작성 (`app/api/v1/audio.py`)

업로드는 FastAPI의 `UploadFile`을 사용한다:

```python
@router.post("/upload", status_code=201)
def upload_audio(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, ...)
    file_content = file.file.read()
    return audio_service.upload_audio(...)
```

다운로드는 `RedirectResponse`로 Pre-signed URL에 302 리다이렉트:

```python
@router.get("/{sample_id}/download")
def download_audio(...) -> RedirectResponse:
    url = audio_service.get_presigned_download_url(...)
    return RedirectResponse(url=url, status_code=302)
```

---

### Step 5: router.py에 audio 라우터 등록

```python
from app.api.v1 import audio, auth, users

api_router.include_router(audio.router)
```

---

### Step 6: 테스트 작성 (S3 Mock)

```python
from unittest.mock import patch

def test_upload_wav_success(self, client):
    with patch("app.services.audio_service.upload_file_to_s3") as mock_upload:
        mock_upload.return_value = "audio/test-uuid.wav"
        response = client.post(
            "/api/v1/audio/upload",
            files={"file": ("kick.wav", b"fake content", "audio/wav")},
            headers=auth_headers,
        )
    assert response.status_code == 201
```

`patch`의 경로는 **사용하는 모듈**의 경로를 지정한다.
`app.core.s3.upload_file_to_s3`가 아니라 `app.services.audio_service.upload_file_to_s3`를 패치한다.

---

## 2. 트러블슈팅

### 문제 1: patch 경로가 틀리면 Mock이 동작하지 않음

**증상**: `@patch("app.core.s3.upload_file_to_s3")`로 패치했는데 실제 S3 호출이 발생함
**원인**: Python의 `patch`는 **이름이 사용되는 위치**를 패치해야 한다
```python
# audio_service.py
from app.core.s3 import upload_file_to_s3  # 이 이름으로 바인딩됨
```
`audio_service` 모듈 안에서 `upload_file_to_s3`는 이미 로컬 이름으로 바인딩되어 있다.
따라서 `app.core.s3.upload_file_to_s3`를 패치해도 `audio_service`가 이미 참조한 함수는 바뀌지 않는다.

**해결**: `app.services.audio_service.upload_file_to_s3`를 패치
**교훈**: `from module import func`로 임포트한 경우, 항상 **사용 위치(import한 모듈)**를 패치한다

---

### 문제 2: 302 리다이렉트 테스트 시 follow_redirects

**증상**: `client.get(".../download")` 결과가 200도 아니고 S3 URL도 아님
**원인**: `TestClient`는 기본으로 리다이렉트를 자동 따라감 (`follow_redirects=True`)
**해결**: `follow_redirects=False` 옵션으로 302 응답 자체를 캡처

```python
response = client.get(
    f"/api/v1/audio/{sample_id}/download",
    follow_redirects=False,
)
assert response.status_code == 302
assert "s3.amazonaws.com" in response.headers["location"]
```

**교훈**: 리다이렉트 응답을 테스트할 때는 반드시 `follow_redirects=False` 옵션을 사용한다

---

## 3. 코드 리뷰 포인트

### A. Pre-signed URL 패턴

```
업로드 흐름:
  클라이언트  →  POST /audio/upload (파일 바이트)
              →  API 서버가 S3에 PUT
              →  201 + 메타데이터 반환

다운로드 흐름:
  클라이언트  →  GET /audio/{id}/download
              →  API 서버가 Pre-signed URL 생성 (5분 유효)
              →  302 Redirect → Pre-signed URL
  클라이언트  →  S3에서 직접 다운로드 (API 서버 무관)
```

**장점**:
- API 서버가 파일 바이트를 프록시하지 않아 대역폭 비용 절감
- API 서버는 무상태 유지 → 수평 확장 용이
- Pre-signed URL은 시간 제한이 있어 무한정 공유 방지

---

### B. S3 키 설계 (경로 조작 공격 방지)

```python
# 위험한 방식: 사용자 입력 파일명을 그대로 S3 키로 사용
s3_key = f"audio/{original_filename}"  # 위험! "../secret.txt" 등 가능

# 안전한 방식: UUID로 키 생성, 원본 파일명은 DB에만 저장
extension = original_filename.rsplit(".", 1)[-1].lower()
s3_key = f"audio/{uuid.uuid4()}.{extension}"  # 안전
```

사용자가 올린 파일명은 `filename_original` 컬럼에만 보관하고,
실제 S3 키는 UUID 기반으로 서버에서 생성한다.

---

### C. DB 먼저, S3 나중에 삭제하는 이유

```python
def delete_audio_sample(...):
    s3_key = sample.filename_s3
    db.delete(sample)
    db.commit()          # 1. DB 삭제 먼저 커밋
    delete_file_from_s3(s3_key)  # 2. S3 삭제
```

| 순서 | S3 먼저 삭제 | DB 먼저 삭제 |
|------|------------|------------|
| 중간 실패 시 | DB에 레코드 있지만 S3 파일 없음 (심각) | DB 삭제됐지만 S3 파일 남음 (허용) |
| 복구 가능성 | 어려움 (고아 레코드) | 쉬움 (S3 정리 작업 가능) |

**결론**: S3에 불필요한 파일이 남는 것보다, DB 레코드가 없는 파일이 남는 것이 복구하기 쉽다.

---

### D. MIME 타입 검증 위치 선택

```python
# 라우터에서 검증 (채택)
@router.post("/upload")
def upload_audio(file: UploadFile = File(...), ...):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, ...)
    # S3 업로드는 하지 않고 바로 에러 반환
```

MIME 타입 검증은 비즈니스 로직이 아닌 **입력 검증**이므로 라우터 레벨에서 처리한다.
잘못된 형식은 서비스 레이어에 도달하기 전에 즉시 거부한다.

---

### E. 소유권 검사에 404 반환 (403 아님)

```python
def get_audio_sample(db, sample_id, owner_id):
    sample = db.query(AudioSample).filter(
        AudioSample.id == sample_id,
        AudioSample.owner_id == owner_id  # 소유자 조건 포함
    ).first()
    if not sample:
        raise NotFoundException()  # 403이 아닌 404
```

403 Forbidden을 반환하면 "리소스는 존재하지만 접근 권한이 없다"는 정보가 노출된다.
404 Not Found를 반환하면 존재 자체를 알 수 없어 열거 공격(enumeration attack)을 방지한다.

---

### F. 페이지네이션 구조

```python
# 서비스
def list_audio_samples(db, owner_id, page=1, limit=20):
    query = db.query(AudioSample).filter(AudioSample.owner_id == owner_id)
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return items, total

# 라우터
PaginatedAudioSamples(
    items=items,
    total=total,
    page=page,
    limit=limit,
    pages=ceil(total / limit) if total > 0 else 0,
)
```

클라이언트가 `GET /audio/?page=2&limit=10`으로 요청하면,
응답에 `total`, `pages`가 포함되어 몇 페이지가 더 있는지 알 수 있다.

---

## 4. Phase 완료 체크리스트

- [x] `app/core/s3.py` - boto3 S3 헬퍼 (upload, presigned URL, delete)
- [x] `app/services/audio_service.py` - 6개 서비스 함수 (커버리지 100%)
- [x] `app/api/v1/audio.py` - 6개 엔드포인트 (커버리지 97%)
- [x] `app/api/v1/router.py` - audio 라우터 등록
- [x] `tests/integration/test_audio.py` - 20개 테스트 (S3 Mock 사용)
- [x] `pytest tests/ -v` → 53개 테스트 모두 PASSED
- [x] 코드 커버리지 84% 달성
- [x] 소유권 검사: 타인 리소스 접근 시 404 반환 확인
- [x] MIME 타입 검증: 이미지 업로드 시 415 반환 확인
- [x] Pre-signed URL 다운로드: 302 리다이렉트 확인
- [x] 삭제: DB 삭제 후 조회 시 404 확인

---

## 5. 다음 Phase 예고

**Phase 4: 악기 API (CRUD, 샘플 매핑, 공유)**

- `POST /api/v1/instruments/` - 악기 생성
- `GET /api/v1/instruments/` - 내 악기 목록
- `POST /api/v1/instruments/{id}/samples` - 오디오 샘플을 악기 노트에 매핑
- `POST /api/v1/instruments/{id}/share` - 공유 링크 생성
- `GET /api/v1/instruments/shared/{token}` - 공유 링크로 악기 조회 (인증 불필요)

`Instrument`, `InstrumentSample`, `SharedInstrument` 모델과 `schemas/instrument.py`가 이미 준비되어 있다.
