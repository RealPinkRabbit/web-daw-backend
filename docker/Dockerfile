# 프로덕션용 Dockerfile (멀티 스테이지 빌드)

# ============================================================
# Stage 1: 빌더 - 의존성 설치
# ============================================================
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ============================================================
# Stage 2: 런타임 - 최소한의 이미지
# ============================================================
FROM python:3.11-slim AS runtime

WORKDIR /app

# 시스템 런타임 의존성만 설치 (빌드 도구 제외)
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# 빌더에서 설치된 패키지만 복사
COPY --from=builder /install /usr/local

# 보안: 비루트 사용자로 실행
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# 소스 코드 복사
COPY --chown=appuser:appuser . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
