import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

# ============================================================
# 로깅 설정
# 개발: DEBUG 레벨 (상세 로그)
# 프로덕션: INFO 레벨 (요청/응답 + 에러만)
# ============================================================
logging.basicConfig(
    level=logging.DEBUG if settings.ENVIRONMENT == "development" else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """앱 시작/종료 시 실행할 작업을 정의한다."""
    logger.info("Web DAW API 시작 (environment=%s)", settings.ENVIRONMENT)
    yield
    logger.info("Web DAW API 종료")


def create_application() -> FastAPI:
    """
    FastAPI 앱 인스턴스를 생성하고 설정하는 팩토리 함수.
    미들웨어 등록과 라우터 마운트를 이 함수에서 처리한다.
    """
    application = FastAPI(
        title="Web DAW API",
        description="오디오 샘플과 커스텀 악기를 관리하는 Web DAW 백엔드 API",
        version="0.1.0",
        lifespan=lifespan,
        # 프로덕션 환경에서는 Swagger UI를 비활성화한다
        docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT == "development" else None,
    )

    # CORS 미들웨어 등록
    # 개발 중에는 모든 출처를 허용하고, 나중에 프로덕션 도메인으로 제한한다
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.ENVIRONMENT == "development" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api.v1.router import api_router
    application.include_router(api_router, prefix="/api/v1")

    return application


app = create_application()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    모든 HTTP 요청/응답을 로깅하는 미들웨어.
    메서드, 경로, 상태 코드, 처리 시간을 기록한다.
    """
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


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """
    서버 상태를 확인하는 헬스체크 엔드포인트.
    AWS ALB 헬스체크와 모니터링에 사용된다.
    """
    return {"status": "ok", "environment": settings.ENVIRONMENT}
