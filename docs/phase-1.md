# Phase 1: DB 기반 구축 — 회고록

## 목표

SQLAlchemy ORM 모델을 작성하고 Alembic으로 PostgreSQL에 테이블을 생성한다.
Phase 0에서 만든 Docker + PostgreSQL 환경 위에 실제 DB 스키마를 올린다.

---

## 1. AI 없이 혼자 구축하는 단계별 절차

### Step 1: 의존성 설치

```bash
pip install sqlalchemy alembic psycopg2-binary
```

> **주의 (Windows + Python 3.13)**: `psycopg2-binary 2.9.9`는 Python 3.13에서 설치가 실패한다. `2.9.11+` 버전을 명시해야 한다.

---

### Step 2: DeclarativeBase 정의 (`app/models/base.py`)

```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

모든 ORM 모델은 이 `Base`를 상속받는다. Alembic이 마이그레이션 파일을 자동 생성할 때
이 `Base.metadata`를 기준으로 현재 DB 스키마와 비교한다.

---

### Step 3: TimestampMixin 작성

```python
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

모든 테이블에서 공통으로 쓰이는 타임스탬프를 Mixin으로 추출한다.
`server_default=func.now()`는 Python 코드가 아닌 **DB 레벨**에서 기본값을 설정한다.

---

### Step 4: 모델 작성 (`app/models/user.py` 등)

SQLAlchemy 2.0 스타일 예시:

```python
class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```

---

### Step 5: Alembic 초기화

```bash
alembic init alembic
```

`alembic/` 디렉토리와 `alembic.ini` 파일이 생성된다.

> **주의 (Windows)**: `alembic.ini`에 한글 주석을 넣으면 `UnicodeDecodeError` 발생.
> 설정 파일에는 영문만 사용한다.

---

### Step 6: `alembic/env.py` 설정

자동 생성(autogenerate)을 위해 모델 메타데이터를 연결한다:

```python
# alembic/env.py
from app.models.base import Base
from app.models import user, audio_sample, instrument, instrument_sample  # 모든 모델 import

target_metadata = Base.metadata
```

모델을 import하지 않으면 Alembic이 테이블 존재를 모르고 마이그레이션을 생성하지 않는다.

---

### Step 7: 마이그레이션 파일 생성 및 실행

```bash
# 마이그레이션 파일 자동 생성
alembic revision --autogenerate -m "initial tables"

# DB에 적용
alembic upgrade head

# 현재 상태 확인
alembic current
```

출력 예시: `5bfc54382ff5 (head)` → 최신 마이그레이션이 적용된 상태

---

## 2. 트러블슈팅

### 문제 1: `psycopg2-binary` 설치 실패 (Python 3.13)

**증상**: `pip install psycopg2-binary` 실행 시 빌드 에러 발생
**원인**: `psycopg2-binary 2.9.9`가 Python 3.13을 지원하지 않음
**해결**: `requirements.txt`에 `psycopg2-binary==2.9.11` 이상 버전 명시
**교훈**: 패키지 설치 실패 시 버전 명시가 없다면 최신 버전을 직접 지정한다

---

### 문제 2: `alembic.ini` UnicodeDecodeError (Windows)

**증상**: `alembic upgrade head` 실행 시 `UnicodeDecodeError: 'cp949' codec can't decode`
**원인**: Windows는 기본 파일 인코딩이 `cp949`인데 한글 주석이 포함된 경우 충돌
**해결**: `alembic.ini`에서 한글 주석을 모두 제거
**교훈**: Windows 환경에서 `.ini`, `.cfg` 파일에는 한글을 사용하지 않는다

---

### 문제 3: `JSONB` 타입 - SQLite 테스트 호환성 문제

**증상**: `pytest` 실행 시 `UnsupportedCompilationError: Compiler can't render element of type JSONB`
**원인**: `JSONB`는 PostgreSQL 전용 타입이라 SQLite 인메모리 테스트 DB에서 사용 불가
**해결**: `app/models/base.py`에 `PortableJSON` TypeDecorator 추가

```python
class PortableJSON(TypeDecorator):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())
```

모델에서 `JSONB` 대신 `PortableJSON`을 사용하면 PostgreSQL에서는 JSONB로,
SQLite에서는 JSON으로 자동 전환된다.
**교훈**: 테스트 DB와 프로덕션 DB가 다를 때는 방언(dialect) 독립적인 타입을 사용한다

---

### 문제 4: `passlib` + `bcrypt` 버전 호환성

**증상**: `pytest` 실행 시 `ValueError: password cannot be longer than 72 bytes`
**원인**: `passlib 1.7.4`는 `bcrypt 4.0+`과 호환되지 않음. bcrypt 5.0.0은 `__about__` 속성을 제거하여 passlib이 버전 감지에 실패
**해결**: `requirements.txt`에 `bcrypt==4.0.1` 명시하여 호환 버전 고정
**교훈**: `passlib[bcrypt]`를 사용할 때 bcrypt 버전을 함께 명시한다. passlib은 2020년 이후 업데이트가 없어 최신 bcrypt와 충돌 위험이 있다

---

### 문제 5: UUID 타입 - SQLite 쿼리 오류

**증상**: `test_get_me_with_valid_token` 실패 - `AttributeError: 'str' object has no attribute 'hex'`
**원인**: `dependencies.py`에서 JWT에서 추출한 `user_id`가 문자열 타입인데, SQLite의 UUID 처리기가 `uuid.UUID` 객체를 기대함
**해결**: `uuid.UUID(user_id)`로 변환 후 쿼리

```python
# Before
user = db.query(User).filter(User.id == user_id).first()

# After
user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
```

**교훈**: PostgreSQL은 UUID 문자열을 암묵적으로 변환해주지만, SQLite는 명시적 변환이 필요하다. 방어적으로 UUID 타입 변환을 명시하는 것이 좋다

---

## 3. 코드 리뷰 포인트

### A. SQLAlchemy 2.0 스타일 - `mapped_column` vs 구버전 `Column`

**구버전 (1.x 스타일)**:
```python
id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
```

**신버전 (2.0 스타일)**:
```python
id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
```

타입 힌트가 ORM 매핑과 결합되어 IDE 자동완성 + 정적 분석(mypy)이 가능해진다.
`user.id`를 접근하면 IDE가 `uuid.UUID` 타입임을 인식한다.

---

### B. TimestampMixin - Mixin 패턴

```python
class User(Base, TimestampMixin):
    ...
```

- `created_at`, `updated_at`를 모든 모델에 반복해서 작성하지 않고 Mixin으로 재사용
- `server_default=func.now()`: Python 레벨이 아닌 **DB 레벨**에서 기본값 설정
  - 모든 DB 클라이언트(앱, 관리자 도구)에서 동일한 타임스탬프 보장
- `onupdate=func.now()`: `UPDATE` SQL 실행 시 자동으로 갱신

---

### C. UUID Primary Key 전략

```python
id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
)
```

순차 ID(1, 2, 3...) 대비 UUID의 장점:
- **열거 공격 방지**: `/users/1`, `/users/2` 예측 불가
- **분산 환경 충돌 없음**: 여러 서버에서 동시에 ID 생성해도 충돌 가능성 극히 낮음
- **마이그레이션 안전**: ID 값이 외부에 노출돼도 순서 정보를 알 수 없음

---

### D. 외래 키 삭제 전략 (CASCADE vs RESTRICT)

```python
# audio_samples: 사용자 삭제 시 오디오 샘플도 함께 삭제
owner_id = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

# instrument_samples: 오디오 샘플이 악기에 연결돼 있으면 삭제 불가
audio_sample_id = mapped_column(ForeignKey("audio_samples.id", ondelete="RESTRICT"))
```

| 전략 | 동작 | 사용 사례 |
|------|------|-----------|
| `CASCADE` | 부모 삭제 시 자식도 자동 삭제 | 사용자 삭제 → 그 사람의 모든 데이터 삭제 |
| `RESTRICT` | 자식이 존재하면 부모 삭제 불가 | 사용 중인 오디오 샘플 삭제 방지 |

비즈니스 규칙을 DB 레벨에서 강제하면 앱 코드 버그에도 데이터 무결성이 보호된다.

---

### E. Alembic autogenerate의 원리

```
모델 변경 후 → alembic revision --autogenerate → alembic upgrade head
```

1. `env.py`에서 `target_metadata = Base.metadata` 설정
2. Alembic이 현재 DB 스키마를 읽음
3. 모델 정의와 비교하여 차이점을 마이그레이션 파일로 생성
4. `alembic upgrade head`로 변경사항을 DB에 적용

**주의**: Alembic이 자동 감지하지 못하는 변경사항도 있다 (CHECK 제약조건 변경, 일부 인덱스 등).
자동 생성된 파일은 항상 검토 후 적용한다.

---

### F. 테스트 격리 전략 (SQLite 인메모리)

```python
# conftest.py
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///./test.db")
```

- 통합 테스트에서 PostgreSQL 대신 SQLite 사용 → Docker 없이도 CI에서 실행 가능
- `get_db` 의존성을 `TestClient`에서 오버라이드 → 앱 코드 수정 없이 테스트 DB 교체
- `setup_db` 픽스처가 각 테스트 전후로 테이블을 생성/삭제하여 테스트 간 격리 보장

**SQLite 사용 시 주의사항**:
- `JSONB` 타입 미지원 → `PortableJSON` TypeDecorator로 해결
- UUID 문자열을 자동 변환하지 않음 → 명시적 `uuid.UUID()` 변환 필요
- Phase 3 이후 PostgreSQL 전용 기능이 많아지면 테스트용 PostgreSQL DB 사용 고려

---

## 4. Phase 완료 체크리스트

- [x] `app/models/base.py` - `Base`, `TimestampMixin`, `PortableJSON` 정의
- [x] `app/models/user.py` - `User` 모델 (UUID PK, 이메일, 비밀번호 해시)
- [x] `app/models/audio_sample.py` - `AudioSample` 모델 (S3 연동 준비)
- [x] `app/models/instrument.py` - `Instrument`, `SharedInstrument` 모델
- [x] `app/models/instrument_sample.py` - `InstrumentSample` 모델 (노트 매핑)
- [x] Alembic 초기화 및 `env.py` 설정 완료
- [x] `alembic upgrade head` 실행 → PostgreSQL에 5개 테이블 생성
- [x] `alembic current` 출력: `5bfc54382ff5 (head)` 확인
- [x] `pytest tests/ -v` → 19개 테스트 모두 PASSED
- [x] 코드 커버리지 67% 달성 (핵심 경로 커버)
- [x] 트러블슈팅 3건 해결 (JSONB, bcrypt 호환성, UUID 쿼리)

---

## 5. 다음 Phase 예고

**Phase 2: 사용자 인증 (JWT)**

- `POST /api/v1/auth/register` - 회원가입 (이미 구현됨, 테스트 통과)
- `POST /api/v1/auth/login` - 로그인 → Access Token + Refresh Token 반환
- `POST /api/v1/auth/refresh` - Refresh Token으로 새 Access Token 발급
- `GET /api/v1/auth/me` - 현재 로그인한 사용자 정보 조회

Phase 1에서 DB 모델 + JWT 기반이 모두 갖춰졌으므로,
Phase 2에서는 실제 API 엔드포인트 동작을 완성하고 엣지 케이스 테스트를 추가한다.
