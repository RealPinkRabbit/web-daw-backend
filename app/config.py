from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    앱 전체 설정을 관리하는 클래스.
    .env 파일 또는 환경변수에서 값을 읽어온다.
    """

    # 데이터베이스
    DATABASE_URL: str

    # JWT 인증
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # AWS S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-northeast-2"
    S3_BUCKET_NAME: str = ""

    # 앱 설정
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


# 앱 전체에서 이 인스턴스를 import해서 사용한다
settings = Settings()
