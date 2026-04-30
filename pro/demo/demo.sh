#!/bin/bash
# TRI-PRO POC 데모 스크립트 (Chrome 수동 데모용)
# 3개 서버가 떠있어야 함: backend(8000), patient-app(3000), admin-app(3001)

set -e

CHROME="/Applications/Google Chrome.app"

# 사전 체크
echo "🔎 서버 상태 확인..."
for url in "http://localhost:8000/docs" "http://localhost:3000" "http://localhost:3001"; do
  if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "^2\|^3"; then
    echo "  ✓ $url"
  else
    echo "  ❌ $url 응답 없음. 서버를 먼저 띄우세요."
    exit 1
  fi
done

pause() {
  echo ""
  echo "  ⏸  ENTER 키를 누르면 다음 단계로..."
  read -r
}

echo ""
echo "============================================="
echo " TRI-PRO POC · 7단계 시연"
echo "============================================="

# ─────────────────────────────────────────────
echo ""
echo "[1/7] 의료진 모니터링 대시보드"
echo "  → C-1042 환자가 🔴 긴급 상태로 떠있는지 확인"
open -na "Google Chrome" --args --new-window "http://localhost:3001"
pause

echo ""
echo "[2/7] Pre-Visit Report"
echo "  → One-Line Summary, 7일 추세 차트, Key Changes 확인"
open -a "Google Chrome" "http://localhost:3001/patients/C-1042/pre-visit"
pause

echo ""
echo "[3/7] 환자앱 홈 (일반 모드) + Web Push 구독"
echo "  → '🔔 Web Push 알림 구독' 버튼 클릭"
open -a "Google Chrome" "http://localhost:3000"
pause

echo ""
echo "[4/7] 어드민에서 PRO 알림 푸시"
echo "  → Pre-Visit Report 페이지의 '🔔 환자에게 PRO 알림 푸시' 버튼 클릭"
echo "  → 환자앱 탭으로 알림 도착 확인"
pause

echo ""
echo "[5/7] PRO 설문 (PRO-CTCAE 5문항 + HADS 14문항)"
echo "  → 환자앱 홈에서 'PRO 설문 시작' → 신경병증 3 응답 → 결과 화면 확인"
open -a "Google Chrome" "http://localhost:3000/pro"
pause

echo ""
echo "[6/7] 어르신 모드 (One-Question-One-Screen)"
echo "  → 큰 글씨, Wong-Baker 얼굴 척도, 상단 보호자/119 원터치"
open -a "Google Chrome" "http://localhost:3000/elder/home"
pause

echo ""
echo "[7/7] LLM Free Talk · Guardrail 시연"
echo "  ① 정상 공감: '오늘 좀 우울해요'"
echo "  ② Out-of-Scope: '약 더 먹어도 되나요?' → 약물 안내 차단"
echo "  ③ 응급 키워드: '숨이 안 쉬어져요' → 응급 화면 takeover"
open -a "Google Chrome" "http://localhost:3000/talk"
pause

echo ""
echo "============================================="
echo " ✅ 데모 종료"
echo "============================================="
