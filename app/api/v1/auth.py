from fastapi import APIRouter, Depends
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.exceptions import CredentialsException
from app.core.security import create_access_token, decode_token
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserRead
from app.services.auth_service import (
    authenticate_user,
    create_tokens_for_user,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserRead, status_code=201)
def register(request: RegisterRequest, db: Session = Depends(get_db)) -> User:
    """
    새 계정을 만든다.
    이메일과 사용자명은 고유해야 한다.
    """
    return register_user(
        db=db,
        email=request.email,
        username=request.username,
        password=request.password,
    )


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """
    이메일과 비밀번호로 로그인하고 JWT 토큰을 받는다.
    반환된 access_token을 Authorization: Bearer <token> 헤더에 담아 보호된 API를 호출한다.
    """
    user = authenticate_user(db=db, email=request.email, password=request.password)
    return create_tokens_for_user(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(request: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """
    Refresh Token으로 새로운 Access Token을 발급받는다.
    Access Token이 만료됐을 때 재로그인 없이 갱신할 수 있다.
    """
    try:
        payload = decode_token(request.refresh_token)

        if payload.get("type") != "refresh":
            raise CredentialsException("Refresh Token이 필요합니다.")

        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise CredentialsException()

    except JWTError:
        raise CredentialsException()

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise CredentialsException()

    # 새로운 Access Token만 발급 (Refresh Token은 재사용)
    token_data = {"sub": str(user.id)}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=request.refresh_token,
    )


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    """
    현재 로그인한 사용자의 정보를 반환한다.
    이 엔드포인트는 JWT 토큰이 정상적으로 작동하는지 테스트할 때 유용하다.
    """
    return current_user
