import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InstrumentSampleRead(BaseModel):
    """악기-샘플 연결 정보 응답 스키마."""

    id: uuid.UUID
    audio_sample_id: uuid.UUID
    note_key: str | None
    velocity_min: int
    velocity_max: int

    model_config = {"from_attributes": True}


class InstrumentSampleCreate(BaseModel):
    """악기에 샘플 추가 요청 스키마."""

    audio_sample_id: uuid.UUID
    note_key: str | None = Field(default=None, max_length=10)
    velocity_min: int = Field(default=0, ge=0, le=127)
    velocity_max: int = Field(default=127, ge=0, le=127)


class InstrumentRead(BaseModel):
    """악기 응답 스키마."""

    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    description: str | None
    instrument_type: str
    is_public: bool
    is_shared: bool
    config_json: dict[str, Any] | None
    instrument_samples: list[InstrumentSampleRead]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InstrumentCreate(BaseModel):
    """악기 생성 요청 스키마."""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    instrument_type: str = Field(default="sampler", max_length=50)
    is_public: bool = False
    config_json: dict[str, Any] | None = None


class InstrumentUpdate(BaseModel):
    """악기 수정 요청 스키마. 모든 필드는 선택적이다."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    instrument_type: str | None = None
    is_public: bool | None = None
    config_json: dict[str, Any] | None = None


class ShareResponse(BaseModel):
    """악기 공유 링크 생성 응답 스키마."""

    share_token: str
    share_url: str


class PaginatedInstruments(BaseModel):
    """페이지네이션된 악기 목록 응답 스키마."""

    items: list[InstrumentRead]
    total: int
    page: int
    limit: int
    pages: int
