import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserRead(BaseModel):
    """사용자 정보 응답 스키마. 비밀번호는 절대 포함하지 않는다."""

    id: uuid.UUID
    email: EmailStr
    username: str
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """사용자 정보 수정 요청 스키마. 모든 필드는 선택적이다."""

    username: str | None = Field(default=None, min_length=3, max_length=50)
    email: EmailStr | None = None
