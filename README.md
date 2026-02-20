# Web DAW Backend

백엔드 학습을 위한 Web Digital Audio Workstation API 서버.
사용자가 오디오 샘플을 업로드하고 커스텀 악기를 만들어 공유할 수 있다.

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| Framework | Python 3.11 + FastAPI |
| ORM | SQLAlchemy 2.0 + Alembic |
| Database | PostgreSQL 15 |
| Auth | JWT (python-jose + passlib[bcrypt]) |
| Storage | AWS S3 (boto3, Pre-signed URL) |
| Container | Docker + Docker Compose |
| CI/CD | GitHub Actions |
| Cloud | AWS EC2 + RDS + S3 |

## 로컬 실행 방법

### 사전 요구사항
- Python 3.11+
- Docker Desktop
- Git

### 1. 레포 클론

```bash
git clone https://github.com/RealPinkRabbit/web-daw-backend.git
cd web-daw-backend
```

### 2. 가상환경 설정

```bash
python -m venv venv

# macOS/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. 의존성 설치

```bash
pip install -r requirements-dev.txt
```

### 4. 환경변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 값 입력
```

### 5. PostgreSQL + 앱 실행 (Docker Compose)

```bash
# DB + 앱 전체 실행
docker compose up -d

# 또는 DB만 실행 후 로컬에서 앱 실행
docker compose up -d db
uvicorn app.main:app --reload
```

### 6. DB 마이그레이션

```bash
alembic upgrade head
```

API 문서: http://localhost:8000/docs

## 테스트 실행

```bash
# 전체 테스트
pytest tests/ -v

# 커버리지 포함
pytest tests/ --cov=app --cov-report=term-missing
```

## API 엔드포인트

### 인증 (인증 불필요)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/auth/register` | 회원가입 |
| POST | `/api/v1/auth/login` | 로그인 (Access + Refresh Token 발급) |
| POST | `/api/v1/auth/refresh` | Access Token 재발급 |
| GET | `/api/v1/auth/me` | 내 정보 조회 |

### 사용자 (인증 필요)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/v1/users/me` | 내 프로필 조회 |
| PATCH | `/api/v1/users/me` | 내 프로필 수정 |
| DELETE | `/api/v1/users/me` | 회원 탈퇴 |

### 오디오 샘플 (인증 필요)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/audio/upload` | 오디오 파일 업로드 (S3) |
| GET | `/api/v1/audio/` | 내 오디오 목록 |
| GET | `/api/v1/audio/{id}` | 오디오 상세 조회 |
| GET | `/api/v1/audio/{id}/download` | Pre-signed URL로 다운로드 (302 redirect) |
| PATCH | `/api/v1/audio/{id}` | 오디오 정보 수정 |
| DELETE | `/api/v1/audio/{id}` | 오디오 삭제 |

### 악기 (인증 필요, 공유 조회 제외)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/instruments/` | 악기 생성 |
| GET | `/api/v1/instruments/` | 내 악기 목록 |
| GET | `/api/v1/instruments/{id}` | 악기 상세 조회 |
| PATCH | `/api/v1/instruments/{id}` | 악기 수정 |
| DELETE | `/api/v1/instruments/{id}` | 악기 삭제 |
| POST | `/api/v1/instruments/{id}/samples` | 오디오 샘플 매핑 추가 |
| DELETE | `/api/v1/instruments/{id}/samples/{mapping_id}` | 샘플 매핑 제거 |
| POST | `/api/v1/instruments/{id}/share` | 공유 링크 생성/갱신 |
| GET | `/api/v1/instruments/shared/{token}` | 공유 링크로 악기 조회 (인증 불필요) |

### 기타
| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/health` | 헬스체크 |

## 프로젝트 구조

```
app/
  main.py         - 앱 팩토리, 로깅, 미들웨어
  config.py       - 환경변수 설정 (pydantic-settings)
  dependencies.py - get_db, get_current_user
  api/v1/         - API 라우터 (auth, users, audio, instruments)
  models/         - SQLAlchemy ORM 모델
  schemas/        - Pydantic 요청/응답 스키마
  services/       - 비즈니스 로직 (라우터와 분리)
  core/           - security, s3, exceptions
  db/             - DB 세션
tests/
  unit/           - 보안 함수 단위 테스트
  integration/    - API 엔드포인트 통합 테스트
docs/             - Phase별 회고록
```

## 학습 단계

- [x] Phase 0: 환경 설정, /health 엔드포인트 → [docs/phase-0.md](docs/phase-0.md)
- [x] Phase 1: DB 모델, Alembic 마이그레이션 → [docs/phase-1.md](docs/phase-1.md)
- [x] Phase 2: JWT 인증 (register, login) → [docs/phase-2.md](docs/phase-2.md)
- [x] Phase 3: S3 오디오 파일 업로드 → [docs/phase-3.md](docs/phase-3.md)
- [x] Phase 4: 악기 CRUD + 공유 → [docs/phase-4.md](docs/phase-4.md)
- [x] Phase 5: AWS 배포 (EC2 + RDS) → [docs/phase-5.md](docs/phase-5.md)
- [x] Phase 6: GitHub Actions CI/CD → [docs/phase-6.md](docs/phase-6.md)
- [x] Phase 7: 마무리 (로깅, README) → [docs/phase-7.md](docs/phase-7.md)
