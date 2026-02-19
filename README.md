# Web DAW Backend

백엔드 학습을 위한 Web Digital Audio Workstation API 서버.
사용자가 오디오 샘플을 업로드하고 커스텀 악기를 만들어 공유할 수 있다.

## 기술 스택

- **Framework**: Python + FastAPI
- **Database**: PostgreSQL (SQLAlchemy 2.0 + Alembic)
- **Auth**: JWT (python-jose + passlib[bcrypt])
- **Storage**: AWS S3 (boto3)
- **Container**: Docker + Docker Compose
- **CI/CD**: GitHub Actions
- **Cloud**: AWS (EC2 + RDS + S3)

## 로컬 실행 방법

### 사전 요구사항
- Python 3.11+
- Docker Desktop
- Git

### 1. 레포 클론

```bash
git clone <repo-url>
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

### 5. PostgreSQL 실행

```bash
docker compose up -d db
```

### 6. DB 마이그레이션

```bash
alembic upgrade head
```

### 7. 개발 서버 실행

```bash
uvicorn app.main:app --reload
```

API 문서: http://localhost:8000/docs

## 테스트 실행

```bash
# 전체 테스트
pytest tests/ -v

# 커버리지 포함
pytest tests/ --cov=app --cov-report=term-missing
```

## 프로젝트 구조

```
app/
  main.py         - 앱 팩토리
  config.py       - 환경변수 설정
  dependencies.py - get_db, get_current_user
  api/v1/         - API 라우터
  models/         - SQLAlchemy 모델
  schemas/        - Pydantic 스키마
  services/       - 비즈니스 로직
  core/           - 보안, S3, 예외
  db/             - DB 세션
```

## 학습 단계

- [x] Phase 0: 환경 설정, /health 엔드포인트
- [x] Phase 1: DB 모델, Alembic 마이그레이션
- [x] Phase 2: JWT 인증 (register, login)
- [ ] Phase 3: S3 오디오 파일 업로드
- [ ] Phase 4: 악기 CRUD + 공유
- [ ] Phase 5: AWS 배포 (EC2 + RDS)
- [ ] Phase 6: GitHub Actions CI/CD
- [ ] Phase 7: 마무리 (페이지네이션, 검증, 로깅)
