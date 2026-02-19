import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AudioSample(Base, TimestampMixin):
    """
    사용자가 업로드한 오디오 샘플 테이블.
    실제 파일은 AWS S3에 저장하고, 이 테이블에는 메타데이터만 저장한다.
    """

    __tablename__ = "audio_samples"

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

    # 파일 정보
    # filename_original: 사용자가 업로드한 원본 파일명 (예: "kick_drum.wav")
    # filename_s3: S3에 저장된 실제 키 (예: "audio/uuid4.wav") - UUID로 충돌 방지
    filename_original: Mapped[str] = mapped_column(String(255), nullable=False)
    filename_s3: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    s3_bucket: Mapped[str] = mapped_column(String(100), nullable=False)

    # 파일 메타데이터
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 허용 MIME 타입: audio/wav, audio/mpeg, audio/ogg
    mime_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 공개 여부
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 관계
    owner: Mapped["User"] = relationship("User", back_populates="audio_samples")
    instrument_samples: Mapped[list["InstrumentSample"]] = relationship(
        "InstrumentSample", back_populates="audio_sample"
    )

    def __repr__(self) -> str:
        return f"<AudioSample id={self.id} filename={self.filename_original}>"
