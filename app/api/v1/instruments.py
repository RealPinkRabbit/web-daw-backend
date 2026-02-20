import uuid
from math import ceil

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.instrument import (
    InstrumentCreate,
    InstrumentRead,
    InstrumentSampleCreate,
    InstrumentSampleRead,
    InstrumentUpdate,
    PaginatedInstruments,
    ShareResponse,
)
from app.services import instrument_service

router = APIRouter(prefix="/instruments", tags=["Instruments"])


@router.post("/", response_model=InstrumentRead, status_code=201)
def create_instrument(
    request: InstrumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InstrumentRead:
    """새 악기를 생성한다."""
    return instrument_service.create_instrument(
        db=db,
        name=request.name,
        description=request.description,
        instrument_type=request.instrument_type,
        is_public=request.is_public,
        config_json=request.config_json,
        owner_id=current_user.id,
    )


@router.get("/", response_model=PaginatedInstruments)
def list_instruments(
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedInstruments:
    """현재 사용자의 악기 목록을 페이지네이션하여 반환한다."""
    items, total = instrument_service.list_instruments(
        db=db, owner_id=current_user.id, page=page, limit=limit
    )
    return PaginatedInstruments(
        items=items,
        total=total,
        page=page,
        limit=limit,
        pages=ceil(total / limit) if total > 0 else 0,
    )


# /shared/{token}은 /{id} 보다 먼저 등록해야 라우팅 충돌을 방지할 수 있다.
# FastAPI는 정의 순서대로 라우트를 매칭하므로, 고정 경로가 파라미터 경로보다 앞에 있어야 한다.
@router.get("/shared/{share_token}", response_model=InstrumentRead)
def get_shared_instrument(
    share_token: str,
    db: Session = Depends(get_db),
) -> InstrumentRead:
    """
    공유 토큰으로 악기를 조회한다.
    인증 없이 접근 가능하다.
    """
    return instrument_service.get_shared_instrument(db=db, share_token=share_token)


@router.get("/{instrument_id}", response_model=InstrumentRead)
def get_instrument(
    instrument_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InstrumentRead:
    """단일 악기의 상세 정보를 반환한다."""
    return instrument_service.get_instrument(
        db=db, instrument_id=instrument_id, owner_id=current_user.id
    )


@router.patch("/{instrument_id}", response_model=InstrumentRead)
def update_instrument(
    instrument_id: uuid.UUID,
    request: InstrumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InstrumentRead:
    """악기의 이름, 설명, 공개 여부, 설정 JSON 등을 수정한다."""
    return instrument_service.update_instrument(
        db=db,
        instrument_id=instrument_id,
        owner_id=current_user.id,
        name=request.name,
        description=request.description,
        instrument_type=request.instrument_type,
        is_public=request.is_public,
        config_json=request.config_json,
    )


@router.delete("/{instrument_id}")
def delete_instrument(
    instrument_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """악기와 연결된 샘플 매핑, 공유 링크를 모두 삭제한다."""
    instrument_service.delete_instrument(
        db=db, instrument_id=instrument_id, owner_id=current_user.id
    )
    return {"message": "삭제되었습니다."}


@router.post("/{instrument_id}/samples", response_model=InstrumentSampleRead, status_code=201)
def add_sample_to_instrument(
    instrument_id: uuid.UUID,
    request: InstrumentSampleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InstrumentSampleRead:
    """오디오 샘플을 악기의 특정 노트에 매핑한다."""
    return instrument_service.add_sample_to_instrument(
        db=db,
        instrument_id=instrument_id,
        owner_id=current_user.id,
        audio_sample_id=request.audio_sample_id,
        note_key=request.note_key,
        velocity_min=request.velocity_min,
        velocity_max=request.velocity_max,
    )


@router.delete("/{instrument_id}/samples/{mapping_id}")
def remove_sample_from_instrument(
    instrument_id: uuid.UUID,
    mapping_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """악기에서 오디오 샘플 매핑을 제거한다."""
    instrument_service.remove_sample_from_instrument(
        db=db,
        instrument_id=instrument_id,
        owner_id=current_user.id,
        mapping_id=mapping_id,
    )
    return {"message": "매핑이 제거되었습니다."}


@router.post("/{instrument_id}/share", response_model=ShareResponse)
def create_share_link(
    instrument_id: uuid.UUID,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ShareResponse:
    """
    악기의 공유 링크를 생성한다.
    이미 공유 링크가 있으면 토큰을 갱신한다 (이전 링크 무효화).
    """
    share = instrument_service.create_share_link(
        db=db, instrument_id=instrument_id, owner_id=current_user.id
    )
    share_url = str(req.base_url) + f"api/v1/instruments/shared/{share.share_token}"
    return ShareResponse(share_token=share.share_token, share_url=share_url)
