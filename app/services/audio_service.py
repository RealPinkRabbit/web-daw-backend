import uuid

from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import NotFoundException
from app.core.s3 import delete_file_from_s3, generate_presigned_url, upload_file_to_s3
from app.models.audio_sample import AudioSample


def upload_audio(
    db: Session,
    file_content: bytes,
    original_filename: str,
    content_type: str,
    owner_id: uuid.UUID,
) -> AudioSample:
    """
    오디오 파일을 S3에 업로드하고 DB에 메타데이터를 저장한다.

    Args:
        db: DB 세션
        file_content: 파일 바이트 데이터
        original_filename: 사용자가 올린 원본 파일명
        content_type: MIME 타입 (예: "audio/wav")
        owner_id: 업로드한 사용자 ID

    Returns:
        생성된 AudioSample 객체

    Raises:
        ClientError: S3 업로드 실패 시
    """
    s3_key = upload_file_to_s3(file_content, original_filename, content_type)

    sample = AudioSample(
        owner_id=owner_id,
        filename_original=original_filename,
        filename_s3=s3_key,
        s3_bucket=settings.S3_BUCKET_NAME,
        file_size_bytes=len(file_content),
        mime_type=content_type,
    )
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample


def list_audio_samples(
    db: Session,
    owner_id: uuid.UUID,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[AudioSample], int]:
    """
    사용자의 오디오 샘플 목록을 페이지네이션하여 반환한다.

    Args:
        db: DB 세션
        owner_id: 조회할 사용자 ID
        page: 페이지 번호 (1부터 시작)
        limit: 페이지당 항목 수

    Returns:
        (AudioSample 목록, 전체 개수) 튜플
    """
    query = db.query(AudioSample).filter(AudioSample.owner_id == owner_id)
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return items, total


def get_audio_sample(
    db: Session,
    sample_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> AudioSample:
    """
    단일 오디오 샘플을 조회한다.
    소유자가 아니면 존재 여부를 노출하지 않기 위해 404를 반환한다.

    Args:
        db: DB 세션
        sample_id: 조회할 오디오 샘플 ID
        owner_id: 요청한 사용자 ID

    Returns:
        AudioSample 객체

    Raises:
        NotFoundException: 샘플이 없거나 소유자가 아닌 경우
    """
    sample = (
        db.query(AudioSample)
        .filter(AudioSample.id == sample_id, AudioSample.owner_id == owner_id)
        .first()
    )
    if not sample:
        raise NotFoundException("오디오 샘플을 찾을 수 없습니다.")
    return sample


def get_presigned_download_url(
    db: Session,
    sample_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> str:
    """
    오디오 파일의 Pre-signed 다운로드 URL을 생성한다.

    Args:
        db: DB 세션
        sample_id: 오디오 샘플 ID
        owner_id: 요청한 사용자 ID

    Returns:
        5분간 유효한 Pre-signed S3 URL

    Raises:
        NotFoundException: 샘플이 없거나 소유자가 아닌 경우
    """
    sample = get_audio_sample(db, sample_id, owner_id)
    return generate_presigned_url(sample.filename_s3)


def update_audio_sample(
    db: Session,
    sample_id: uuid.UUID,
    owner_id: uuid.UUID,
    filename_original: str | None,
    is_public: bool | None,
) -> AudioSample:
    """
    오디오 샘플의 메타데이터(파일명, 공개 여부)를 수정한다.

    Args:
        db: DB 세션
        sample_id: 수정할 오디오 샘플 ID
        owner_id: 요청한 사용자 ID
        filename_original: 변경할 파일명 (None이면 유지)
        is_public: 변경할 공개 여부 (None이면 유지)

    Returns:
        수정된 AudioSample 객체

    Raises:
        NotFoundException: 샘플이 없거나 소유자가 아닌 경우
    """
    sample = get_audio_sample(db, sample_id, owner_id)
    if filename_original is not None:
        sample.filename_original = filename_original
    if is_public is not None:
        sample.is_public = is_public
    db.commit()
    db.refresh(sample)
    return sample


def delete_audio_sample(
    db: Session,
    sample_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> None:
    """
    오디오 샘플을 DB와 S3에서 모두 삭제한다.
    DB 삭제를 먼저 커밋하고 S3 삭제를 수행하여 DB 트랜잭션 무결성을 우선한다.

    Args:
        db: DB 세션
        sample_id: 삭제할 오디오 샘플 ID
        owner_id: 요청한 사용자 ID

    Raises:
        NotFoundException: 샘플이 없거나 소유자가 아닌 경우
    """
    sample = get_audio_sample(db, sample_id, owner_id)
    s3_key = sample.filename_s3
    db.delete(sample)
    db.commit()
    # DB 커밋 후 S3 삭제: DB 삭제 실패 시 S3 파일이 남아 재시도 가능
    delete_file_from_s3(s3_key)
