"""
테스트 공통 픽스처 모음.

모든 테스트는 독립적인 DB 세션을 사용하며,
각 테스트 후 DB 상태가 초기화된다.

사용 방법:
    def test_something(client, db_session):
        # client: TestClient 인스턴스
        # db_session: 격리된 DB 세션
        ...
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.dependencies import get_db
from app.main import app
from app.models.base import Base

# 테스트 전용 DB (개발 DB와 분리)
# 환경변수가 없으면 SQLite 인메모리 DB를 사용한다 (CI 환경에서는 PostgreSQL 사용)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "sqlite:///./test.db",
)

test_engine = create_engine(
    TEST_DATABASE_URL,
    # SQLite는 check_same_thread=False 필요
    connect_args={"check_same_thread": False} if "sqlite" in TEST_DATABASE_URL else {},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function", autouse=True)
def setup_db():
    """
    각 테스트 함수 실행 전 테이블을 생성하고,
    실행 후 테이블을 삭제하여 테스트 간 격리를 보장한다.
    """
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def db_session(setup_db):
    """
    테스트용 DB 세션을 제공한다.
    테스트 종료 후 자동으로 닫힌다.
    """
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session):
    """
    FastAPI TestClient를 제공한다.
    get_db 의존성을 테스트 DB 세션으로 교체한다.
    """

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
