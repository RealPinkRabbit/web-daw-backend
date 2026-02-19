from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# bcrypt 알고리즘으로 비밀번호를 해싱하는 컨텍스트
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT 알고리즘
ALGORITHM = "HS256"


def hash_password(plain_password: str) -> str:
    """
    평문 비밀번호를 bcrypt로 해싱한다.

    Args:
        plain_password: 사용자가 입력한 평문 비밀번호

    Returns:
        해싱된 비밀번호 문자열 (DB에 저장)
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    평문 비밀번호와 해싱된 비밀번호가 일치하는지 확인한다.

    Args:
        plain_password: 사용자가 입력한 평문 비밀번호
        hashed_password: DB에 저장된 해싱된 비밀번호

    Returns:
        일치하면 True, 불일치하면 False
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict[str, Any]) -> str:
    """
    Access Token (단기 JWT)을 생성한다.

    Args:
        data: 토큰에 담을 데이터 (일반적으로 {"sub": user_id})

    Returns:
        JWT 문자열
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict[str, Any]) -> str:
    """
    Refresh Token (장기 JWT)을 생성한다.
    Access Token이 만료됐을 때 재발급에 사용한다.

    Args:
        data: 토큰에 담을 데이터 (일반적으로 {"sub": user_id})

    Returns:
        JWT 문자열
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """
    JWT 토큰을 디코딩하고 페이로드를 반환한다.

    Args:
        token: JWT 문자열

    Returns:
        디코딩된 페이로드 딕셔너리

    Raises:
        JWTError: 토큰이 유효하지 않거나 만료된 경우
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
