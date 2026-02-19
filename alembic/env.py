import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.models import Base  # noqa: F401 - 모든 모델이 import되어야 Alembic이 감지한다

config = context.config

# alembic.ini의 로그 설정 적용
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic이 마이그레이션을 생성할 때 비교할 메타데이터
target_metadata = Base.metadata

# .env에서 읽어온 DATABASE_URL을 Alembic에 전달
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """
    오프라인 모드: DB에 연결 없이 SQL 스크립트만 생성한다.
    실제 DB 없이 마이그레이션 SQL을 파일로 추출할 때 사용.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    온라인 모드: 실제 DB에 연결하여 마이그레이션을 실행한다.
    일반적으로 사용하는 모드.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
