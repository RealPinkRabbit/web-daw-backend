# Phase 7: 마무리 — 회고록

## 목표

프로젝트 전체를 완성도 있게 마무리한다.
로깅을 추가하여 운영 중 문제를 추적할 수 있게 하고,
README를 완성하여 프로젝트를 처음 보는 사람도 바로 실행할 수 있도록 한다.

---

## 변경된 파일

| 파일 | 변경 내용 |
|------|-----------|
| `app/main.py` | 로깅 설정 + 요청 로깅 미들웨어 + lifespan 이벤트 |
| `app/config.py` | Pydantic V2 스타일로 설정 방식 업데이트 |
| `README.md` | API 목록 추가, Phase 3~7 완료 체크, 전체 내용 보강 |

---

## 1. 구현 내용

### 로깅 설정 (`app/main.py`)

```python
import logging

logging.basicConfig(
    level=logging.DEBUG if settings.ENVIRONMENT == "development" else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
```

**환경에 따른 로그 레벨 분리:**
- 개발(`development`): DEBUG — 모든 로그 출력
- 프로덕션(`production`): INFO — 요청/응답 + 에러만 출력

---

### 요청 로깅 미들웨어 (`app/main.py`)

```python
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000

    logger.info(
        "%s %s → %d (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response
```

모든 요청에 대해 아래와 같은 로그가 출력된다:
```
2026-02-20 14:00:00 [INFO] app.main: POST /api/v1/auth/login → 200 (23.4ms)
2026-02-20 14:00:01 [INFO] app.main: GET /api/v1/instruments/ → 200 (8.1ms)
2026-02-20 14:00:02 [INFO] app.main: GET /api/v1/audio/invalid-id → 404 (3.2ms)
```

---

### lifespan 이벤트 (`app/main.py`)

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info("Web DAW API 시작 (environment=%s)", settings.ENVIRONMENT)
    yield
    logger.info("Web DAW API 종료")

app = FastAPI(lifespan=lifespan, ...)
```

`@app.on_event("startup")`은 FastAPI 최신 버전에서 deprecated.
`lifespan` 컨텍스트 매니저가 공식 권장 방식이다.
`yield` 전: 시작 시 실행 / `yield` 후: 종료 시 실행.

---

### Pydantic V2 설정 방식 (`app/config.py`)

```python
# 변경 전 (Pydantic V1 스타일 — deprecated 경고 발생)
class Config:
    env_file = ".env"
    case_sensitive = True

# 변경 후 (Pydantic V2 스타일)
from pydantic_settings import SettingsConfigDict
model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)
```

---

## 2. 코드 리뷰 포인트

### A. 미들웨어 실행 순서

FastAPI에서 미들웨어는 **등록 역순**으로 실행된다.

```python
app.add_middleware(CORSMiddleware, ...)   # 2번째 실행
# ...
@app.middleware("http")                  # 1번째 실행
async def log_requests(...): ...
```

요청이 들어오면: `log_requests` → `CORSMiddleware` → 라우터
응답이 나가면: 라우터 → `CORSMiddleware` → `log_requests`

요청 로깅 미들웨어를 마지막에 등록하면 CORS 처리까지 포함한 전체 시간이 측정된다.

---

### B. `time.perf_counter()` vs `time.time()`

```python
start_time = time.perf_counter()   # 고해상도 타이머 (마이크로초 단위)
# ...
duration_ms = (time.perf_counter() - start_time) * 1000
```

`time.time()`은 벽시계 시간(wall clock)으로 시스템 시간 변경에 영향을 받는다.
`time.perf_counter()`는 단조 증가(monotonic) 고해상도 타이머로 경과 시간 측정에 적합하다.

---

### C. `logging.getLogger(__name__)` 패턴

```python
logger = logging.getLogger(__name__)
```

`__name__`은 현재 모듈의 이름(`app.main`)이 된다.
로그 메시지에 `[app.main]`처럼 출처가 명시되어 어느 파일에서 발생한 로그인지 바로 알 수 있다.
각 파일마다 이 패턴을 사용하면 로그 출처를 쉽게 필터링할 수 있다.

---

### D. `lifespan`의 `yield` 패턴

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: DB 연결 풀 초기화, 캐시 워밍업 등
    logger.info("앱 시작")
    yield
    # shutdown: 연결 종료, 정리 작업 등
    logger.info("앱 종료")
```

이 패턴은 `try/finally`와 동일하게 동작한다.
예외가 발생해도 `yield` 이후 코드(종료 로직)가 반드시 실행된다.
실제 프로덕션에서는 DB 연결 풀 초기화, 외부 서비스 연결 확인 등을 이 단계에서 처리한다.

---

## 3. Phase 완료 체크리스트

- [x] `app/main.py` - 로깅 설정 (환경별 레벨 분리)
- [x] `app/main.py` - 요청/응답 로깅 미들웨어 (메서드, 경로, 상태코드, 처리시간)
- [x] `app/main.py` - `@app.on_event` → `lifespan` 마이그레이션
- [x] `app/config.py` - Pydantic V2 `model_config` 스타일로 업데이트
- [x] `README.md` - 전체 API 엔드포인트 목록, Phase 완료 체크, 실행 방법 보강
- [x] `pytest tests/ -v` → 74개 전부 PASSED

---

## 프로젝트 완료

Phase 0부터 Phase 7까지 Web DAW Backend 프로젝트가 완성되었다.

| Phase | 내용 | 핵심 학습 |
|-------|------|-----------|
| 0 | 환경 설정, /health | FastAPI 앱 팩토리, Docker Compose |
| 1 | DB 모델, 마이그레이션 | SQLAlchemy 2.0, Alembic autogenerate |
| 2 | JWT 인증 | Access/Refresh Token, 의존성 주입 |
| 3 | S3 오디오 업로드 | boto3, Pre-signed URL, 302 redirect |
| 4 | 악기 CRUD + 공유 | 이중 소유권 검사, 토큰 교체, 라우트 순서 |
| 5 | AWS 배포 | EC2 + RDS + S3, Docker 멀티 스테이지 빌드 |
| 6 | GitHub Actions | CI/CD 파이프라인, workflow_run |
| 7 | 마무리 | 로깅, README, 코드 정리 |
