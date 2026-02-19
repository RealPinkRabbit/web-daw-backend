from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, CredentialsException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import TokenResponse


def register_user(db: Session, email: str, username: str, password: str) -> User:
    """
    새 사용자를 등록한다.

    Args:
        db: DB 세션
        email: 사용자 이메일 (고유해야 함)
        username: 사용자명 (고유해야 함)
        password: 평문 비밀번호 (해싱하여 저장)

    Returns:
        생성된 User 객체

    Raises:
        ConflictException: 이메일 또는 사용자명이 이미 존재하는 경우
    """
    # 이메일 중복 확인
    if db.query(User).filter(User.email == email).first():
        raise ConflictException("이미 사용 중인 이메일입니다.")

    # 사용자명 중복 확인
    if db.query(User).filter(User.username == username).first():
        raise ConflictException("이미 사용 중인 사용자명입니다.")

    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    """
    이메일과 비밀번호로 사용자를 인증한다.

    보안 주의: 이메일이 없는 경우와 비밀번호가 틀린 경우 모두
    동일한 예외를 발생시켜 어떤 정보가 틀렸는지 노출하지 않는다.

    Args:
        db: DB 세션
        email: 사용자 이메일
        password: 평문 비밀번호

    Returns:
        인증된 User 객체

    Raises:
        CredentialsException: 이메일이 존재하지 않거나 비밀번호가 틀린 경우
    """
    user = db.query(User).filter(User.email == email).first()

    # 이메일 미존재와 비밀번호 불일치를 동일하게 처리 (정보 노출 방지)
    if not user or not verify_password(password, user.hashed_password):
        raise CredentialsException("이메일 또는 비밀번호가 올바르지 않습니다.")

    if not user.is_active:
        raise CredentialsException("비활성화된 계정입니다.")

    return user


def create_tokens_for_user(user: User) -> TokenResponse:
    """
    사용자를 위한 Access/Refresh 토큰 쌍을 생성한다.

    Args:
        user: 토큰을 발급할 User 객체

    Returns:
        TokenResponse (access_token, refresh_token, token_type)
    """
    token_data = {"sub": str(user.id)}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )
