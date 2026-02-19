"""
개발용 더미 데이터를 DB에 삽입하는 스크립트.

사용 방법:
    python scripts/seed_db.py

주의: 로컬 개발 환경에서만 실행한다. 프로덕션에 절대 실행하지 않는다.
"""

import sys
import os

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Base, User
from app.db.session import engine


def seed():
    """더미 데이터를 삽입한다."""
    # 테이블 생성 (없는 경우)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 이미 데이터가 있으면 건너뜀
        if db.query(User).count() > 0:
            print("이미 데이터가 존재합니다. 건너뜁니다.")
            return

        # 테스트 사용자 2명 생성
        users = [
            User(
                email="alice@example.com",
                username="alice",
                hashed_password=hash_password("password123"),
                is_active=True,
            ),
            User(
                email="bob@example.com",
                username="bob",
                hashed_password=hash_password("password123"),
                is_active=True,
            ),
        ]

        for user in users:
            db.add(user)

        db.commit()
        print(f"더미 사용자 {len(users)}명이 생성되었습니다.")
        print("  - alice@example.com / password123")
        print("  - bob@example.com / password123")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
