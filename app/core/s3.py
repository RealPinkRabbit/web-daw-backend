import uuid

import boto3
from botocore.exceptions import ClientError

from app.config import settings


def get_s3_client():
    """
    boto3 S3 클라이언트를 생성하고 반환한다.
    AWS 자격증명은 환경변수에서 자동으로 읽어온다.
    """
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def upload_file_to_s3(
    file_content: bytes,
    original_filename: str,
    content_type: str,
) -> str:
    """
    파일을 S3에 업로드하고 S3 키를 반환한다.

    보안상 사용자 제공 파일명을 그대로 S3 키로 사용하지 않는다.
    UUID를 기반으로 고유한 키를 생성하여 경로 조작 공격을 방지한다.

    Args:
        file_content: 업로드할 파일의 바이트 데이터
        original_filename: 원본 파일명 (확장자 추출용)
        content_type: 파일의 MIME 타입 (예: "audio/wav")

    Returns:
        S3에 저장된 파일의 키 (예: "audio/abc123.wav")

    Raises:
        ClientError: S3 업로드 실패 시
    """
    # 원본 파일명에서 확장자를 추출한다
    extension = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "bin"
    s3_key = f"audio/{uuid.uuid4()}.{extension}"

    client = get_s3_client()
    client.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=s3_key,
        Body=file_content,
        ContentType=content_type,
    )

    return s3_key


def generate_presigned_url(s3_key: str, expires_in: int = 300) -> str:
    """
    S3 파일에 대한 임시 접근 URL을 생성한다.

    Pre-signed URL: 서명된 임시 URL로 인증 없이 파일에 접근 가능.
    기본 5분 후 만료된다.

    Args:
        s3_key: S3에 저장된 파일의 키
        expires_in: URL 유효 시간 (초), 기본값 300초 (5분)

    Returns:
        임시 접근 URL 문자열

    Raises:
        ClientError: URL 생성 실패 시
    """
    client = get_s3_client()
    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key},
        ExpiresIn=expires_in,
    )
    return url


def delete_file_from_s3(s3_key: str) -> None:
    """
    S3에서 파일을 삭제한다.

    주의: 이 함수를 호출하기 전에 DB 레코드를 먼저 확인한다.
    S3 삭제 후 DB 레코드 삭제 순서로 진행하면,
    S3 삭제 성공 후 DB 삭제 실패 시 데이터 불일치가 생길 수 있다.
    서비스 레이어에서 트랜잭션을 적절히 관리한다.

    Args:
        s3_key: 삭제할 파일의 S3 키

    Raises:
        ClientError: S3 삭제 실패 시
    """
    client = get_s3_client()
    client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
