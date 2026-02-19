from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

# SQLAlchemy 엔진 생성
# pool_pre_ping=True: 연결이 끊겼을 때 자동으로 재연결
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)

# 세션 팩토리
# autocommit=False: 트랜잭션을 명시적으로 관리한다
# autoflush=False: 명시적으로 flush 해야 DB에 반영된다
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
