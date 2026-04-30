#!/bin/bash
# TRI-PRO POC 통합 재시작 스크립트
# 사용법:
#   ./restart.sh             - 3개 서버만 재시작 (DB 보존)
#   ./restart.sh --reset     - DB 리셋 + 시드 + 재시작
#   ./restart.sh --clean     - .next 캐시 삭제 + 재시작
#   ./restart.sh --all       - 위 모두 (full reset)
#   ./restart.sh stop        - 모든 서버 종료
#   ./restart.sh status      - 현재 상태 확인
#   ./restart.sh logs        - 모든 로그 tail (Ctrl+C로 종료)

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$PROJECT_ROOT/.logs"
PID_DIR="$PROJECT_ROOT/.pids"
mkdir -p "$LOG_DIR" "$PID_DIR"

BACKEND_PORT=8000
PATIENT_PORT=3000
ADMIN_PORT=3001

# ─────────────────────────────────────────────
# 색상
# ─────────────────────────────────────────────
G="\033[32m"; Y="\033[33m"; R="\033[31m"; B="\033[34m"; D="\033[2m"; N="\033[0m"
ok()   { echo -e "${G}✓${N} $1"; }
warn() { echo -e "${Y}⚠${N} $1"; }
err()  { echo -e "${R}✗${N} $1"; }
info() { echo -e "${B}▸${N} $1"; }

# ─────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────
kill_port() {
  local port=$1
  local pids
  pids=$(lsof -ti tcp:"$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill -9 2>/dev/null || true
    sleep 0.5
  fi
}

is_up() {
  local port=$1
  curl -sf -o /dev/null -m 1 "http://127.0.0.1:$port" 2>/dev/null
}

wait_for() {
  local port=$1
  local label=$2
  local path=${3:-/}
  local timeout=${4:-30}
  local elapsed=0
  while [ $elapsed -lt $timeout ]; do
    if curl -sf -o /dev/null -m 1 "http://127.0.0.1:$port$path" 2>/dev/null; then
      ok "$label (port $port) ready"
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
    printf "."
  done
  echo ""
  err "$label timeout (${timeout}s)"
  echo "  로그: tail -f $LOG_DIR/$(echo "$label" | tr '[:upper:]' '[:lower:]').log"
  return 1
}

stop_all() {
  info "기존 서버 종료..."
  for port in $BACKEND_PORT $PATIENT_PORT $ADMIN_PORT; do
    if is_up $port || lsof -ti tcp:$port >/dev/null 2>&1; then
      kill_port $port
      ok "  port $port killed"
    fi
  done
  rm -f "$PID_DIR"/*.pid 2>/dev/null || true
}

show_status() {
  echo ""
  echo "─── 서버 상태 ───"
  for entry in "Backend:$BACKEND_PORT:/api/health" "Patient:$PATIENT_PORT:/" "Admin:$ADMIN_PORT:/"; do
    label=$(echo "$entry" | cut -d: -f1)
    port=$(echo "$entry" | cut -d: -f2)
    path=$(echo "$entry" | cut -d: -f3)
    if curl -sf -o /dev/null -m 1 "http://127.0.0.1:$port$path" 2>/dev/null; then
      printf "  ${G}●${N} %-9s http://localhost:%d ${D}(up)${N}\n" "$label" "$port"
    else
      printf "  ${R}○${N} %-9s http://localhost:%d ${D}(down)${N}\n" "$label" "$port"
    fi
  done
  echo ""
}

# ─────────────────────────────────────────────
# 명령 분기
# ─────────────────────────────────────────────
case "${1:-}" in
  stop)
    stop_all
    ok "모든 서버 종료"
    exit 0
    ;;
  status)
    show_status
    exit 0
    ;;
  logs)
    info "tail -f $LOG_DIR/*.log  (Ctrl+C로 종료)"
    tail -f "$LOG_DIR"/*.log
    exit 0
    ;;
esac

RESET_DB=false
CLEAN_NEXT=false
case "${1:-}" in
  --reset)  RESET_DB=true ;;
  --clean)  CLEAN_NEXT=true ;;
  --all)    RESET_DB=true; CLEAN_NEXT=true ;;
  "")       ;;
  *)        err "알 수 없는 옵션: $1"; head -10 "$0" | tail -8; exit 1 ;;
esac

echo ""
echo "═══════════════════════════════════════"
echo "  TRI-PRO POC 통합 재시작"
echo "═══════════════════════════════════════"
[ "$RESET_DB" = true ]   && warn "옵션: DB 리셋"
[ "$CLEAN_NEXT" = true ] && warn "옵션: .next 캐시 삭제"
echo ""

# 1. 종료
stop_all

# 2. DB reset (선택)
if [ "$RESET_DB" = true ]; then
  info "DB 리셋..."
  rm -f "$PROJECT_ROOT/backend/dev.db"
  ok "  dev.db 삭제"
  cd "$PROJECT_ROOT/backend"
  ./venv/bin/python seed.py 2>&1 | tail -3 | sed 's/^/  /'
fi

# 3. .next 캐시 삭제 (선택)
if [ "$CLEAN_NEXT" = true ]; then
  info ".next 캐시 삭제..."
  rm -rf "$PROJECT_ROOT/admin-app/.next"
  rm -rf "$PROJECT_ROOT/patient-app/.next"
  ok "  admin-app/.next, patient-app/.next 삭제"
fi

# 4. Backend 기동
info "Backend 기동 (port $BACKEND_PORT)..."
cd "$PROJECT_ROOT/backend"
nohup ./venv/bin/uvicorn main:app --reload --port $BACKEND_PORT \
  > "$LOG_DIR/backend.log" 2>&1 &
echo $! > "$PID_DIR/backend.pid"
wait_for $BACKEND_PORT "Backend" "/api/health" 30 || true

# 5. Patient app 기동
info "Patient App 기동 (port $PATIENT_PORT)..."
cd "$PROJECT_ROOT/patient-app"
nohup npm run dev -- -p $PATIENT_PORT \
  > "$LOG_DIR/patient.log" 2>&1 &
echo $! > "$PID_DIR/patient.pid"

# 6. Admin app 기동
info "Admin App 기동 (port $ADMIN_PORT)..."
cd "$PROJECT_ROOT/admin-app"
nohup npm run dev -- -p $ADMIN_PORT \
  > "$LOG_DIR/admin.log" 2>&1 &
echo $! > "$PID_DIR/admin.pid"

# 7. 둘 다 ready 대기 (Next.js는 첫 컴파일 때문에 좀 걸림)
wait_for $PATIENT_PORT "Patient" "/" 60 || true
wait_for $ADMIN_PORT "Admin" "/" 60 || true

# 8. 최종 상태
show_status

echo "─── 빠른 점검 ───"
DASH=$(curl -sf -m 2 http://127.0.0.1:$BACKEND_PORT/api/admin/dashboard 2>/dev/null \
  | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null \
  || echo "?")
echo "  · 대시보드 환자: ${DASH}명"
echo ""
echo "─── 명령어 ───"
echo "  ./restart.sh logs    # 모든 서버 로그 tail"
echo "  ./restart.sh status  # 상태 확인"
echo "  ./restart.sh stop    # 모두 종료"
echo "  ./restart.sh --reset # DB 리셋 후 재시작"
echo ""
echo "─── URL ───"
echo "  Patient: http://localhost:$PATIENT_PORT"
echo "  Admin:   http://localhost:$ADMIN_PORT"
echo "  API:     http://localhost:$BACKEND_PORT/docs"
echo ""
