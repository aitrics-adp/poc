#!/bin/bash
# TRI-PRO POC · 자동 데모 실행 헬퍼
# 사용 (로컬):
#   ./demo/run_demo.sh                # 전체 데모 (자동)
#   ./demo/run_demo.sh --manual       # 수동 진행 ('다음' 버튼/Space로 넘김)
#   ./demo/run_demo.sh --speed fast   # 빠르게 자동
#   ./demo/run_demo.sh --start 8      # 8단계부터
#   ./demo/run_demo.sh --phases dashboard,llm  # 특정 단계만
#
# 사용 (배포된 서버 시연):
#   ./demo/run_demo.sh --prod \
#     PATIENT_HOST=patient.example.com \
#     ADMIN_HOST=admin.example.com \
#     API_HOST=api.example.com
# 또는 환경변수 직접 주입:
#   PATIENT_URL=https://... ADMIN_URL=https://... BACKEND_URL=https://... \
#     ./demo/run_demo.sh
# 또는 .env.demo 파일 자동 로드:
#   ./demo/run_demo.sh                # demo/.env가 있으면 자동 source

set -e
cd "$(dirname "$0")/.."

# 0. .env.demo 또는 환경변수 처리 ─────────────────────
if [ "${1:-}" = "--prod" ]; then
  shift
  # KEY=VALUE 인자 파싱 후 export
  while [ $# -gt 0 ] && [[ "$1" == *=* ]]; do
    key="${1%%=*}"
    val="${1#*=}"
    case "$key" in
      PATIENT_HOST) export PATIENT_URL="https://$val" ;;
      ADMIN_HOST)   export ADMIN_URL="https://$val" ;;
      API_HOST)     export BACKEND_URL="https://$val" ;;
      PATIENT_URL)  export PATIENT_URL="$val" ;;
      ADMIN_URL)    export ADMIN_URL="$val" ;;
      BACKEND_URL)  export BACKEND_URL="$val" ;;
    esac
    shift
  done
fi

# demo/.env 자동 로드 (있으면)
if [ -f "demo/.env" ]; then
  set -a; . demo/.env; set +a
fi

PATIENT_URL="${PATIENT_URL:-http://localhost:3000}"
ADMIN_URL="${ADMIN_URL:-http://localhost:3001}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"

echo "▸ 데모 대상:"
echo "    Patient: $PATIENT_URL"
echo "    Admin:   $ADMIN_URL"
echo "    API:     $BACKEND_URL"

# 1. Playwright 설치 확인
if ! ./backend/venv/bin/python -c "import playwright" 2>/dev/null; then
  echo "▸ Playwright 설치..."
  ./backend/venv/bin/pip install --quiet playwright
  ./backend/venv/bin/python -m playwright install chromium
fi

# 2. 서버 헬스체크
echo "▸ 서버 헬스체크..."
for url in \
    "$BACKEND_URL/api/health" \
    "$PATIENT_URL" \
    "$ADMIN_URL"; do
  if ! curl -sf -o /dev/null -m 8 "$url"; then
    echo "❌ $url 응답 없음."
    if [[ "$url" == *localhost* ]]; then
      echo "   로컬: ./restart.sh --all 먼저 실행하세요."
    else
      echo "   배포: 서버 가동 확인 + 도메인·CORS 설정 점검."
    fi
    exit 1
  fi
done
echo "✓ 모든 서버 정상"

# 3. 데모 실행 (env vars 자동 전달)
echo "▸ Chrome 자동 데모 시작..."
PATIENT_URL="$PATIENT_URL" \
ADMIN_URL="$ADMIN_URL" \
BACKEND_URL="$BACKEND_URL" \
  ./backend/venv/bin/python demo/demo_full.py "$@"
