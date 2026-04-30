#!/bin/bash
# EC2 배포·재배포 스크립트
# 사용:
#   ssh ec2-user@<public-ip>
#   cd ~/tri-pro-poc
#   ./scripts/deploy.sh           # 최신 코드 pull + 재빌드 + 재기동
#   ./scripts/deploy.sh --no-pull # 현재 코드로만 재기동 (.env 변경만)
#   ./scripts/deploy.sh --reset   # DB 까지 새로 (데이터 날아감)

set -e
cd "$(dirname "$0")/.."

PULL=true
RESET=false
for arg in "$@"; do
  case $arg in
    --no-pull) PULL=false ;;
    --reset)   RESET=true ;;
  esac
done

# .env 확인
if [ ! -f .env ]; then
  echo "❌ .env 파일이 없습니다."
  echo "   cp .env.prod.example .env 후 채워주세요."
  exit 1
fi

# 1. git pull
if [ "$PULL" = true ]; then
  echo "▸ git pull..."
  git pull origin main
fi

# 2. DB reset (옵션)
if [ "$RESET" = true ]; then
  echo "⚠️ DB 리셋 — 모든 데이터 삭제"
  docker compose down -v
fi

# 3. 빌드 + 기동 (변경된 컨테이너만 재빌드)
echo "▸ 빌드 + 기동..."
docker compose pull caddy db 2>/dev/null || true
docker compose up -d --build

# 4. 헬스체크
echo "▸ 헬스체크 (최대 60초)..."
for i in {1..30}; do
  if docker compose exec -T backend curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
    echo "✓ Backend 정상"
    break
  fi
  sleep 2
done

echo ""
echo "═══════════════════════════════════════"
echo " ✅ 배포 완료"
echo "═══════════════════════════════════════"
docker compose ps
echo ""
. .env
echo "URL:"
echo "  Patient: https://${PATIENT_HOST}"
echo "  Admin:   https://${ADMIN_HOST}"
echo "  API:     https://${API_HOST}/api/health"
echo ""
echo "로그 보기: docker compose logs -f backend"
echo "재배포:    ./scripts/deploy.sh"
echo "DB 리셋:   ./scripts/deploy.sh --reset"
