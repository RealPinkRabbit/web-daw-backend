# Phase 5: Docker + AWS 배포 — 회고록

## 목표

로컬에서 작동하는 FastAPI 앱을 AWS 인프라(EC2 + RDS + S3)에 Docker 컨테이너로 배포한다.
이 Phase는 **실제 AWS 작업이 포함**되므로, 아래 절차를 순서대로 따라야 한다.

---

## 구현된 파일

| 파일 | 설명 |
|------|------|
| `docker/Dockerfile` | 프로덕션 멀티 스테이지 빌드 이미지 |
| `docker/Dockerfile.dev` | 개발용 hot-reload 이미지 |
| `docker-compose.yml` | 로컬 개발 (app + postgres) |
| `docker-compose.prod.yml` | EC2 배포용 (app만, DB는 RDS) |
| `.dockerignore` | 이미지에서 제외할 파일 목록 |
| `scripts/deploy.sh` | EC2에서 실행하는 배포 자동화 스크립트 |

---

## 1. AI 없이 혼자 구축하는 단계별 절차

### PART A: AWS 인프라 구성

#### A-1. IAM 사용자 생성 (최소 권한 원칙)

> AWS 콘솔 → IAM → 사용자 → 사용자 생성

**중요**: 루트 계정 자격증명을 절대 앱에 사용하지 않는다.

1. 사용자 이름: `web-daw-app` (또는 원하는 이름)
2. 권한: 인라인 정책으로 **특정 S3 버킷만** 허용
3. 액세스 키 생성 (CLI용)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::web-daw-audio-files-yourname/*"
    }
  ]
}
```

생성 후 **Access Key ID**와 **Secret Access Key**를 저장해둔다 (다시 볼 수 없음).

---

#### A-2. S3 버킷 생성

> AWS 콘솔 → S3 → 버킷 만들기

```
버킷 이름: web-daw-audio-files-yourname  (전 세계에서 고유해야 함)
리전: ap-northeast-2 (서울)
퍼블릭 액세스: 모든 퍼블릭 액세스 차단 (체크)
```

- 퍼블릭 URL로 직접 접근 불가 → Pre-signed URL로만 접근 가능
- 버킷 정책이나 ACL은 건드리지 않는다 (기본 비공개 유지)

---

#### A-3. RDS PostgreSQL 생성

> AWS 콘솔 → RDS → 데이터베이스 생성

```
엔진: PostgreSQL 15.x
템플릿: 프리 티어
식별자: web-daw-db
마스터 사용자: webdaw_user
마스터 암호: (강력한 암호 설정)
인스턴스 클래스: db.t3.micro
스토리지: 20GB (gp2)
퍼블릭 액세스: 아니오 (EC2에서만 접근)
VPC 보안 그룹: 새로 생성 (web-daw-rds-sg)
초기 데이터베이스 이름: webdaw
```

생성 완료 후 **엔드포인트** 메모:
```
your-db-identifier.xxxxxxxx.ap-northeast-2.rds.amazonaws.com
```

---

#### A-4. EC2 인스턴스 생성

> AWS 콘솔 → EC2 → 인스턴스 시작

```
이름: web-daw-server
AMI: Amazon Linux 2023
인스턴스 유형: t3.micro (프리 티어)
키 페어: 새 키 페어 생성 (web-daw-key.pem 다운로드)
보안 그룹: 새로 생성 (web-daw-ec2-sg)
```

**보안 그룹 인바운드 규칙:**

| 유형 | 포트 | 소스 | 목적 |
|------|------|------|------|
| SSH | 22 | 내 IP | 서버 관리 |
| 사용자 정의 TCP | 8000 | 0.0.0.0/0 | API 서버 접근 |

---

#### A-5. 보안 그룹 연결 (EC2 → RDS 연결 허용)

> RDS 보안 그룹(web-daw-rds-sg) → 인바운드 규칙 편집

| 유형 | 포트 | 소스 |
|------|------|------|
| PostgreSQL | 5432 | EC2 보안 그룹 ID (web-daw-ec2-sg) |

이렇게 하면 EC2에서만 RDS에 접속 가능하고, 인터넷에서 직접 DB 접근은 차단된다.

---

### PART B: EC2 서버 설정

#### B-1. EC2 SSH 접속

```bash
# 키 파일 권한 설정 (Linux/Mac)
chmod 400 web-daw-key.pem

# SSH 접속
ssh -i web-daw-key.pem ec2-user@<EC2-퍼블릭-IP>
```

---

#### B-2. Docker 설치 (Amazon Linux 2023)

```bash
# 패키지 업데이트
sudo dnf update -y

# Docker 설치
sudo dnf install -y docker

# Docker 서비스 시작 및 자동 시작 설정
sudo systemctl start docker
sudo systemctl enable docker

# ec2-user를 docker 그룹에 추가 (sudo 없이 docker 실행)
sudo usermod -aG docker ec2-user

# 변경사항 적용을 위해 재접속
exit
ssh -i web-daw-key.pem ec2-user@<EC2-퍼블릭-IP>

# Docker 동작 확인
docker --version
docker ps
```

---

#### B-3. Docker Compose 설치

```bash
# Docker Compose 플러그인 설치 (Docker v2 방식)
sudo dnf install -y docker-compose-plugin

# 확인
docker compose version
```

---

#### B-4. 저장소 클론

```bash
# Git 설치 (보통 기본 설치됨)
git --version

# 저장소 클론
git clone https://github.com/RealPinkRabbit/web-daw-backend.git
cd web-daw-backend
```

---

#### B-5. 환경변수 파일 생성

```bash
# 템플릿 복사
cp .env.example .env.prod

# 편집
nano .env.prod
```

`.env.prod` 내용 예시:

```env
# DB (RDS 엔드포인트 사용)
DATABASE_URL=postgresql://webdaw_user:YOUR_STRONG_PASSWORD@your-db-identifier.xxxxxxxx.ap-northeast-2.rds.amazonaws.com:5432/webdaw

# JWT (새로운 시크릿 생성: python3 -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=your-64-char-hex-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# AWS S3 (IAM 사용자 자격증명)
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=ap-northeast-2
S3_BUCKET_NAME=web-daw-audio-files-yourname

# 앱 설정 (production으로 설정 → Swagger UI 비활성화)
ENVIRONMENT=production
```

**주의**: `.env.prod`는 절대 git에 커밋하지 않는다. `.gitignore`에 이미 포함됨.

---

#### B-6. 배포 스크립트 실행

```bash
# 실행 권한 부여
chmod +x scripts/deploy.sh

# 배포 실행
bash scripts/deploy.sh
```

스크립트가 수행하는 작업:
1. `git pull` 또는 첫 클론
2. `.env.prod` 파일 존재 확인
3. Docker 이미지 빌드
4. Alembic DB 마이그레이션 실행
5. 앱 컨테이너 시작
6. `/health` 엔드포인트 헬스체크

---

#### B-7. 배포 확인

```bash
# 컨테이너 상태 확인
docker compose -f docker-compose.prod.yml ps

# 실시간 로그 확인
docker compose -f docker-compose.prod.yml logs -f app

# 헬스체크 (서버에서)
curl http://localhost:8000/health

# 외부에서 확인 (로컬 PC 브라우저)
# http://<EC2-퍼블릭-IP>:8000/health
```

---

### PART C: 이후 배포 (코드 업데이트 시)

```bash
# EC2에서
cd ~/web-daw-backend
bash scripts/deploy.sh
```

스크립트가 git pull → 빌드 → 마이그레이션 → 재시작을 자동으로 처리한다.

---

## 2. 트러블슈팅

### 문제 1: RDS 연결 실패 (`could not connect to server`)

**증상**: 앱 시작 시 `OperationalError: could not connect to server`
**원인**: EC2 보안 그룹이 RDS 보안 그룹에 허용되지 않음
**해결**: RDS 보안 그룹 인바운드 규칙에 EC2 보안 그룹 ID를 추가
**확인 방법**: EC2에서 `nc -zv <RDS-엔드포인트> 5432` 로 연결 테스트

---

### 문제 2: Docker 빌드 시 `psycopg2` 컴파일 오류

**증상**: `Error: pg_config executable not found`
**원인**: `psycopg2` 빌드에 PostgreSQL 개발 헤더 필요
**해결**: `Dockerfile`의 빌더 스테이지에 `libpq-dev`가 이미 포함됨 (정상)
**대안**: `psycopg2-binary` 사용 시 컴파일 불필요 (현재 requirements.txt에서 binary 사용)

---

### 문제 3: S3 업로드 실패 (`NoCredentialsError`)

**증상**: 파일 업로드 시 `botocore.exceptions.NoCredentialsError`
**원인**: `.env.prod`의 AWS 자격증명이 누락되거나 잘못됨
**해결**: `.env.prod`에서 `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` 확인
**확인 방법**: EC2에서 `aws sts get-caller-identity --region ap-northeast-2` (AWS CLI 필요)

---

### 문제 4: Alembic 마이그레이션 실패 (`relation already exists`)

**증상**: `alembic upgrade head` 시 테이블 중복 오류
**원인**: 이미 마이그레이션이 적용된 DB에 재실행
**해결**: 정상 동작 — Alembic은 `alembic_version` 테이블로 현재 버전을 추적하므로 이미 적용된 마이그레이션은 건너뜀

---

### 문제 5: Docker 컨테이너가 `unhealthy` 상태

**증상**: `docker compose ps`에서 앱 컨테이너가 `unhealthy`
**원인**: 앱이 시작됐지만 `/health` 엔드포인트가 응답하지 않음
**해결**:
```bash
# 컨테이너 로그 확인
docker compose -f docker-compose.prod.yml logs --tail=100 app

# DB 연결 문제라면 DATABASE_URL 확인
# 포트 충돌이라면 8000번 포트 사용 여부 확인
sudo lsof -i :8000
```

---

## 3. 코드 리뷰 포인트

### A. 멀티 스테이지 빌드의 이점

```dockerfile
# Stage 1: 빌더 (gcc, libpq-dev 필요 — 컴파일용)
FROM python:3.11-slim AS builder
RUN apt-get install -y gcc libpq-dev
RUN pip install --prefix=/install -r requirements.txt

# Stage 2: 런타임 (libpq5만 필요 — 런타임용)
FROM python:3.11-slim AS runtime
RUN apt-get install -y libpq5            # 빌드 도구 제외!
COPY --from=builder /install /usr/local  # 설치된 패키지만 복사
```

**결과**: 빌더 스테이지(~500MB)가 최종 이미지에서 제외 → 런타임 이미지 크기 대폭 감소

---

### B. 비루트 사용자 실행 (보안)

```dockerfile
RUN useradd --create-home --shell /bin/bash appuser
USER appuser
COPY --chown=appuser:appuser . .
```

컨테이너 내부에서 root로 실행하면 컨테이너 탈출(container escape) 취약점 발생 시 위험.
비루트 사용자로 실행하면 피해 범위를 최소화한다.

---

### C. `.dockerignore`의 역할

```
venv/      # 수백 MB의 가상환경 — 컨테이너 안에서 재설치하므로 불필요
.env       # 시크릿이 이미지 레이어에 포함되면 `docker history`로 노출 가능
tests/     # 프로덕션 이미지에 테스트 코드 불필요
.git/      # Git 이력이 이미지에 포함될 필요 없음
```

`.dockerignore` 없이 빌드하면 `COPY . .` 명령이 `venv/`(수백 MB)를 통째로 포함해
이미지 크기가 폭발적으로 증가한다.

---

### D. 환경별 설정 분리 (`ENVIRONMENT` 변수)

```python
# app/main.py
docs_url="/docs" if settings.ENVIRONMENT == "development" else None
```

`ENVIRONMENT=production`으로 설정하면:
- Swagger UI(`/docs`) 비활성화 → API 스키마 노출 차단
- CORS origins를 빈 리스트로 제한 (현재는 `[]`로만 설정됨)

프로덕션에서는 `allow_origins`에 실제 프론트엔드 도메인을 추가해야 한다.

---

### E. Pre-signed URL이 서버 부하를 줄이는 이유

```
클라이언트 → API /audio/{id}/download → 302 redirect → S3 direct download
         ↑ 인증만 처리 (경량)           ↑ 실제 파일 전송은 S3가 담당
```

오디오 파일은 대용량(수 MB ~ 수백 MB)이다.
API 서버가 직접 프록시하면 t3.micro의 네트워크 대역폭이 순식간에 포화된다.
Pre-signed URL 방식은 S3가 직접 파일을 전송하므로 EC2 부하가 없다.

---

### F. DB 마이그레이션 분리 실행

```bash
# 배포 스크립트에서 마이그레이션을 별도 컨테이너로 실행
docker compose -f docker-compose.prod.yml run --rm app \
    sh -c "alembic upgrade head"
```

앱 컨테이너 시작 전에 마이그레이션을 완료한다.
만약 앱 `CMD`에 마이그레이션을 포함하면 (`alembic upgrade head && uvicorn ...`):
- 수평 확장 시 여러 컨테이너가 동시에 마이그레이션 실행 → 충돌 가능
- 마이그레이션 실패 시 앱 자체가 시작 불가 (문제 진단 어려움)

---

## 4. Phase 완료 체크리스트

- [x] `docker/Dockerfile` - 멀티 스테이지 프로덕션 이미지
- [x] `docker/Dockerfile.dev` - 개발용 hot-reload 이미지
- [x] `docker-compose.yml` - 로컬 개발 (app + db)
- [x] `docker-compose.prod.yml` - EC2 배포용 (app만)
- [x] `.dockerignore` - 이미지 최적화
- [x] `scripts/deploy.sh` - EC2 자동 배포 스크립트
- [ ] AWS EC2 생성 및 Docker 설치 완료
- [ ] AWS RDS PostgreSQL 생성 완료
- [ ] AWS S3 버킷 생성 완료
- [ ] AWS IAM 사용자 및 최소 권한 정책 설정 완료
- [ ] 보안 그룹 설정 완료 (EC2 → RDS 포트 허용)
- [ ] EC2에 `.env.prod` 파일 생성 완료
- [ ] `bash scripts/deploy.sh` 실행 후 `/health` 정상 응답 확인

---

## 5. 다음 Phase 예고

**Phase 6: GitHub Actions CI/CD**

- `.github/workflows/ci.yml`: PR마다 `pytest` 자동 실행
- `.github/workflows/cd.yml`: `main` 브랜치 머지 시 EC2 자동 배포
  - GitHub Secrets에 EC2 SSH 키, AWS 자격증명 저장
  - `appleboy/ssh-action`으로 EC2에 SSH 접속 후 `deploy.sh` 실행
- 테스트 → 배포까지 완전 자동화 파이프라인 구축
