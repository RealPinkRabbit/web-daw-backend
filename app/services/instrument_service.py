import secrets
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.models.audio_sample import AudioSample
from app.models.instrument import Instrument, SharedInstrument
from app.models.instrument_sample import InstrumentSample


def create_instrument(
    db: Session,
    name: str,
    description: str | None,
    instrument_type: str,
    is_public: bool,
    config_json: dict[str, Any] | None,
    owner_id: uuid.UUID,
) -> Instrument:
    """
    새 악기를 생성한다.

    Args:
        db: DB 세션
        name: 악기 이름
        description: 악기 설명 (선택)
        instrument_type: 악기 종류 (예: "drum_kit", "sampler")
        is_public: 공개 여부
        config_json: 악기 설정 JSON (선택)
        owner_id: 소유자 ID

    Returns:
        생성된 Instrument 객체
    """
    instrument = Instrument(
        owner_id=owner_id,
        name=name,
        description=description,
        instrument_type=instrument_type,
        is_public=is_public,
        config_json=config_json,
    )
    db.add(instrument)
    db.commit()
    db.refresh(instrument)
    return instrument


def list_instruments(
    db: Session,
    owner_id: uuid.UUID,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[Instrument], int]:
    """
    사용자의 악기 목록을 페이지네이션하여 반환한다.

    Args:
        db: DB 세션
        owner_id: 조회할 사용자 ID
        page: 페이지 번호 (1부터 시작)
        limit: 페이지당 항목 수

    Returns:
        (Instrument 목록, 전체 개수) 튜플
    """
    query = db.query(Instrument).filter(Instrument.owner_id == owner_id)
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return items, total


def get_instrument(
    db: Session,
    instrument_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> Instrument:
    """
    단일 악기를 조회한다.
    소유자가 아니면 존재 여부를 노출하지 않기 위해 404를 반환한다.

    Args:
        db: DB 세션
        instrument_id: 조회할 악기 ID
        owner_id: 요청한 사용자 ID

    Returns:
        Instrument 객체

    Raises:
        NotFoundException: 악기가 없거나 소유자가 아닌 경우
    """
    instrument = (
        db.query(Instrument)
        .filter(Instrument.id == instrument_id, Instrument.owner_id == owner_id)
        .first()
    )
    if not instrument:
        raise NotFoundException("악기를 찾을 수 없습니다.")
    return instrument


def update_instrument(
    db: Session,
    instrument_id: uuid.UUID,
    owner_id: uuid.UUID,
    name: str | None,
    description: str | None,
    instrument_type: str | None,
    is_public: bool | None,
    config_json: dict[str, Any] | None,
) -> Instrument:
    """
    악기의 메타데이터를 수정한다.
    None인 필드는 변경하지 않는다.

    Args:
        db: DB 세션
        instrument_id: 수정할 악기 ID
        owner_id: 요청한 사용자 ID
        name: 변경할 이름 (None이면 유지)
        description: 변경할 설명 (None이면 유지)
        instrument_type: 변경할 종류 (None이면 유지)
        is_public: 변경할 공개 여부 (None이면 유지)
        config_json: 변경할 설정 JSON (None이면 유지)

    Returns:
        수정된 Instrument 객체

    Raises:
        NotFoundException: 악기가 없거나 소유자가 아닌 경우
    """
    instrument = get_instrument(db, instrument_id, owner_id)
    if name is not None:
        instrument.name = name
    if description is not None:
        instrument.description = description
    if instrument_type is not None:
        instrument.instrument_type = instrument_type
    if is_public is not None:
        instrument.is_public = is_public
    if config_json is not None:
        instrument.config_json = config_json
    db.commit()
    db.refresh(instrument)
    return instrument


def delete_instrument(
    db: Session,
    instrument_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> None:
    """
    악기를 삭제한다.
    cascade 설정으로 InstrumentSample, SharedInstrument 레코드도 함께 삭제된다.

    Args:
        db: DB 세션
        instrument_id: 삭제할 악기 ID
        owner_id: 요청한 사용자 ID

    Raises:
        NotFoundException: 악기가 없거나 소유자가 아닌 경우
    """
    instrument = get_instrument(db, instrument_id, owner_id)
    db.delete(instrument)
    db.commit()


def add_sample_to_instrument(
    db: Session,
    instrument_id: uuid.UUID,
    owner_id: uuid.UUID,
    audio_sample_id: uuid.UUID,
    note_key: str | None,
    velocity_min: int,
    velocity_max: int,
) -> InstrumentSample:
    """
    오디오 샘플을 악기의 노트에 매핑한다.
    악기와 오디오 샘플 모두 요청 사용자의 소유여야 한다.

    Args:
        db: DB 세션
        instrument_id: 악기 ID
        owner_id: 요청한 사용자 ID
        audio_sample_id: 연결할 오디오 샘플 ID
        note_key: 매핑할 노트 (예: "C4", "pad_1")
        velocity_min: 최소 벨로시티 (0-127)
        velocity_max: 최대 벨로시티 (0-127)

    Returns:
        생성된 InstrumentSample 객체

    Raises:
        NotFoundException: 악기 또는 오디오 샘플을 찾을 수 없거나 소유자가 아닌 경우
    """
    instrument = get_instrument(db, instrument_id, owner_id)

    audio_sample = (
        db.query(AudioSample)
        .filter(AudioSample.id == audio_sample_id, AudioSample.owner_id == owner_id)
        .first()
    )
    if not audio_sample:
        raise NotFoundException("오디오 샘플을 찾을 수 없습니다.")

    mapping = InstrumentSample(
        instrument_id=instrument.id,
        audio_sample_id=audio_sample_id,
        note_key=note_key,
        velocity_min=velocity_min,
        velocity_max=velocity_max,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


def remove_sample_from_instrument(
    db: Session,
    instrument_id: uuid.UUID,
    owner_id: uuid.UUID,
    mapping_id: uuid.UUID,
) -> None:
    """
    악기에서 오디오 샘플 매핑을 제거한다.

    Args:
        db: DB 세션
        instrument_id: 악기 ID
        owner_id: 요청한 사용자 ID
        mapping_id: 제거할 매핑 ID

    Raises:
        NotFoundException: 악기 또는 매핑을 찾을 수 없거나 소유자가 아닌 경우
    """
    get_instrument(db, instrument_id, owner_id)

    mapping = (
        db.query(InstrumentSample)
        .filter(
            InstrumentSample.id == mapping_id,
            InstrumentSample.instrument_id == instrument_id,
        )
        .first()
    )
    if not mapping:
        raise NotFoundException("샘플 매핑을 찾을 수 없습니다.")

    db.delete(mapping)
    db.commit()


def create_share_link(
    db: Session,
    instrument_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> SharedInstrument:
    """
    악기의 공유 링크를 생성하거나 기존 링크의 토큰을 갱신한다.
    악기당 하나의 활성 공유 링크를 유지한다.

    Args:
        db: DB 세션
        instrument_id: 공유할 악기 ID
        owner_id: 요청한 사용자 ID

    Returns:
        SharedInstrument 객체 (share_token 포함)

    Raises:
        NotFoundException: 악기가 없거나 소유자가 아닌 경우
    """
    instrument = get_instrument(db, instrument_id, owner_id)
    new_token = secrets.token_urlsafe(32)

    existing = (
        db.query(SharedInstrument)
        .filter(
            SharedInstrument.instrument_id == instrument_id,
            SharedInstrument.shared_by_user_id == owner_id,
        )
        .first()
    )

    if existing:
        existing.share_token = new_token
        db.commit()
        db.refresh(existing)
        return existing

    share = SharedInstrument(
        instrument_id=instrument_id,
        shared_by_user_id=owner_id,
        share_token=new_token,
    )
    db.add(share)
    instrument.is_shared = True
    db.commit()
    db.refresh(share)
    return share


def get_shared_instrument(
    db: Session,
    share_token: str,
) -> Instrument:
    """
    공유 토큰으로 악기를 조회한다.
    인증 없이 접근 가능하다.

    Args:
        db: DB 세션
        share_token: 공유 토큰

    Returns:
        공유된 Instrument 객체

    Raises:
        NotFoundException: 토큰에 해당하는 공유 링크가 없는 경우
    """
    shared = (
        db.query(SharedInstrument)
        .filter(SharedInstrument.share_token == share_token)
        .first()
    )
    if not shared:
        raise NotFoundException("공유된 악기를 찾을 수 없습니다.")
    return shared.instrument
