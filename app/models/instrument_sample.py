import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class InstrumentSample(Base, TimestampMixin):
    """
    악기와 오디오 샘플의 연결 테이블 (다대다 관계 해소).
    어떤 노트/패드에 어떤 오디오 샘플이 매핑되는지 저장한다.
    """

    __tablename__ = "instrument_samples"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("instruments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # RESTRICT: 악기에 사용 중인 오디오 샘플은 삭제할 수 없다
    audio_sample_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audio_samples.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # 매핑 정보
    # note_key: 어떤 노트에 매핑되는지 (예: "C4", "D#3", "pad_1")
    note_key: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # MIDI 벨로시티 범위 (0-127)
    velocity_min: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    velocity_max: Mapped[int] = mapped_column(Integer, default=127, nullable=False)

    # 관계
    instrument: Mapped["Instrument"] = relationship(
        "Instrument", back_populates="instrument_samples"
    )
    audio_sample: Mapped["AudioSample"] = relationship(
        "AudioSample", back_populates="instrument_samples"
    )

    def __repr__(self) -> str:
        return (
            f"<InstrumentSample instrument={self.instrument_id} "
            f"sample={self.audio_sample_id} note={self.note_key}>"
        )
