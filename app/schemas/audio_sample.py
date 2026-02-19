import uuid
from datetime import datetime

from pydantic import BaseModel


class AudioSampleRead(BaseModel):
    """오디오 샘플 응답 스키마."""

    id: uuid.UUID
    owner_id: uuid.UUID
    filename_original: str
    file_size_bytes: int | None
    duration_ms: int | None
    mime_type: str | None
    is_public: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AudioSampleUpdate(BaseModel):
    """오디오 샘플 수정 요청 스키마."""

    filename_original: str | None = None
    is_public: bool | None = None


class PaginatedAudioSamples(BaseModel):
    """페이지네이션된 오디오 샘플 목록 응답 스키마."""

    items: list[AudioSampleRead]
    total: int
    page: int
    limit: int
    pages: int
