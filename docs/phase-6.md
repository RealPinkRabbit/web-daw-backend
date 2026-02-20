# Phase 6: GitHub Actions CI/CD — 회고록

## 목표

코드를 push할 때마다 테스트가 자동으로 실행되고,
테스트가 통과하면 EC2에 자동으로 배포되는 파이프라인을 구축한다.

---

## 구현된 파일

| 파일 | 설명 |
|------|------|
| `.github/workflows/ci.yml` | push/PR 시 pytest 자동 실행 |
| `.github/workflows/cd.yml` | CI 통과 후 EC2 자동 배포 |

---

## 1. AI 없이 혼자 구축하는 단계별 절차

### Step 1: ci.yml 작성

```yaml
name: CI - 테스트 자동화

on:
  pull_request:
    branches: [master]
  push:
    branches: [master]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:               # 테스트용 PostgreSQL 컨테이너
        image: postgres:15-alpine
        env:
          POSTGRES_USER: testuser
          POSTGRES_PASSWORD: testpassword
          POSTGRES_DB: webdaw_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - uses: actions/cache@v4        # pip 캐시로 설치 속도 향상
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('requirements-dev.txt') }}
      - run: pip install -r requirements-dev.txt
      - name: pytest 실행
        env:
          TEST_DATABASE_URL: postgresql://testuser:testpassword@localhost:5432/webdaw_test
          SECRET_KEY: test-secret-key-for-ci-not-for-production
          # AWS 자격증명은 fake값 사용 (S3는 mock 처리)
          AWS_ACCESS_KEY_ID: fake-key-for-testing
          AWS_SECRET_ACCESS_KEY: fake-secret-for-testing
          ...
        run: pytest tests/ -v --cov=app --cov-report=xml
```

핵심: `TEST_DATABASE_URL` 환경변수를 설정하면 `conftest.py`가 SQLite 대신 PostgreSQL을 사용한다.
S3 관련 테스트는 `unittest.mock.patch`로 처리하므로 실제 AWS 자격증명이 불필요하다.

---

### Step 2: cd.yml 작성

```yaml
name: CD - EC2 자동 배포

on:
  workflow_run:
    workflows: ["CI - 테스트 자동화"]  # CI 워크플로우 이름과 정확히 일치해야 함
    types: [completed]
    branches: [master]

jobs:
  deploy:
    runs-on: ubuntu-latest
    if: ${{ github.event.workflow_run.conclusion == 'success' }}  # CI 실패 시 배포 안 함

    steps:
      - uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ec2-user
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            cd /home/ec2-user/web-daw-backend
            bash scripts/deploy.sh
```

`workflow_run` 트리거를 사용하면 CI와 CD를 별도 파일로 관리하면서도
CI 성공 여부에 따라 CD 실행을 제어할 수 있다.

---

### Step 3: GitHub Secrets 설정

> GitHub 저장소 → Settings → Secrets and variables → Actions → New repository secret

| Secret 이름 | 값 |
|------------|-----|
| `EC2_HOST` | EC2 퍼블릭 IP (예: `13.125.xxx.xxx`) |
| `EC2_SSH_KEY` | `web-daw-key.pem` 파일 전체 내용 |

pem 파일 내용 확인:
```bash
cat web-daw-key.pem
```

`-----BEGIN RSA PRIVATE KEY-----` 부터 `-----END RSA PRIVATE KEY-----` 까지 전부 복사한다.

---

### Step 4: EC2 보안 그룹 SSH 규칙 수정

> AWS 콘솔 → EC2 → 보안 그룹 → `web-daw-ec2-sg` → 인바운드 규칙 편집

| 항목 | 변경 전 | 변경 후 |
|------|---------|---------|
| SSH 소스 | 내 IP | 위치 무관 (0.0.0.0/0) |

GitHub Actions 서버는 실행할 때마다 IP가 달라지므로 특정 IP를 허용할 수 없다.
키 페어(`.pem`)가 없으면 접속 자체가 불가능하므로 실습 수준에서 허용 가능하다.

---

### Step 5: 동작 확인

```
코드 push
  → CI 워크플로우 실행 (pytest, ~2분)
  → 통과 시 CD 워크플로우 트리거
  → EC2 SSH 접속 → deploy.sh 실행
  → /health 확인
```

> GitHub 저장소 → Actions 탭에서 실시간 확인 가능

---

## 2. 트러블슈팅

### 문제 1: `Error: missing server host`

**증상**: CD 워크플로우 첫 실행 시 SSH 접속 전에 바로 실패
**원인**: `EC2_HOST` Secret의 Value 칸이 비어있음
(처음 Secret 생성 시 Name만 입력하고 Secret(Value) 칸을 비워둔 경우)
**해결**: Secret 수정 → Value 칸에 EC2 퍼블릭 IP 입력 → Update secret
**교훈**: Secret 생성 시 Name과 Secret(값) 두 칸을 모두 채워야 한다

---

### 문제 2: `dial tcp ***:22: i/o timeout`

**증상**: SSH 접속 단계에서 타임아웃
**원인**: EC2 보안 그룹의 SSH 인바운드 규칙이 "내 IP"만 허용
→ GitHub Actions 서버 IP는 매번 달라 차단됨
**해결**: EC2 보안 그룹 SSH 소스를 `0.0.0.0/0`(위치 무관)으로 변경
**교훈**: GitHub Actions는 고정 IP가 없으므로 SSH 소스를 전체 허용해야 한다

---

### 문제 3: `test_decode_tampered_token_raises_error` 테스트 실패

**증상**: CI 실행 전 로컬에서 74개 중 1개 실패
**원인**: JWT 토큰의 마지막 문자를 변경하는 방식은 base64 패딩 특성상
실제 서명 바이트에 영향을 주지 않아 JWTError가 발생하지 않음
**해결**: 페이로드(두 번째 세그먼트)를 변조하는 방식으로 수정
```python
# 변경 전: 토큰 마지막 문자 변경 (비신뢰성)
tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

# 변경 후: 페이로드 세그먼트 변조 (서명과 불일치 보장)
header, payload, signature = token.split(".")
tampered_payload = payload[:-1] + ("A" if payload[-1] != "A" else "B")
tampered = f"{header}.{tampered_payload}.{signature}"
```
**교훈**: JWT 변조 테스트는 서명 대상인 페이로드를 수정해야 신뢰성이 보장된다

---

## 3. 코드 리뷰 포인트

### A. CI와 CD를 별도 파일로 분리한 이유

```
ci.yml  → push/PR 시 항상 실행 (테스트만)
cd.yml  → CI 성공 시에만 실행 (배포)
```

하나의 파일에 합치면 PR 시에도 배포가 시도될 수 있다.
분리하면 각 파일의 책임이 명확해지고, CI는 PR에서도 실행되지만 CD는 master push 후 CI 통과 시에만 실행된다.

---

### B. `workflow_run` vs `needs`

```yaml
# 방법 1: 같은 파일 내 needs (단순하지만 파일 분리 불가)
jobs:
  test: ...
  deploy:
    needs: test   # test 완료 후 실행

# 방법 2: workflow_run (파일 분리 가능)
on:
  workflow_run:
    workflows: ["CI - 테스트 자동화"]
    types: [completed]
```

`workflow_run`은 다른 워크플로우의 완료를 트리거로 사용한다.
`if: ${{ github.event.workflow_run.conclusion == 'success' }}`로 성공 여부를 체크한다.

---

### C. CI에서 PostgreSQL 서비스 컨테이너 사용

```yaml
services:
  postgres:
    image: postgres:15-alpine
    ...
    ports:
      - 5432:5432
```

로컬 테스트는 SQLite를 사용하지만, CI는 PostgreSQL을 사용한다.
`conftest.py`에서 `TEST_DATABASE_URL` 환경변수를 읽어 DB를 결정하므로
CI 환경변수만 바꾸면 코드 수정 없이 PostgreSQL로 테스트할 수 있다.
실제 프로덕션 DB와 동일한 환경에서 테스트하므로 신뢰성이 높다.

---

### D. GitHub Secrets가 워크플로우 로그에서 `***`로 마스킹되는 이유

```
host: ***
key: ***
```

Secrets에 저장된 값은 로그에 출력될 때 자동으로 `***`로 대체된다.
코드에 하드코딩하거나 일반 환경변수로 넘기면 로그에 그대로 노출된다.
민감한 값은 반드시 Secrets에 저장해야 한다.

---

### E. pip 캐시로 CI 속도 향상

```yaml
- uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('requirements-dev.txt') }}
```

`requirements-dev.txt`가 변경되지 않으면 이전에 다운로드한 패키지를 재사용한다.
패키지 설치 시간(~30초)을 캐시 복원 시간(~5초)으로 단축한다.

---

## 4. Phase 완료 체크리스트

- [x] `.github/workflows/ci.yml` - pytest 자동 실행 (PostgreSQL 서비스 컨테이너)
- [x] `.github/workflows/cd.yml` - CI 통과 후 EC2 자동 배포 (`workflow_run`)
- [x] GitHub Secrets 설정 (`EC2_HOST`, `EC2_SSH_KEY`)
- [x] EC2 보안 그룹 SSH 소스 0.0.0.0/0으로 변경
- [x] `test_decode_tampered_token_raises_error` 테스트 버그 수정
- [x] Actions 탭에서 CI/CD 전체 파이프라인 성공 확인

---

## 5. 다음 Phase 예고

**Phase 7: 마무리**

- 페이지네이션 응답 형식 통일 검토
- 로깅 설정 (uvicorn 액세스 로그, 앱 레벨 로깅)
- README.md 작성 (프로젝트 소개, 실행 방법, API 목록)
- 전체 코드 최종 점검
