# Phase 2: 사용자 인증 — 회고록

## 목표

JWT 기반 인증 시스템을 구현하고 검증한다.
회원가입 → 로그인 → 토큰 발급 → 인증된 API 호출까지 전체 인증 흐름을 완성한다.

---

## 구현된 API 엔드포인트

| 메서드 | 경로 | 설명 | 인증 |
|--------|------|------|------|
| POST | `/api/v1/auth/register` | 회원가입 | 불필요 |
| POST | `/api/v1/auth/login` | 로그인 → 토큰 발급 | 불필요 |
| POST | `/api/v1/auth/refresh` | Access Token 갱신 | Refresh Token |
| GET | `/api/v1/auth/me` | 현재 사용자 정보 | 필요 |
| GET | `/api/v1/users/me` | 사용자 프로필 조회 | 필요 |
| PATCH | `/api/v1/users/me` | 사용자 프로필 수정 | 필요 |
| DELETE | `/api/v1/users/me` | 계정 비활성화 | 필요 |

---

## 1. AI 없이 혼자 구축하는 단계별 절차

### Step 1: 비밀번호 해싱 (`app/core/security.py`)

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
```

절대로 비밀번호를 평문으로 저장하지 않는다.
bcrypt는 같은 비밀번호라도 **salt** 덕분에 매번 다른 해시를 생성한다.

---

### Step 2: JWT 토큰 생성/검증 (`app/core/security.py`)

```python
from jose import jwt
from datetime import datetime, timedelta, timezone

ALGORITHM = "HS256"

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=30)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
```

JWT는 `header.payload.signature` 세 부분으로 구성된다.
`SECRET_KEY`로 서명하므로 서버만 유효한 토큰을 발급할 수 있다.

---

### Step 3: Pydantic 스키마로 입력 검증 (`app/schemas/auth.py`)

```python
class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8, max_length=100)
```

- `EmailStr`: 이메일 형식 자동 검증 (Pydantic 내장)
- `pattern`: 영문/숫자/언더스코어만 허용
- 검증 실패 시 FastAPI가 자동으로 422 에러를 반환한다

---

### Step 4: 서비스 레이어로 비즈니스 로직 분리 (`app/services/auth_service.py`)

```python
def register_user(db: Session, email: str, username: str, password: str) -> User:
    if db.query(User).filter(User.email == email).first():
        raise ConflictException("이미 사용 중인 이메일입니다.")
    # ...
    user = User(email=email, username=username, hashed_password=hash_password(password))
    db.add(user)
    db.commit()
    return user
```

라우터는 서비스를 호출하기만 하고, 비즈니스 로직은 서비스에만 있다.
덕분에 라우터 코드가 짧아지고 서비스 로직을 독립적으로 테스트할 수 있다.

---

### Step 5: 인증 의존성 함수 (`app/dependencies.py`)

```python
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(token)
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    if user is None or not user.is_active:
        raise CredentialsException()
    return user
```

FastAPI의 `Depends()`를 사용하면 보호된 모든 엔드포인트에서 이 함수 하나로 인증을 처리한다.

---

### Step 6: Access/Refresh Token 전략

```
로그인
  └─> Access Token (30분 유효)  →  API 요청 시 사용
  └─> Refresh Token (7일 유효)  →  Access Token 만료 시 갱신용

갱신 흐름
  1. Access Token 만료 (401 에러)
  2. POST /auth/refresh + Refresh Token
  3. 새 Access Token 발급
  4. API 재요청
```

Access Token은 짧게 유지해야 탈취 위험이 줄어든다.
Refresh Token은 길게 유지해 사용자 경험을 개선한다.

---

## 2. 트러블슈팅

### 문제 1: refresh 엔드포인트 UUID 문자열 오류 (SQLite)

**증상**: `test_refresh_returns_new_access_token` 테스트에서 `AttributeError: 'str' object has no attribute 'hex'`
**원인**: `auth.py`의 refresh 엔드포인트에서 JWT의 `sub` 값(문자열)을 그대로 DB 쿼리에 사용
**해결**: `uuid.UUID(user_id)` 변환 추가

```python
# Before
user = db.query(User).filter(User.id == user_id).first()

# After
user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
```

**교훈**: UUID를 PK로 사용할 때 JWT에서 꺼낸 값은 항상 문자열이다.
DB 쿼리 전에 반드시 `uuid.UUID()` 객체로 변환한다.
(Phase 1에서 `dependencies.py`에 동일한 패턴이 있었으나 `auth.py`에도 중복 존재)

---

## 3. 코드 리뷰 포인트

### A. 서비스 레이어 패턴 (Service Layer Pattern)

```
라우터 (HTTP 관심사)
  ↓ 호출
서비스 (비즈니스 로직)
  ↓ 호출
모델/DB (데이터 접근)
```

**라우터가 직접 DB를 쿼리하면 안 되는 이유**:
1. 동일한 로직이 여러 라우터에서 중복될 수 있다
2. HTTP와 비즈니스 로직이 얽혀 테스트가 어려워진다
3. 나중에 gRPC나 CLI로 확장할 때 서비스 레이어를 재사용할 수 있다

---

### B. 보안: 동일한 에러 메시지로 정보 노출 방지

```python
def authenticate_user(db, email, password):
    user = db.query(User).filter(User.email == email).first()

    # "이메일이 없음"과 "비밀번호 틀림"을 구분하지 않는다
    if not user or not verify_password(password, user.hashed_password):
        raise CredentialsException("이메일 또는 비밀번호가 올바르지 않습니다.")
```

만약 "이메일이 존재하지 않습니다"와 "비밀번호가 틀렸습니다"를 구분해서 반환하면,
공격자가 이메일 존재 여부를 알아낼 수 있다 (사용자 열거 공격).

---

### C. 소프트 삭제 (Soft Delete)

```python
@router.delete("/me")
def delete_my_account(...):
    current_user.is_active = False  # DB 레코드를 실제 삭제하지 않는다
    db.commit()
```

실제 삭제 대신 `is_active=False`로 처리하는 이유:
- **데이터 복구 가능**: 실수로 탈퇴한 경우 복원 가능
- **참조 무결성**: 사용자가 생성한 콘텐츠(오디오, 악기)의 FK가 깨지지 않음
- **규정 준수**: 일부 법규에서는 데이터를 즉시 삭제하지 않고 보관 기간을 요구

---

### D. FastAPI Depends() - 의존성 주입

```python
@router.get("/me")
def get_my_profile(current_user: User = Depends(get_current_user)) -> User:
    return current_user
```

`Depends(get_current_user)`가 하는 일:
1. Authorization 헤더에서 Bearer 토큰 추출
2. 토큰 유효성 검증 (서명, 만료 시간, 타입)
3. DB에서 사용자 조회
4. 비활성 계정 검사
5. User 객체를 핸들러에 주입

10줄 이상의 로직이 파라미터 한 줄로 처리된다.
인증이 필요한 모든 엔드포인트에서 동일하게 재사용한다.

---

### E. Access Token vs Refresh Token 분리

| | Access Token | Refresh Token |
|--|---|---|
| 유효 기간 | 30분 | 7일 |
| 용도 | API 요청 인증 | Access Token 갱신 |
| 보관 위치 | 메모리 (JS 변수) | HTTP-only 쿠키 권장 |

Refresh Token을 `POST /auth/refresh`에 보내면 새 Access Token을 발급받는다.
현재 구현은 Refresh Token을 재사용(rotation 없음)하는데, 보안을 강화하려면
갱신 시 Refresh Token도 새로 발급(rotation)하고 이전 것을 무효화해야 한다.

---

### F. 테스트: 각 클래스가 하나의 엔드포인트 담당

```
TestRegister         → POST /auth/register
TestLogin            → POST /auth/login
TestRefreshToken     → POST /auth/refresh
TestProtectedEndpoint → GET /auth/me
TestGetMyProfile     → GET /users/me
TestUpdateMyProfile  → PATCH /users/me
TestDeleteMyAccount  → DELETE /users/me
```

테스트 클래스를 엔드포인트 단위로 구성하면:
- 어떤 엔드포인트를 테스트하는지 한눈에 보인다
- 특정 엔드포인트 테스트만 선택해서 실행할 수 있다: `pytest tests/ -k "TestLogin"`

---

## 4. Phase 완료 체크리스트

- [x] `POST /api/v1/auth/register` - 회원가입 (이메일/사용자명 중복 검사 포함)
- [x] `POST /api/v1/auth/login` - 로그인 (Access + Refresh Token 발급)
- [x] `POST /api/v1/auth/refresh` - Refresh Token으로 Access Token 갱신
- [x] `GET /api/v1/auth/me` - 현재 사용자 조회
- [x] `GET /api/v1/users/me` - 사용자 프로필 조회
- [x] `PATCH /api/v1/users/me` - 프로필 수정 (사용자명/이메일, 중복 검사)
- [x] `DELETE /api/v1/users/me` - 계정 비활성화 (소프트 삭제)
- [x] `pytest tests/ -v` → 33개 테스트 모두 PASSED
- [x] 코드 커버리지 74% (auth_service.py: 100%, users.py: 100%, security.py: 100%)
- [x] 비활성 계정 로그인 차단 테스트 통과
- [x] 정보 노출 방지 (동일한 401 메시지) 구현 확인

---

## 5. 다음 Phase 예고

**Phase 3: S3 오디오 업로드**

- `POST /api/v1/audio/upload` - 오디오 파일을 S3에 업로드하고 메타데이터를 DB에 저장
- `GET /api/v1/audio/{id}/download` - Pre-signed URL로 클라이언트가 S3에서 직접 다운로드
- boto3로 AWS S3 연동
- 실제 S3 호출은 Mock으로 처리하여 테스트
- `AudioSample` 모델은 이미 준비되어 있음
