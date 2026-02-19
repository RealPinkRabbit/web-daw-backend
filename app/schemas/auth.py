from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """회원가입 요청 스키마."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=8, max_length=100)


class LoginRequest(BaseModel):
    """로그인 요청 스키마."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """로그인/토큰 갱신 성공 응답 스키마."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """토큰 갱신 요청 스키마."""

    refresh_token: str
