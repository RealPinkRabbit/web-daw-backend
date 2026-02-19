from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.user import UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserRead)
def get_my_profile(current_user: User = Depends(get_current_user)) -> User:
    """현재 로그인한 사용자의 프로필을 반환한다."""
    return current_user


@router.patch("/me", response_model=UserRead)
def update_my_profile(
    request: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """
    현재 로그인한 사용자의 프로필을 수정한다.
    변경하지 않을 필드는 요청에서 제외하면 된다.
    """
    if request.username is not None:
        # 다른 사용자가 사용 중인 사용자명인지 확인
        existing = (
            db.query(User)
            .filter(User.username == request.username, User.id != current_user.id)
            .first()
        )
        if existing:
            raise ConflictException("이미 사용 중인 사용자명입니다.")
        current_user.username = request.username

    if request.email is not None:
        existing = (
            db.query(User)
            .filter(User.email == request.email, User.id != current_user.id)
            .first()
        )
        if existing:
            raise ConflictException("이미 사용 중인 이메일입니다.")
        current_user.email = request.email

    db.commit()
    db.refresh(current_user)
    return current_user


@router.delete("/me")
def delete_my_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    현재 로그인한 사용자의 계정을 비활성화한다.
    실제 DB 레코드를 삭제하지 않고 is_active=False로 소프트 삭제한다.
    """
    current_user.is_active = False
    db.commit()
    return {"message": "계정이 비활성화되었습니다."}
