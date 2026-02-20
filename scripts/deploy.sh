#!/usr/bin/env bash
# EC2 배포 스크립트
# EC2 인스턴스에서 직접 실행: bash scripts/deploy.sh
set -euo pipefail

REPO_URL="https://github.com/RealPinkRabbit/web-daw-backend.git"
APP_DIR="/home/ec2-user/web-daw-backend"
COMPOSE_FILE="docker-compose.prod.yml"

echo "=== Web DAW Backend 배포 시작 ==="

# 1. 소스 코드 업데이트
if [ -d "$APP_DIR" ]; then
    echo "[1/5] 소스 코드 업데이트 (git pull)..."
    cd "$APP_DIR"
    git pull origin master
else
    echo "[1/5] 저장소 클론..."
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
fi

# 2. .env.prod 파일 존재 확인
if [ ! -f ".env.prod" ]; then
    echo "[ERROR] .env.prod 파일이 없습니다."
    echo "        .env.example을 참고하여 .env.prod를 생성하세요."
    echo "        cp .env.example .env.prod && nano .env.prod"
    exit 1
fi

# 3. Docker 이미지 빌드
# docker compose build 대신 docker build 직접 사용
# (Amazon Linux 2023의 buildx 버전 호환성 문제 회피)
echo "[2/5] Docker 이미지 빌드 중..."
docker build -f docker/Dockerfile -t web-daw-backend:latest .

# 4. DB 마이그레이션 실행 (기존 컨테이너 환경변수 사용)
echo "[3/5] Alembic DB 마이그레이션 실행..."
docker compose -f "$COMPOSE_FILE" run --rm app \
    sh -c "alembic upgrade head"

# 5. 앱 컨테이너 재시작
echo "[4/5] 앱 컨테이너 재시작..."
docker compose -f "$COMPOSE_FILE" up -d --force-recreate

# 6. 헬스체크
echo "[5/5] 헬스체크..."
sleep 5
if curl -sf http://localhost:8000/health > /dev/null; then
    echo "=== 배포 완료! /health OK ==="
else
    echo "[ERROR] 헬스체크 실패. 로그 확인:"
    docker compose -f "$COMPOSE_FILE" logs --tail=50 app
    exit 1
fi
