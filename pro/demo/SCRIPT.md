# TRI-PRO POC · 데모 시나리오 (5분)

> 합성 환자 **C-1042** (62세, 결장암, Oxaliplatin Cycle D14) 7일 PRO 데이터 기반.

## 0. 사전 준비 (3 터미널)

```bash
# T1
cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000
# T2
cd patient-app && npm run dev
# T3
cd admin-app && npm run dev -- -p 3001
```

---

## 1. 의료진 대시보드 (30초)
**URL**: http://localhost:3001

> "외래 시작 5분 전. 담당 환자 1명이 🔴 긴급으로 떠 있습니다.
> 7일 동안 신경병증이 1 → 3까지 올라왔다는 신호입니다."

확인 포인트: 🔴 긴급 1명 / 🟡 주의 0~1 / 🟢 안정 N

## 2. Pre-Visit Report (60초)
**클릭**: `Pre-Visit Report →`

> "신경병증 3·HADS-A 8(경계). 라이프로그(걷기 30%↓·수면 -1.2h)
> 와의 대조까지 한 눈에. **One-Line Summary**가 의사에게 전달되는 결론입니다."

확인 포인트:
- 빨간 박스 One-Line Summary
- Recharts 7일 추세선 (신경병증 ↗, HADS-A 횡보)
- Key Changes 우측 카드 (🔴 PRO-CTCAE neuropathy=3)

## 3. Web Push 구독 (30초)
**환자앱**: http://localhost:3000 → "🔔 Web Push 알림 구독"

> "환자가 한 번 구독하면, 다음 PRO 시점에 의료진이 트리거할 수 있습니다."

## 4. 어드민 → 환자 푸시 (30초)
Pre-Visit Report 페이지의 "🔔 환자에게 PRO 알림 푸시" 클릭.

> "구독 디바이스 1개로 발송 완료. 환자 OS 알림센터에 도착합니다."

## 5. PRO 설문 + 즉시 결과 (60초)
**환자앱**: 홈 → "PRO 설문 시작"

> "PRO-CTCAE 5문항 + HADS 14문항. 결정론 코어가 즉시 채점·MCID 비교·
> Red/Yellow 판정. LLM 없이도 임상 의사결정 가능한 수준."

확인 포인트: result 페이지에 신호등 + 추세 차트.

## 6. 어르신 모드 (45초)
**URL**: http://localhost:3000/elder/home

> "큰 글씨, 한 화면 = 한 질문, Wong-Baker 얼굴 척도.
> 상단 보호자/119 원터치(`tel:` 링크)는 늘 노출."

## 7. LLM Free Talk · Guardrail (45초)
**URL**: http://localhost:3000/talk

세 가지 입력 차례로:

| 입력 | 기대 응답 |
|---|---|
| `오늘 좀 우울해요` | 공감 템플릿 + PRO 유도 |
| `약 더 먹어도 되나요?` | **Out-of-Scope** 차단 → "주치의에게" |
| `숨이 안 쉬어져요` | **응급 takeover** → 119/보호자 버튼 |

> "Step 1 결정론이 응급 키워드 12개·OoS 패턴 20개를 먼저 걸러낸 뒤
> Step 2 LLM에 위임. 모든 LLM 응답에 의료자문 면책 푸터 자동 부착."

---

## 마무리 한 줄
"5주 사양을 **2.5일 만에 로컬에서 검증**했습니다.
2-Step 안전 구조·결정론 채점·Web Push·LLM 가드레일까지 작동합니다."

---

## 자동 실행

```bash
# 수동 진행 (ENTER로 다음 단계)
chmod +x demo/demo.sh && ./demo/demo.sh

# Playwright 완전 자동 + 스크린샷
./backend/venv/bin/python -m pip install playwright
./backend/venv/bin/python -m playwright install chromium
./backend/venv/bin/python demo/demo_auto.py
# → demo/screenshots/01..07_*.png 생성
```
