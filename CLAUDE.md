# CLAUDE.md - Web DAW Backend 프로젝트 컨텍스트

> 이 파일은 Claude Code가 새 세션을 시작할 때 프로젝트 전체 맥락을 복원하기 위한 파일입니다.
> 진행 단계가 바뀌면 "현재 진행 단계" 섹션을 직접 업데이트하세요.

---

## 프로젝트 개요

**Web DAW (Digital Audio Workstation) Backend API**

사용자가 오디오 샘플을 업로드하고, 커스텀 악기를 만들고, 다른 사용자와 공유할 수 있는 백엔드 API 서버.
**목적**: 백엔드 개발 입문자가 FastAPI, PostgreSQL, AWS를 단계적으로 학습하는 프로젝트.

**원칙**: 명확성 > 영리함. 짧은 한 줄 코드보다 읽기 쉬운 명시적 코드를 작성한다.

---

## 기술 스택

| 레이어 | 기술 | 버전 |
|--------|------|------|
| Framework | FastAPI | 0.111+ |
| ORM | SQLAlchemy | 2.0 |
| Migration | Alembic | 1.13+ |
| Database | PostgreSQL | 15 |
| Auth | python-jose + passlib[bcrypt] | latest |
| Storage | boto3 (AWS S3) | latest |
| Settings | pydantic-settings | 2.x |
| Testing | pytest + httpx | latest |
| Container | Docker + Docker Compose | latest |
| CI/CD | GitHub Actions | - |
| Cloud | AWS EC2 + RDS + S3 | - |

---

## 아키텍처 결정 사항

### Services 레이어를 사용하는 이유
라우터는 서비스를 호출하고, 서비스는 모델/DB를 호출한다.
HTTP 관심사와 비즈니스 로직을 분리하여 테스트가 쉽고 재사용이 가능하다.
**라우터에서 직접 DB를 쿼리하지 않는다. 항상 서비스를 통한다.**

### UUID PK를 사용하는 이유
순차적 ID 열거 공격을 방지한다. UUID v4는 무작위로 안전하다.
```python
id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
```

### Pre-signed S3 URL 방식
API 서버가 오디오 파일 바이트를 직접 프록시하지 않는다.
1. 클라이언트가 `GET /audio/{id}/download` 호출
2. API가 시간 제한(5분) Pre-signed S3 URL 생성
3. API가 302 리다이렉트로 해당 URL 반환
4. 클라이언트가 S3에서 직접 다운로드

API 서버를 무상태로 유지하고 대역폭 비용을 절감한다.

### 공유 기능에 별도 테이블을 사용하는 이유
공유 로직을 `instruments` 테이블에서 분리하여:
- 악기당 여러 공유 링크 지원
- 만료 링크 추가 (나중에 `expires_at` 컬럼 추가 가능)
- 악기를 삭제하지 않고 공유 링크만 취소 가능

---

## 디렉토리 구조

```
web-daw-backend/
├── app/
│   ├── main.py              # 앱 팩토리, 미들웨어, 라우터 등록
│   ├── config.py            # pydantic-settings (환경변수 관리)
│   ├── dependencies.py      # get_db(), get_current_user() - 모든 보호된 라우터에서 사용
│   ├── api/v1/
│   │   ├── router.py        # 모든 v1 라우터 집합
│   │   ├── auth.py          # 인증 라우터
│   │   ├── users.py         # 사용자 라우터
│   │   ├── audio.py         # 오디오 샘플 라우터
│   │   └── instruments.py   # 악기 라우터
│   ├── models/              # SQLAlchemy ORM 모델 (DB 테이블 정의)
│   │   ├── base.py          # DeclarativeBase + TimestampMixin
│   │   ├── user.py
│   │   ├── audio_sample.py
│   │   ├── instrument.py
│   │   └── instrument_sample.py
│   ├── schemas/             # Pydantic 요청/응답 스키마 (데이터 검증)
│   │   ├── user.py
│   │   ├── auth.py
│   │   ├── audio_sample.py
│   │   └── instrument.py
│   ├── services/            # 비즈니스 로직 (라우터와 분리)
│   │   ├── auth_service.py
│   │   ├── audio_service.py
│   │   └── instrument_service.py
│   ├── core/
│   │   ├── security.py      # JWT 생성/검증, 비밀번호 해싱
│   │   ├── s3.py            # boto3 S3 클라이언트 래퍼
│   │   └── exceptions.py    # 커스텀 예외 클래스
│   └── db/
│       └── session.py       # SQLAlchemy 엔진 + SessionLocal
├── alembic/                 # DB 마이그레이션 파일
│   └── versions/
├── tests/
│   ├── conftest.py          # 테스트 DB, 클라이언트 픽스처
│   ├── unit/                # 서비스, 보안 로직 단위 테스트
│   └── integration/         # API 엔드포인트 통합 테스트
├── docker/
│   ├── Dockerfile           # 프로덕션 이미지 (멀티 스테이지)
│   └── Dockerfile.dev       # 개발용 이미지 (hot-reload)
├── .github/workflows/
│   ├── ci.yml               # PR마다 pytest 자동 실행
│   └── cd.yml               # main 머지 시 EC2 자동 배포
├── scripts/
│   └── seed_db.py           # 개발용 더미 데이터 삽입
├── .env.example             # 환경변수 템플릿 (커밋 O)
├── .env                     # 실제 시크릿 (커밋 X, .gitignore에 포함)
├── docker-compose.yml       # 로컬 개발: app + postgres
├── requirements.txt         # 프로덕션 의존성
├── requirements-dev.txt     # 개발 + 테스트 의존성
├── alembic.ini
├── pyproject.toml           # 코드 포매터(ruff, black) 설정
└── CLAUDE.md                # 이 파일
```

---

## 데이터베이스 스키마 요약

```
users:            id, email(UNIQUE), username(UNIQUE), hashed_password, is_active
audio_samples:    id, owner_id(FK), filename_original, filename_s3, s3_bucket, mime_type, is_public
instruments:      id, owner_id(FK), name, instrument_type, is_public, config_json(JSONB)
instrument_samples: id, instrument_id(FK), audio_sample_id(FK), note_key, velocity_min, velocity_max
shared_instruments: id, instrument_id(FK), shared_by_user_id(FK), share_token(UNIQUE), is_link_share
```

---

## API 엔드포인트 목록

```
# 인증 (인증 불필요)
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
GET    /api/v1/auth/me          (인증 필요)

# 사용자 (인증 필요)
GET    /api/v1/users/me
PATCH  /api/v1/users/me
DELETE /api/v1/users/me

# 오디오 샘플 (인증 필요)
POST   /api/v1/audio/upload
GET    /api/v1/audio/
GET    /api/v1/audio/{id}
GET    /api/v1/audio/{id}/download   # Pre-signed URL 반환
PATCH  /api/v1/audio/{id}
DELETE /api/v1/audio/{id}

# 악기 (인증 필요, 공유 링크 조회 제외)
POST   /api/v1/instruments/
GET    /api/v1/instruments/
GET    /api/v1/instruments/{id}
PATCH  /api/v1/instruments/{id}
DELETE /api/v1/instruments/{id}
POST   /api/v1/instruments/{id}/samples
DELETE /api/v1/instruments/{id}/samples/{sample_id}
POST   /api/v1/instruments/{id}/share
GET    /api/v1/instruments/shared/{token}   # 인증 불필요

# 헬스체크
GET    /health
```

---

## 환경변수 (.env)

```env
# 데이터베이스
DATABASE_URL=postgresql://user:password@localhost:5432/webdaw

# JWT 시크릿 (생성: python -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# AWS S3
AWS_ACCESS_KEY_ID=your-iam-access-key
AWS_SECRET_ACCESS_KEY=your-iam-secret-key
AWS_REGION=ap-northeast-2
S3_BUCKET_NAME=web-daw-audio-files

# 앱 설정
ENVIRONMENT=development
```

---

## 로컬 실행 방법

```bash
# 1. 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. 의존성 설치
pip install -r requirements-dev.txt

# 3. .env 파일 생성
cp .env.example .env
# .env 파일을 열어 값 입력

# 4. PostgreSQL 실행 (Docker)
docker compose up -d db

# 5. DB 마이그레이션
alembic upgrade head

# 6. 개발 서버 실행 (hot-reload)
uvicorn app.main:app --reload

# 7. 테스트 실행
pytest tests/ -v

# 8. 커버리지 포함 테스트
pytest tests/ --cov=app --cov-report=term-missing
```

---

## 현재 진행 단계

**아래 체크리스트를 진행하면서 직접 업데이트하세요:**

- [x] Phase 0: 환경 설정 (프로젝트 구조, Docker, /health 엔드포인트) → [docs/phase-0.md](docs/phase-0.md)
- [x] Phase 1: DB 기반 구축 (SQLAlchemy 모델, Alembic 마이그레이션) → [docs/phase-1.md](docs/phase-1.md)
- [x] Phase 2: 사용자 인증 (JWT, register, login, get_current_user) → [docs/phase-2.md](docs/phase-2.md)
- [x] Phase 3: S3 오디오 업로드 (boto3, Pre-signed URL) → [docs/phase-3.md](docs/phase-3.md)
- [x] Phase 4: 악기 API (CRUD, 샘플 매핑, 공유) → [docs/phase-4.md](docs/phase-4.md)
- [x] Phase 5: Docker + AWS 배포 (EC2, RDS, 보안 그룹) → [docs/phase-5.md](docs/phase-5.md)
- [x] Phase 6: GitHub Actions CI/CD → [docs/phase-6.md](docs/phase-6.md)
- [ ] Phase 7: 마무리 (페이지네이션, 검증, 로깅, README)

## 문서화 규칙

**각 Phase 완료 시 `docs/phase-N.md`를 작성한다.**
파일에 반드시 포함할 내용:
1. AI 없이 혼자 구축하는 단계별 절차 (명령어 포함)
2. 발생했던 트러블슈팅 (증상 → 원인 → 해결 → 교훈)
3. 백엔드 입문자가 코드 리뷰 시 확인할 포인트
4. Phase 완료 체크리스트
5. 다음 Phase 예고

---

## 코드 스타일 규칙

1. 모든 함수는 파라미터와 반환 타입에 타입 힌트를 붙인다
2. 모든 Pydantic 스키마는 무엇을 나타내는지 docstring을 붙인다
3. 모든 서비스 함수는 Args, Returns, Raises를 포함한 docstring을 붙인다
4. 라우터는 얇게: 입력 검증(Pydantic이 처리) → 서비스 함수 1개 호출 → 결과 반환
5. **라우터 핸들러에서 직접 DB를 쿼리하지 않는다. 항상 서비스를 통한다**
6. 리소스 수정 전 항상 소유권 확인: `resource.owner_id == current_user.id`
7. 사용자가 소유하지 않은 리소스 요청 시 403이 아닌 404 반환 (존재 자체를 노출하지 않음)

---

## API 응답 형식 규약

**목록 엔드포인트:**
```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "limit": 20,
  "pages": 5
}
```

**오류 응답:**
```json
{
  "detail": "사람이 읽을 수 있는 오류 메시지"
}
```

**삭제 성공:**
```json
{
  "message": "삭제되었습니다."
}
```

---

## AWS 인프라 구성

| 서비스 | 사양 | 설정 |
|--------|------|------|
| EC2 | t3.micro (프리티어) | Amazon Linux 2023, 인바운드: 8000 전체, 22 내 IP만 |
| RDS | db.t3.micro (프리티어) | PostgreSQL 15, 인바운드: 5432 EC2 보안 그룹만 (인터넷 차단) |
| S3 | - | 퍼블릭 액세스 전체 차단, Pre-signed URL로만 접근 |
| IAM | 전용 사용자 | 정책: 특정 버킷 ARN에만 s3:PutObject, s3:GetObject, s3:DeleteObject 허용 |

**중요**: 루트 계정 자격증명을 앱에 절대 사용하지 않는다.

---

## Git 브랜치 전략

- `main`: 항상 배포 가능 상태 (CI 통과 후만 머지)
- 기능 브랜치: `feature/phase-2-auth`, `feature/audio-upload` 등
- 커밋 메시지 형식: `feat: JWT 리프레시 토큰 엔드포인트 추가`
  - 접두사: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`

---

## 테스트 전략

**단위 테스트** (`tests/unit/`):
- `security.py` 함수 직접 테스트
- `unittest.mock.patch`로 boto3 mock 처리

**통합 테스트** (`tests/integration/`):
- pytest 픽스처로 테스트 전용 DB 생성 (개발 DB와 분리)
- `httpx.AsyncClient`로 실제 HTTP 요청 테스트
- 각 테스트는 독립적 (테스트 간 DB 롤백 또는 초기화)

**절대 금지**:
- 실제 S3 버킷에 테스트하지 않는다 (항상 mock)
- 프로덕션 DB에 테스트하지 않는다
