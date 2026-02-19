import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PortableJSON, TimestampMixin


class Instrument(Base, TimestampMixin):
    """
    사용자가 만든 커스텀 악기 테이블.
    여러 오디오 샘플을 노트/패드에 매핑하여 악기를 구성한다.
    """

    __tablename__ = "instruments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 악기 종류 예시: "drum_kit", "synth", "sampler", "pad"
    instrument_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="sampler"
    )

    # 공개/공유 설정
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 악기 설정을 유연하게 저장하는 JSON 컬럼
    # 예: {"bpm": 120, "reverb": 0.3, "pads": [{"key": "C4", "sample_id": "..."}]}
    # JSONB는 PostgreSQL에서 인덱싱 가능한 JSON 타입
    config_json: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)

    # 관계
    owner: Mapped["User"] = relationship("User", back_populates="instruments")
    instrument_samples: Mapped[list["InstrumentSample"]] = relationship(
        "InstrumentSample",
        back_populates="instrument",
        cascade="all, delete-orphan",
    )
    shared_instruments: Mapped[list["SharedInstrument"]] = relationship(
        "SharedInstrument",
        back_populates="instrument",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Instrument id={self.id} name={self.name}>"


class SharedInstrument(Base):
    """
    악기 공유 링크 테이블.
    share_token으로 비인증 사용자도 악기를 조회할 수 있다.
    """

    __tablename__ = "shared_instruments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("instruments.id", ondelete="CASCADE"),
        nullable=False,
    )
    shared_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # URL로 공유할 수 있는 고유 토큰
    share_token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    is_link_share: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 관계
    instrument: Mapped["Instrument"] = relationship(
        "Instrument", back_populates="shared_instruments"
    )

    def __repr__(self) -> str:
        return f"<SharedInstrument instrument_id={self.instrument_id} token={self.share_token[:8]}...>"
