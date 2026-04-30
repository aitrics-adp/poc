#!/bin/bash
# TRI-PRO POC · 자동 데모 실행 헬퍼
# 사용:
#   ./demo/run_demo.sh                # 전체 데모 (자동)
#   ./demo/run_demo.sh --manual       # 수동 진행 ('다음' 버튼/Space로 넘김)
#   ./demo/run_demo.sh --speed fast   # 빠르게 자동
#   ./demo/run_demo.sh --start 8      # 8단계부터
#   ./demo/run_demo.sh --phases dashboard,llm  # 특정 단계만

set -e
cd "$(dirname "$0")/.."

# 1. Playwright 설치 확인
if ! ./backend/venv/bin/python -c "import playwright" 2>/dev/null; then
  echo "▸ Playwright 설치..."
  ./backend/venv/bin/pip install --quiet playwright
  ./backend/venv/bin/python -m playwright install chromium
fi

# 2. 서버 헬스체크
echo "▸ 서버 상태 확인..."
for url in \
    "http://localhost:8000/api/health" \
    "http://localhost:3000" \
    "http://localhost:3001"; do
  if ! curl -sf -o /dev/null -m 2 "$url"; then
    echo "❌ $url 응답 없음. './restart.sh --all' 먼저 실행하세요."
    exit 1
  fi
done
echo "✓ 모든 서버 정상"

# 3. 데모 실행
echo "▸ Chrome 자동 데모 시작..."
./backend/venv/bin/python demo/demo_full.py "$@"
