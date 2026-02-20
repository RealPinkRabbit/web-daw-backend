# Phase 4: 악기 API — 회고록

## 목표

커스텀 악기(Instrument)를 생성·수정·삭제하고, 오디오 샘플을 노트에 매핑하고,
공유 링크로 타인과 악기를 공유하는 API를 구현한다.

---

## 구현된 API 엔드포인트

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| POST | `/api/v1/instruments/` | 필요 | 악기 생성 |
| GET | `/api/v1/instruments/` | 필요 | 내 악기 목록 (페이지네이션) |
| GET | `/api/v1/instruments/{id}` | 필요 | 단일 악기 조회 |
| PATCH | `/api/v1/instruments/{id}` | 필요 | 악기 수정 |
| DELETE | `/api/v1/instruments/{id}` | 필요 | 악기 삭제 |
| POST | `/api/v1/instruments/{id}/samples` | 필요 | 샘플 매핑 추가 |
| DELETE | `/api/v1/instruments/{id}/samples/{mapping_id}` | 필요 | 샘플 매핑 제거 |
| POST | `/api/v1/instruments/{id}/share` | 필요 | 공유 링크 생성/갱신 |
| GET | `/api/v1/instruments/shared/{token}` | **불필요** | 토큰으로 악기 조회 |

---

## 1. AI 없이 혼자 구축하는 단계별 절차

### Step 1: 모델 구조 파악

Phase 0에서 이미 3개 테이블이 설계되어 있다:

```
instruments         → Instrument (악기 정보 + config_json)
instrument_samples  → InstrumentSample (악기-오디오샘플 연결 + 노트 매핑)
shared_instruments  → SharedInstrument (공유 토큰)
```

외래 키 관계:
- `Instrument.owner_id → users.id (CASCADE)` → 사용자 삭제 시 악기도 삭제
- `InstrumentSample.instrument_id → instruments.id (CASCADE)` → 악기 삭제 시 매핑도 삭제
- `InstrumentSample.audio_sample_id → audio_samples.id (RESTRICT)` → 매핑된 오디오 샘플은 삭제 불가
- `SharedInstrument.instrument_id → instruments.id (CASCADE)` → 악기 삭제 시 공유 링크도 삭제

---

### Step 2: 서비스 함수 설계

```python
# 악기 CRUD
create_instrument(db, name, description, instrument_type, is_public, config_json, owner_id)
list_instruments(db, owner_id, page, limit) -> (items, total)
get_instrument(db, instrument_id, owner_id) -> Instrument
update_instrument(db, instrument_id, owner_id, **kwargs) -> Instrument
delete_instrument(db, instrument_id, owner_id) -> None

# 샘플 매핑
add_sample_to_instrument(db, instrument_id, owner_id, audio_sample_id, note_key, velocity_min, velocity_max)
remove_sample_from_instrument(db, instrument_id, owner_id, mapping_id)

# 공유
create_share_link(db, instrument_id, owner_id) -> SharedInstrument
get_shared_instrument(db, share_token) -> Instrument
```

---

### Step 3: 공유 토큰 생성

```python
import secrets

# URL-safe base64 인코딩, 32바이트 → 43자 토큰 생성
share_token = secrets.token_urlsafe(32)
```

`secrets` 모듈은 암호학적으로 안전한 난수를 생성한다.
`random.randint()`처럼 예측 가능한 난수 대신 반드시 `secrets`를 사용한다.

---

### Step 4: 라우트 순서 주의

```python
# 올바른 순서
@router.get("/shared/{share_token}")  # 고정 경로 먼저
def get_shared_instrument(...): ...

@router.get("/{instrument_id}")       # 파라미터 경로 나중
def get_instrument(...): ...
```

`GET /instruments/shared/abc`가 들어오면 FastAPI는 등록된 순서대로 매칭을 시도한다.
`/{instrument_id}`가 먼저 등록되면 `"shared"`가 instrument_id로 매칭되고,
`shared`를 UUID로 변환하려다 422 에러가 발생한다.

---

### Step 5: 공유 링크 생성 시 `Request` 활용

```python
from fastapi import Request

@router.post("/{instrument_id}/share")
def create_share_link(
    instrument_id: uuid.UUID,
    req: Request,                           # FastAPI가 자동 주입
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ShareResponse:
    share = instrument_service.create_share_link(...)
    share_url = str(req.base_url) + f"api/v1/instruments/shared/{share.share_token}"
    return ShareResponse(share_token=share.share_token, share_url=share_url)
```

`Request.base_url`은 실제 요청의 기반 URL을 반환하므로 하드코딩이 필요 없다.
로컬에서는 `http://localhost:8000/`, 프로덕션에서는 실제 도메인이 자동으로 들어간다.

---

## 2. 트러블슈팅

### 문제 1 (잠재적): 라우트 매칭 순서 충돌

**증상**: `GET /instruments/shared/{token}` 요청이 422 에러 반환
**원인**: `GET /instruments/{id}` 라우트가 먼저 등록되어 `"shared"`를 UUID로 변환하려 함
**해결**: `get_shared_instrument` 라우트를 `get_instrument` 라우트보다 먼저 등록
**교훈**: FastAPI에서 같은 prefix 하에 **고정 경로는 파라미터 경로보다 먼저** 등록한다

---

### 문제 2 (잠재적): `InstrumentRead.instrument_samples` 지연 로딩

**증상**: 악기 조회 응답에 `instrument_samples`가 빠지거나 `DetachedInstanceError`
**원인**: SQLAlchemy 지연 로딩이 세션 종료 후 작동 시 오류 발생
**해결**: FastAPI의 `Depends(get_db)`는 응답 직렬화가 완료될 때까지 세션을 열어 두므로,
현재 구현에서는 지연 로딩이 정상 동작한다.
만약 백그라운드 태스크 등에서 세션 밖으로 ORM 객체를 전달한다면
`selectinload(Instrument.instrument_samples)`를 쿼리에 추가한다.
**교훈**: SQLAlchemy 지연 로딩은 세션이 열려 있는 동안에만 작동한다

---

## 3. 코드 리뷰 포인트

### A. 이중 소유권 검사 (악기 + 오디오 샘플)

```python
def add_sample_to_instrument(db, instrument_id, owner_id, audio_sample_id, ...):
    # 1. 악기 소유권 확인
    instrument = get_instrument(db, instrument_id, owner_id)

    # 2. 오디오 샘플 소유권도 확인 (다른 사람의 샘플 추가 방지)
    audio_sample = db.query(AudioSample).filter(
        AudioSample.id == audio_sample_id,
        AudioSample.owner_id == owner_id   # 반드시 본인 소유 샘플
    ).first()
    if not audio_sample:
        raise NotFoundException("오디오 샘플을 찾을 수 없습니다.")
```

악기도 내 것이고 오디오 샘플도 내 것이어야만 매핑할 수 있다.
다른 사람의 오디오 샘플을 내 악기에 무단으로 연결하는 것을 방지한다.

---

### B. Cascade Delete 설계

```python
# Instrument 모델
instrument_samples = relationship("InstrumentSample", cascade="all, delete-orphan")
shared_instruments = relationship("SharedInstrument", cascade="all, delete-orphan")
```

`delete_instrument`에서 DB 레코드 하나만 삭제해도:
1. 연결된 `InstrumentSample` 레코드 자동 삭제 (cascade)
2. 연결된 `SharedInstrument` 레코드 자동 삭제 (cascade)

단, 오디오 샘플(`audio_samples`)은 `InstrumentSample`의 FK가 `RESTRICT`이므로 삭제되지 않는다.
악기를 삭제해도 오디오 파일은 그대로 보존된다.

---

### C. 공유 링크 토큰 교체 (Token Rotation)

```python
def create_share_link(db, instrument_id, owner_id) -> SharedInstrument:
    new_token = secrets.token_urlsafe(32)

    existing = db.query(SharedInstrument).filter(...).first()
    if existing:
        existing.share_token = new_token   # 기존 토큰 무효화 + 새 토큰 발급
        db.commit()
        return existing

    # 신규 생성
    share = SharedInstrument(...)
    db.add(share)
    ...
```

`POST /instruments/{id}/share`를 반복 호출하면 매번 새 토큰이 발급되고 이전 토큰은 무효화된다.
공유 링크가 유출된 경우 재발급으로 즉시 차단할 수 있다.

---

### D. 비인증 엔드포인트 설계

```python
@router.get("/shared/{share_token}", response_model=InstrumentRead)
def get_shared_instrument(
    share_token: str,
    db: Session = Depends(get_db),
    # get_current_user Depends가 없음 → 인증 불필요
) -> InstrumentRead:
    return instrument_service.get_shared_instrument(db=db, share_token=share_token)
```

`Depends(get_current_user)`를 파라미터에 추가하지 않으면 해당 엔드포인트는 인증 없이 접근 가능하다.
이 패턴으로 "공개 API vs 비공개 API"를 명확하게 구분한다.

---

### E. SQLAlchemy 관계와 Pydantic 직렬화

```python
class InstrumentRead(BaseModel):
    ...
    instrument_samples: list[InstrumentSampleRead]  # 관계 데이터 포함
    model_config = {"from_attributes": True}
```

`from_attributes=True`가 있으면 Pydantic이 SQLAlchemy ORM 객체에서 직접 데이터를 읽는다.
`instrument.instrument_samples`에 접근할 때 SQLAlchemy가 자동으로 관계 데이터를 로드한다.
이 때 세션이 열려 있어야 한다 (FastAPI의 `get_db` Depends가 이를 보장).

---

## 4. Phase 완료 체크리스트

- [x] `app/services/instrument_service.py` - 9개 서비스 함수 (커버리지 96%)
- [x] `app/api/v1/instruments.py` - 9개 엔드포인트 (커버리지 100%)
- [x] `app/api/v1/router.py` - instruments 라우터 등록
- [x] `tests/integration/test_instruments.py` - 21개 테스트 (전부 PASSED)
- [x] `pytest tests/ -v` → 74개 테스트 모두 PASSED
- [x] 코드 커버리지 95% 달성
- [x] 이중 소유권 검사: 타인의 샘플 추가 시 404 확인
- [x] 공유 링크: 토큰으로 인증 없이 접근 확인
- [x] 토큰 교체: 재생성 시 이전 토큰 무효화 확인
- [x] 라우트 순서: `/shared/{token}` → `/{id}` 순서로 등록

---

## 5. 다음 Phase 예고

**Phase 5: Docker + AWS 배포**

- `docker/Dockerfile` 작성 (멀티 스테이지 빌드: 빌드 스테이지 → 런타임 스테이지)
- `docker-compose.yml` 업데이트 (app 서비스 추가)
- AWS EC2 인스턴스 생성 및 서버 설정
- AWS RDS PostgreSQL 생성 및 보안 그룹 설정
- EC2에 Docker 설치 및 앱 배포
- S3 버킷 생성 및 IAM 역할 설정
- 환경변수 관리 (.env vs AWS Secrets Manager)
