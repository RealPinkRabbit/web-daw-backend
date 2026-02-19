from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings


def create_application() -> FastAPI:
    """
    FastAPI 앱 인스턴스를 생성하고 설정하는 팩토리 함수.
    미들웨어 등록과 라우터 마운트를 이 함수에서 처리한다.
    """
    application = FastAPI(
        title="Web DAW API",
        description="오디오 샘플과 커스텀 악기를 관리하는 Web DAW 백엔드 API",
        version="0.1.0",
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


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """
    서버 상태를 확인하는 헬스체크 엔드포인트.
    AWS ALB 헬스체크와 모니터링에 사용된다.
    """
    return {"status": "ok", "environment": settings.ENVIRONMENT}
