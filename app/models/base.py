from datetime import datetime

from sqlalchemy import DateTime, JSON, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class PortableJSON(TypeDecorator):
    """
    PostgreSQL에서는 JSONB, 그 외 DB(SQLite 등)에서는 JSON으로 동작하는 타입.
    테스트 환경(SQLite)과 프로덕션 환경(PostgreSQL) 모두에서 사용 가능하다.
    """

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class Base(DeclarativeBase):
    """모든 SQLAlchemy 모델의 기반 클래스."""
    pass


class TimestampMixin:
    """
    created_at, updated_at 컬럼을 자동으로 추가하는 믹스인.
    모든 모델에서 이 클래스를 상속받아 사용한다.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
