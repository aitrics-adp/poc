#!/bin/bash
# TRI-PRO POC 셋업 스크립트
# macOS / Linux 가정. Python 3.11+, Node 20+ 필요.

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

echo "======================================"
echo "  TRI-PRO POC Setup"
echo "======================================"

# 1) 사전 체크
command -v python3 >/dev/null 2>&1 || { echo "❌ python3 필요"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "❌ node 필요 (20+)"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "❌ npm 필요"; exit 1; }

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
NODE_VER=$(node --version | sed 's/v//')
echo "✓ Python $PY_VER"
echo "✓ Node $NODE_VER"

# 2) Backend 셋업
echo ""
echo "[1/4] Backend Python 환경..."
cd "$PROJECT_ROOT/backend"
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
# venv 내 pip을 절대경로로 호출 (source activate에 의존 안 함)
./venv/bin/python -m pip install --quiet --upgrade pip
./venv/bin/python -m pip install --quiet -r requirements.txt
echo "✓ Python 의존성 설치"

# 3) VAPID 키 자동 생성 (Web Push)
echo ""
echo "[2/4] VAPID 키 생성 (Web Push)..."
cd "$PROJECT_ROOT"
if [ ! -f ".env" ]; then
  cp .env.example .env
fi

# Python으로 VAPID 키 생성
VAPID_KEYS=$(python3 - <<'PYEOF'
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import base64

private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
public_key = private_key.public_key()

# Private key (PKCS8 → base64url)
private_bytes = private_key.private_numbers().private_value.to_bytes(32, 'big')
private_b64 = base64.urlsafe_b64encode(private_bytes).decode().rstrip('=')

# Public key (raw uncompressed point → base64url)
public_bytes = public_key.public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint
)
public_b64 = base64.urlsafe_b64encode(public_bytes).decode().rstrip('=')

print(f"{public_b64}|{private_b64}")
PYEOF
)

VAPID_PUB=$(echo "$VAPID_KEYS" | cut -d'|' -f1)
VAPID_PRIV=$(echo "$VAPID_KEYS" | cut -d'|' -f2)

# .env 업데이트 (sed in-place macOS 호환)
if [[ "$OSTYPE" == "darwin"* ]]; then
  sed -i '' "s|^VAPID_PUBLIC_KEY=.*|VAPID_PUBLIC_KEY=$VAPID_PUB|" .env
  sed -i '' "s|^VAPID_PRIVATE_KEY=.*|VAPID_PRIVATE_KEY=$VAPID_PRIV|" .env
  sed -i '' "s|^NEXT_PUBLIC_VAPID_PUBLIC_KEY=.*|NEXT_PUBLIC_VAPID_PUBLIC_KEY=$VAPID_PUB|" .env
else
  sed -i "s|^VAPID_PUBLIC_KEY=.*|VAPID_PUBLIC_KEY=$VAPID_PUB|" .env
  sed -i "s|^VAPID_PRIVATE_KEY=.*|VAPID_PRIVATE_KEY=$VAPID_PRIV|" .env
  sed -i "s|^NEXT_PUBLIC_VAPID_PUBLIC_KEY=.*|NEXT_PUBLIC_VAPID_PUBLIC_KEY=$VAPID_PUB|" .env
fi
echo "✓ VAPID 키 생성 완료 (.env 업데이트)"

# 4) Frontend 의존성
echo ""
echo "[3/4] Patient App 의존성..."
cd "$PROJECT_ROOT/patient-app"
npm install --silent
echo "✓ Patient App 설치"

echo ""
echo "[4/4] Admin App 의존성..."
cd "$PROJECT_ROOT/admin-app"
npm install --silent
echo "✓ Admin App 설치"

# 5) DB 시드
echo ""
echo "[5/5] DB 초기화 + 합성 환자 시드..."
cd "$PROJECT_ROOT/backend"
./venv/bin/python seed.py
echo "✓ 합성 환자 #C-1042 7일 궤적 생성"

# 6) 안내
echo ""
echo "======================================"
echo "  ✅ Setup 완료"
echo "======================================"
echo ""
echo "실행 (3 터미널):"
echo "  터미널 1) cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000"
echo "  터미널 2) cd patient-app && npm run dev"
echo "  터미널 3) cd admin-app && npm run dev -- -p 3001"
echo ""
echo "URL:"
echo "  Patient App: http://localhost:3000"
echo "  Admin App:   http://localhost:3001"
echo "  API Docs:    http://localhost:8000/docs"
echo ""
echo "데이터 리셋: cd backend && python seed.py --reset"
echo ""
