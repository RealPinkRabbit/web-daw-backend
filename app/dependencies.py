import uuid
from typing import Generator

from fastapi import Depends
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.exceptions import CredentialsException
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models.user import User

# FastAPI의 OAuth2 Bearer 토큰 스킴
# Authorization: Bearer <token> 헤더에서 토큰을 자동으로 추출한다
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_db() -> Generator[Session, None, None]:
    """
    DB 세션을 생성하고 요청이 끝나면 자동으로 닫는 의존성 함수.

    FastAPI의 Depends()와 함께 사용한다:
        def my_route(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    JWT 토큰을 검증하고 현재 로그인한 사용자를 반환하는 의존성 함수.

    보호된 엔드포인트에서 사용한다:
        def protected_route(current_user: User = Depends(get_current_user)):
            ...

    Args:
        token: Authorization 헤더에서 추출한 JWT 토큰
        db: DB 세션

    Returns:
        현재 인증된 User 객체

    Raises:
        CredentialsException: 토큰이 유효하지 않거나, 사용자가 존재하지 않거나, 비활성 상태인 경우
    """
    try:
        payload = decode_token(token)

        # 토큰 타입 확인 (refresh 토큰으로 인증 시도 방지)
        if payload.get("type") != "access":
            raise CredentialsException("Access Token이 필요합니다.")

        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise CredentialsException()

    except JWTError:
        raise CredentialsException()

    user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()

    if user is None:
        # 존재하지 않는 사용자임을 노출하지 않기 위해 동일한 예외를 사용한다
        raise CredentialsException()

    if not user.is_active:
        raise CredentialsException("비활성화된 계정입니다.")

    return user
