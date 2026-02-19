from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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
