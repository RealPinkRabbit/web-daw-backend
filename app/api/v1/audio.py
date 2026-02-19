import uuid
from math import ceil

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.audio_sample import AudioSampleRead, AudioSampleUpdate, PaginatedAudioSamples
from app.services import audio_service

router = APIRouter(prefix="/audio", tags=["Audio"])

ALLOWED_MIME_TYPES = {"audio/wav", "audio/mpeg", "audio/ogg"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB


@router.post("/upload", response_model=AudioSampleRead, status_code=201)
def upload_audio(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AudioSampleRead:
    """
    오디오 파일을 S3에 업로드하고 메타데이터를 DB에 저장한다.
    허용 형식: WAV, MP3(audio/mpeg), OGG. 최대 50MB.
    """
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"지원하지 않는 파일 형식입니다. 허용: {', '.join(sorted(ALLOWED_MIME_TYPES))}",
        )

    file_content = file.file.read()

    if len(file_content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="파일 크기가 50MB를 초과합니다.",
        )

    return audio_service.upload_audio(
        db=db,
        file_content=file_content,
        original_filename=file.filename or "unnamed",
        content_type=file.content_type,
        owner_id=current_user.id,
    )


@router.get("/", response_model=PaginatedAudioSamples)
def list_audio_samples(
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedAudioSamples:
    """현재 사용자의 오디오 샘플 목록을 페이지네이션하여 반환한다."""
    items, total = audio_service.list_audio_samples(
        db=db, owner_id=current_user.id, page=page, limit=limit
    )
    return PaginatedAudioSamples(
        items=items,
        total=total,
        page=page,
        limit=limit,
        pages=ceil(total / limit) if total > 0 else 0,
    )


@router.get("/{sample_id}", response_model=AudioSampleRead)
def get_audio_sample(
    sample_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AudioSampleRead:
    """단일 오디오 샘플의 메타데이터를 반환한다."""
    return audio_service.get_audio_sample(
        db=db, sample_id=sample_id, owner_id=current_user.id
    )


@router.get("/{sample_id}/download")
def download_audio(
    sample_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RedirectResponse:
    """
    Pre-signed S3 URL을 생성하고 302 리다이렉트로 반환한다.
    클라이언트는 이 URL로 S3에서 직접 파일을 다운로드한다 (5분간 유효).
    """
    url = audio_service.get_presigned_download_url(
        db=db, sample_id=sample_id, owner_id=current_user.id
    )
    return RedirectResponse(url=url, status_code=302)


@router.patch("/{sample_id}", response_model=AudioSampleRead)
def update_audio_sample(
    sample_id: uuid.UUID,
    request: AudioSampleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AudioSampleRead:
    """오디오 샘플의 파일명 또는 공개 여부를 수정한다."""
    return audio_service.update_audio_sample(
        db=db,
        sample_id=sample_id,
        owner_id=current_user.id,
        filename_original=request.filename_original,
        is_public=request.is_public,
    )


@router.delete("/{sample_id}")
def delete_audio_sample(
    sample_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """오디오 샘플을 DB와 S3에서 모두 삭제한다."""
    audio_service.delete_audio_sample(
        db=db, sample_id=sample_id, owner_id=current_user.id
    )
    return {"message": "삭제되었습니다."}
