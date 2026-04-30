#!/bin/bash
# 서비스 시작 (idempotent — 이미 떠있으면 그대로, 안 떠있으면 띄움)
# 사용:
#   ./start.sh             일반 시작
#   ./start.sh --fg        포그라운드 (Ctrl+C로 한꺼번에 종료, 3색 로그 합쳐서 보기)
#
# DB 리셋이나 캐시 삭제 옵션은 ./restart.sh --reset / --clean 사용

set -e
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$PROJECT_ROOT/.logs"
PID_DIR="$PROJECT_ROOT/.pids"
mkdir -p "$LOG_DIR" "$PID_DIR"

BACKEND_PORT=8000
PATIENT_PORT=3000
ADMIN_PORT=3001

G="\033[32m"; Y="\033[33m"; R="\033[31m"; B="\033[34m"; D="\033[2m"; N="\033[0m"
ok()   { echo -e "${G}✓${N} $1"; }
warn() { echo -e "${Y}⚠${N} $1"; }
info() { echo -e "${B}▸${N} $1"; }

is_up() {
  curl -sf -o /dev/null -m 1 "http://127.0.0.1:$1" 2>/dev/null
}

wait_for() {
  local port=$1 label=$2 path=${3:-/} timeout=${4:-30}
  local i=0
  while [ $i -lt $timeout ]; do
    if curl -sf -o /dev/null -m 1 "http://127.0.0.1:$port$path" 2>/dev/null; then
      ok "$label (port $port) ready"
      return 0
    fi
    sleep 1; i=$((i+1)); printf "."
  done
  echo ""
  warn "$label timeout (${timeout}s) — 로그: tail -f $LOG_DIR/$(echo "$label" | tr '[:upper:]' '[:lower:]').log"
}

# ───── 포그라운드 모드 ─────
if [ "${1:-}" = "--fg" ]; then
  info "포그라운드 모드 — Ctrl+C로 한꺼번에 종료"
  trap 'kill $(jobs -p) 2>/dev/null; exit' INT TERM

  if ! is_up $BACKEND_PORT; then
    info "Backend 시작..."
    (cd "$PROJECT_ROOT/backend" && ./venv/bin/uvicorn main:app --reload --port $BACKEND_PORT 2>&1 | sed "s/^/${B}[backend]${N} /") &
  fi
  if ! is_up $PATIENT_PORT; then
    info "Patient 시작..."
    (cd "$PROJECT_ROOT/patient-app" && npm run dev -- -p $PATIENT_PORT 2>&1 | sed "s/^/${G}[patient]${N} /") &
  fi
  if ! is_up $ADMIN_PORT; then
    info "Admin 시작..."
    (cd "$PROJECT_ROOT/admin-app" && npm run dev -- -p $ADMIN_PORT 2>&1 | sed "s/^/${Y}[admin]${N}   /") &
  fi
  wait
  exit
fi

# ───── 백그라운드 모드 (기본) ─────
echo ""
echo "═══════════════════════════════════════"
echo "  TRI-PRO POC 서비스 시작"
echo "═══════════════════════════════════════"

# Backend
if is_up $BACKEND_PORT; then
  ok "Backend (port $BACKEND_PORT) 이미 실행중"
else
  info "Backend 시작..."
  cd "$PROJECT_ROOT/backend"
  nohup ./venv/bin/uvicorn main:app --reload --port $BACKEND_PORT \
    > "$LOG_DIR/backend.log" 2>&1 &
  echo $! > "$PID_DIR/backend.pid"
  wait_for $BACKEND_PORT "Backend" "/api/health" 30 || true
fi

# Patient
if is_up $PATIENT_PORT; then
  ok "Patient (port $PATIENT_PORT) 이미 실행중"
else
  info "Patient 시작..."
  cd "$PROJECT_ROOT/patient-app"
  nohup npm run dev -- -p $PATIENT_PORT \
    > "$LOG_DIR/patient.log" 2>&1 &
  echo $! > "$PID_DIR/patient.pid"
fi

# Admin
if is_up $ADMIN_PORT; then
  ok "Admin (port $ADMIN_PORT) 이미 실행중"
else
  info "Admin 시작..."
  cd "$PROJECT_ROOT/admin-app"
  nohup npm run dev -- -p $ADMIN_PORT \
    > "$LOG_DIR/admin.log" 2>&1 &
  echo $! > "$PID_DIR/admin.pid"
fi

# Next.js 둘 다 컴파일 대기 (최대 60초)
wait_for $PATIENT_PORT "Patient" "/" 60 || true
wait_for $ADMIN_PORT "Admin" "/" 60 || true

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
echo "─── 명령어 ───"
echo "  ./start.sh --fg      포그라운드 모드 (로그 합쳐 보기)"
echo "  ./stop.sh            모두 종료"
echo "  ./restart.sh         재시작"
echo "  ./restart.sh logs    로그 tail"
echo "  ./restart.sh --reset DB 리셋 후 재시작"
echo ""
echo "URL:"
echo "  Patient: http://localhost:$PATIENT_PORT"
echo "  Admin:   http://localhost:$ADMIN_PORT"
echo "  API:     http://localhost:$BACKEND_PORT/docs"
