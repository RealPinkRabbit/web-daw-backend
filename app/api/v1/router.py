from fastapi import APIRouter

from app.api.v1 import auth, users

# v1 API의 모든 라우터를 하나로 묶는다
api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(users.router)

# Phase 3 이후 아래 라우터들이 추가된다
# from app.api.v1 import audio, instruments
# api_router.include_router(audio.router)
# api_router.include_router(instruments.router)
