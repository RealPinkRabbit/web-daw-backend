from fastapi import HTTPException, status


class CredentialsException(HTTPException):
    """인증 실패 시 발생하는 예외."""

    def __init__(self, detail: str = "인증 정보가 유효하지 않습니다.") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class NotFoundException(HTTPException):
    """리소스를 찾을 수 없을 때 발생하는 예외."""

    def __init__(self, detail: str = "요청한 리소스를 찾을 수 없습니다.") -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )


class ForbiddenException(HTTPException):
    """권한이 없을 때 발생하는 예외."""

    def __init__(self, detail: str = "이 작업을 수행할 권한이 없습니다.") -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class ConflictException(HTTPException):
    """중복 리소스 생성 시 발생하는 예외."""

    def __init__(self, detail: str = "이미 존재하는 리소스입니다.") -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )
