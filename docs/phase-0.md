# Phase 0 - 환경 설정 회고록

> **목표**: 프로젝트 구조를 잡고, 로컬 개발 환경을 구성하고, `GET /health`가 DB와 함께 정상 동작하는 것을 확인한다.

---

## 1. AI 없이 혼자 처음부터 구축하는 방법 (단계별 절차)

### 사전 설치 프로그램

| 프로그램 | 설치 방법 | 용도 |
|---------|-----------|------|
| Python 3.11+ | python.org 다운로드 | 백엔드 언어 |
| Docker Desktop | [docker.com](https://www.docker.com/products/docker-desktop/) 또는 `winget install Docker.DockerDesktop` | 로컬 PostgreSQL 실행 |
| Git | git-scm.com | 버전 관리 |
| GitHub CLI (`gh`) | `winget install GitHub.cli` | GitHub 레포 생성/관리 |
| VS Code (권장) | vscode 공식 사이트 | 코드 에디터 |

> **Docker Desktop 설치 시 주의:**
> - "Allow Windows Containers" → **체크하지 않음** (Linux 컨테이너만 사용)
> - Work / Personal 선택 → **Personal**
> - 로그인 → 스킵 가능 (공개 이미지만 사용하므로)

---

### Step 1. GitHub 레포 생성

```bash
# gh CLI 인증 (브라우저 로그인 방식)
gh auth login
# → GitHub.com → HTTPS → Login with a web browser 선택

# 로컬 프로젝트 폴더 생성
mkdir web-daw-backend
cd web-daw-backend

# git 초기화 + 첫 커밋 + GitHub 레포 생성 + push를 한 번에
git init
git add .
git commit -m "feat: 프로젝트 초기 설정"
gh repo create web-daw-backend --public --source=. --remote=origin --push
```

---

### Step 2. 프로젝트 디렉토리 구조 생성

```
web-daw-backend/
├── app/
│   ├── api/v1/          # 라우터 (auth.py, users.py, ...)
│   ├── core/            # 보안, S3, 예외
│   ├── db/              # DB 세션
│   ├── models/          # SQLAlchemy ORM 모델
│   ├── schemas/         # Pydantic 스키마
│   ├── services/        # 비즈니스 로직
│   ├── config.py        # 환경변수 설정
│   ├── dependencies.py  # get_db, get_current_user
│   └── main.py          # 앱 팩토리
├── alembic/             # DB 마이그레이션
├── tests/               # 테스트
├── docker/              # Dockerfile
├── .github/workflows/   # CI/CD
├── .env.example
├── .gitignore
├── alembic.ini
├── docker-compose.yml
├── requirements.txt
└── requirements-dev.txt
```

```bash
# 필요한 디렉토리 한 번에 생성 (bash)
mkdir -p app/api/v1 app/core app/db app/models app/schemas app/services \
         alembic/versions tests/unit tests/integration \
         docker .github/workflows scripts docs
```

---

### Step 3. 주요 파일 작성

#### `app/main.py` - 앱 팩토리 패턴
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

def create_application() -> FastAPI:
    application = FastAPI(
        title="Web DAW API",
        docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
    )
    application.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
    from app.api.v1.router import api_router
    application.include_router(api_router, prefix="/api/v1")
    return application

app = create_application()

@app.get("/health")
async def health_check():
    return {"status": "ok", "environment": settings.ENVIRONMENT}
```

#### `app/config.py` - 환경변수 관리
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    AWS_REGION: str = "ap-northeast-2"
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"

settings = Settings()
```

#### `.env` 파일 생성 (`.gitignore`에 반드시 포함)
```bash
# SECRET_KEY 생성
python -c "import secrets; print(secrets.token_hex(32))"

# .env 파일 내용
DATABASE_URL=postgresql://webdaw_user:webdaw_password@localhost:5432/webdaw
SECRET_KEY=<위에서 생성한 값>
ENVIRONMENT=development
```

#### `docker-compose.yml` - 로컬 PostgreSQL
```yaml
services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: webdaw_user
      POSTGRES_PASSWORD: webdaw_password
      POSTGRES_DB: webdaw
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U webdaw_user -d webdaw"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

---

### Step 4. Python 가상환경 + 의존성 설치

```bash
# 가상환경 생성
python -m venv venv

# 활성화
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 의존성 설치
pip install -r requirements-dev.txt
```

#### `requirements.txt` 핵심 패키지
```
fastapi==0.111.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.31
alembic==1.13.2
psycopg2-binary==2.9.11   # Python 3.13 이상은 2.9.11+
pydantic-settings==2.3.4
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
boto3==1.34.144
python-multipart==0.0.9
```

---

### Step 5. SQLAlchemy 모델 작성

```python
# app/models/base.py
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
from sqlalchemy import DateTime, func
from datetime import datetime

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

```python
# app/models/user.py  (핵심 구조만)
import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    ...
```

---

### Step 6. Alembic 마이그레이션 설정

```bash
# Alembic 초기화 (이미 alembic/ 폴더가 있으면 생략)
alembic init alembic

# alembic/env.py 수정: 모델을 import하고 DATABASE_URL을 settings에서 읽도록 설정
# alembic.ini: 한글 주석 금지 (Windows cp949 인코딩 문제)

# 마이그레이션 파일 자동 생성
alembic revision --autogenerate -m "initial_tables"

# DB에 적용
alembic upgrade head

# 현재 상태 확인
alembic current

# 이전 버전으로 롤백 (필요 시)
alembic downgrade -1
```

---

### Step 7. 서버 실행 + 확인

```bash
# PostgreSQL 실행
docker compose up -d db

# 마이그레이션 적용
alembic upgrade head

# 개발 서버 실행 (--reload: 코드 변경 시 자동 재시작)
uvicorn app.main:app --reload

# 확인
curl http://localhost:8000/health
# → {"status":"ok","environment":"development"}

# Swagger UI: http://localhost:8000/docs
```

---

### Step 8. GitHub push + .gitignore 확인

```bash
# .gitignore에 반드시 포함되어야 할 것들
.env          # 시크릿 절대 커밋 금지
venv/         # 가상환경
__pycache__/
*.pyc

# .env.example은 커밋 O (시크릿 없는 템플릿)
.env.example  → 커밋 O

git add .
git commit -m "feat: Phase 0 완료"
git push
```

---

## 2. 중간에 발생했던 어려움

### 문제 1: `psycopg2-binary` Python 3.13 미지원

- **증상**: `pip install -r requirements.txt` 실행 시 `pg_config executable not found` 에러
- **원인**: `psycopg2-binary==2.9.9`가 Python 3.13용 바이너리 휠을 제공하지 않아 소스에서 빌드를 시도. 소스 빌드는 PostgreSQL 클라이언트 라이브러리가 필요한데 없어서 실패.
- **해결**: `psycopg2-binary==2.9.11`로 업그레이드 (Python 3.13 휠 제공)
- **교훈**: 새로운 Python 버전에서 바이너리 패키지는 반드시 최신 버전 확인 필요

```bash
# 사용 가능한 버전 확인
pip index versions psycopg2-binary
```

---

### 문제 2: `alembic.ini` 한글 주석 UnicodeDecodeError

- **증상**: `alembic revision --autogenerate` 실행 시 `UnicodeDecodeError: 'cp949' codec can't decode byte 0xec`
- **원인**: Windows 한국어 환경의 기본 인코딩은 `cp949`. Alembic이 `alembic.ini`를 `locale` 인코딩으로 읽는데, 파일에 UTF-8 한글 주석이 있어서 충돌.
- **해결**: `alembic.ini`에서 한글 주석 전부 제거
- **교훈**: `.ini` / `.cfg` 같은 설정 파일에는 ASCII 범위 문자만 사용. Windows 개발 환경에서는 특히 주의.

---

### 문제 3: Docker가 MSYS(Git Bash) 환경에서 PATH 미인식

- **증상**: Git Bash에서 `docker` 명령어가 `command not found`
- **원인**: Docker Desktop 설치 후 Windows PATH에는 등록되지만, MSYS 셸 세션은 재시작 전까지 새 PATH를 반영하지 않음
- **해결**: 터미널을 새로 열거나 Docker Desktop이 실행된 상태에서 PowerShell 사용
- **교훈**: 설치 후 환경변수 변경은 터미널 재시작 또는 `source ~/.bashrc`가 필요

---

### 문제 4: 포트 8000 이미 사용 중 (WinError 10048)

- **증상**: 서버를 두 번 실행하면 `[WinError 10048] 한 소켓 주소는 하나의 프로세스만 사용할 수 있습니다`
- **원인**: 이전 uvicorn 프로세스가 백그라운드에서 계속 실행 중
- **해결**: `taskkill /f /im python.exe` 또는 작업 관리자에서 종료. 또는 다른 포트 사용 `--port 8001`
- **교훈**: 개발 중 서버를 자주 끄고 켤 때는 프로세스 정리 습관이 필요

---

## 3. 백엔드 입문자 코드 리뷰 포인트

### A. 앱 팩토리 패턴 (`app/main.py`)

```python
def create_application() -> FastAPI:
    ...
    return application

app = create_application()
```

- `app = FastAPI()`를 직접 쓰지 않고 **함수로 감싼 이유**: 테스트에서 앱 인스턴스를 새로 만들기 쉽고, 설정을 유연하게 변경 가능
- 프로덕션에서는 `docs_url=None`으로 Swagger UI를 비활성화하는 것이 보안상 좋음

---

### B. 환경변수 관리 (`app/config.py`)

```python
class Settings(BaseSettings):
    DATABASE_URL: str      # 기본값 없음 = 필수값
    SECRET_KEY: str        # 기본값 없음 = 필수값
    ENVIRONMENT: str = "development"  # 기본값 있음 = 선택값
```

- **하드코딩 금지**: 비밀번호, API 키, JWT Secret을 코드에 직접 쓰면 GitHub에 올라가는 순간 노출됨
- `.env` 파일은 반드시 `.gitignore`에 추가. `.env.example`(빈 템플릿)만 커밋
- `SECRET_KEY`는 `secrets.token_hex(32)`로 생성한 랜덤 값 사용

---

### C. SQLAlchemy 모델 설계 (`app/models/`)

```python
# UUID 기본키 사용
id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
```

- **왜 UUID?**: 정수 ID(1, 2, 3...)는 `/users/1`, `/users/2`처럼 예측 가능해서 존재하지 않는 리소스를 순서대로 탐색하는 "열거 공격"에 취약
- **소프트 삭제**: `is_active = False`로 비활성화하면 데이터를 보존하면서 삭제 효과를 줄 수 있음 (로그, 감사 목적)
- `TimestampMixin`으로 `created_at`, `updated_at`을 모든 테이블에 자동 추가

---

### D. Alembic 마이그레이션 (`alembic/`)

```bash
# 올바른 워크플로우
# 1. models/*.py 수정
# 2. 마이그레이션 파일 생성
alembic revision --autogenerate -m "add_profile_image_to_users"
# 3. 생성된 파일 확인 (자동 생성이 완벽하지 않을 수 있음!)
# 4. DB에 적용
alembic upgrade head
```

- **절대로** DB를 직접 수정하지 않는다. 항상 마이그레이션 파일을 통해서만 스키마를 변경한다
- `alembic/versions/` 폴더의 파일들은 반드시 git에 커밋 (팀원 모두가 같은 스키마를 사용해야 함)
- `--autogenerate`가 모든 변경을 감지하지 못하는 경우도 있으므로 생성된 파일을 꼭 열어서 확인

---

### E. Docker Compose (`docker-compose.yml`)

```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U webdaw_user -d webdaw"]
  interval: 10s
  retries: 5
```

- **healthcheck의 역할**: `app` 서비스가 `db`가 준비되기 전에 시작하면 연결 에러가 남. `depends_on: condition: service_healthy`와 함께 쓰면 DB가 완전히 준비된 후에만 앱이 시작됨
- `volumes: postgres_data`: 컨테이너를 재시작해도 DB 데이터가 사라지지 않음. 이 줄이 없으면 `docker compose down` 시 데이터 전부 삭제됨

---

### F. `.gitignore` 필수 항목

```gitignore
.env              # 시크릿 (가장 중요!)
venv/             # 가상환경 (용량 크고 각자 설치해야 함)
__pycache__/      # Python 컴파일 캐시
*.pyc
.pytest_cache/
.coverage
```

- `.env`가 한 번이라도 커밋되면 GitHub 히스토리에 남음. 즉시 `SECRET_KEY`와 AWS 키를 재발급해야 함
- `venv/`는 절대 커밋 금지. 수백 MB의 파일이 올라가고, 각 팀원은 `pip install -r requirements.txt`로 각자 설치해야 함

---

## 4. Phase 0 완료 체크리스트

- [x] GitHub 레포 생성 (Public) + 첫 커밋 push
- [x] Python 가상환경 + 의존성 설치 (`requirements-dev.txt`)
- [x] `.env` 파일 생성 (SECRET_KEY 포함)
- [x] `docker compose up -d db` → PostgreSQL `healthy` 상태 확인
- [x] `alembic revision --autogenerate` → 5개 테이블 감지 확인
- [x] `alembic upgrade head` → DB에 테이블 생성 완료
- [x] `uvicorn app.main:app --reload` → 서버 실행
- [x] `GET /health` → `{"status":"ok","environment":"development"}` 응답 확인
- [x] `http://localhost:8000/docs` → Swagger UI 접속 확인

---

## 5. 다음 단계: Phase 1

Phase 1에서는 이미 생성된 DB 모델과 마이그레이션을 바탕으로 **사용자 인증(JWT)**을 구현합니다.

- `POST /api/v1/auth/register` - 회원가입
- `POST /api/v1/auth/login` - 로그인 → JWT 발급
- `GET /api/v1/auth/me` - 내 정보 조회 (토큰 필요)
