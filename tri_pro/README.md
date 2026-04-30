# TRI-PRO POC

> **2.5일 Lean POC** — 환자앱(웹) + 의료진 어드민 + Core PRO Engine + LLM 가드레일(Mock) + Web Push.
> Phase 1 RN WebView 임베드를 위한 기본 구조 포함.

## 한 줄 요약

C-Rehab 퇴원 환자 PRO(Patient-Reported Outcome) 수집 POC. 결정론 채점 + LLM 격리 가드레일 + Pre-Visit Report 자동 생성 가설 검증.

## 폴더 구조

```
tri-pro-poc/
├── backend/                  FastAPI + SQLModel + SQLite + Mock LLM
│   ├── main.py               6 endpoints
│   ├── models.py             5 tables (Patient/Session/Response/Score/LlmAudit)
│   ├── scoring.py            PRO-CTCAE + HADS 결정론 채점
│   ├── llm_mock.py           응급/OoS 가드레일 (LLM_MODE=mock)
│   ├── push.py               Web Push (VAPID 자체 생성)
│   ├── seed.py               합성 환자 #001 7일 궤적
│   └── tests/                단위·가드레일 회귀
├── patient-app/              Next.js 14 (App Router) — 환자
│   ├── app/home              일반 모드 홈
│   ├── app/pro               PRO 응답 (PRO-CTCAE + HADS)
│   ├── app/result            점수 피드백
│   ├── app/talk              LLM Free Talk (가드레일 시연)
│   └── app/elder/*           어르신 모드 (얼굴 척도, 큰 글씨, 일상어)
├── admin-app/                Next.js 14 — 의료진
│   ├── app/                  모니터링 대시보드 (담당 환자 목록)
│   └── app/patients/[id]/pre-visit  Pre-Visit Report
├── e2e/                      Playwright 1 시나리오
├── setup.sh                  의존성 설치 + .env 자동 생성
└── .env.example
```

## 빠른 시작 (macOS)

### 사전 요구사항

- Python 3.11+
- Node 20+
- npm

```bash
python3 --version    # 3.11+
node --version       # 20+
```

### 1) 셋업 (1회)

```bash
chmod +x setup.sh
./setup.sh
```

이 한 번에 다음이 자동 처리됩니다:
- Backend Python venv 생성 + 의존성 설치
- VAPID 키 자동 생성 → `.env` 자동 작성
- patient-app·admin-app npm install
- SQLite DB 초기화 + 합성 환자 #001 7일 시드 데이터 주입

### 2) 실행 (3 터미널)

```bash
# 터미널 1 — Backend
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000

# 터미널 2 — Patient App
cd patient-app
npm run dev    # http://localhost:3000

# 터미널 3 — Admin App
cd admin-app
npm run dev -- -p 3001    # http://localhost:3001
```

### 3) 시연 흐름 (5분)

| 단계 | URL | 동작 |
|---|---|---|
| 1 | http://localhost:3000/home | 환자 #C-1042 선택 → "오늘의 PRO" |
| 2 | http://localhost:3000/pro | PRO-CTCAE 5문항 + HADS 14문항 응답 |
| 3 | http://localhost:3000/result | 점수 피드백 + 7일 추세 차트 + HADS 경계값 알림 |
| 4 | http://localhost:3000/talk | "약 더 먹어도 되나요?" 입력 → Out-of-Scope 차단<br>"숨이 안 쉬어져요" 입력 → 응급 화면 강제 전환 |
| 5 | http://localhost:3000/elder/home | 어르신 모드 — 얼굴 5단계 척도, 큰 글씨, 일상어 |
| 6 | http://localhost:3001 | 의료진 모니터링 대시보드 (긴급/주의/안정 분류) |
| 7 | http://localhost:3001/patients/C-1042/pre-visit | Pre-Visit Report — One-Line Summary + MCID RED 하이라이트 + 라이프로그 대조 + 7일 추세 |
| 8 | (자동) | 의료진 어드민 → "PRO 알림 보내기" 클릭 → 환자 브라우저에 Web Push 도착 |

### 4) 데이터 리셋

```bash
cd backend
source venv/bin/activate
python seed.py --reset
```

### 5) 단위·회귀 테스트

```bash
cd backend
source venv/bin/activate
pytest -v
```

## POC 범위

### 포함
- 일반 모드 + 어르신 모드 UI (얼굴 척도, 큰 글씨, 일상어)
- PRO-CTCAE 핵심 5문항 + HADS 14문항 결정론 채점
- HADS-A/D Cutoff 분류 (정상/경계/이상)
- MCID 하이라이트 (PRO 매핑 Sheet 8 기준)
- LLM 가드레일 — 응급 키워드 12개 + Out-of-Scope 20 패턴
- Pre-Visit Report — One-Line Summary(룰 기반) + 추세 차트 + 라이프로그 대조
- Web Push — PRO 설문 시작 알림
- 합성 환자 #001 7일 궤적 (Oxaliplatin 사이클 후 신경병증 점진 악화 패턴)
- 보호자/콜센터 `tel:` 링크 (어르신 모드)

### 제외 (Phase 1 이월)
- AI 음성 대화 PRO 수집 (STT/TTS)
- Quick / No-Change Mode (Full Mode만)
- FACT-C / FACIT-F / PSQI / EQ-5D-5L
- AWS 서버리스 인프라 (로컬 SQLite)
- 본인인증 (mock — 환자 ID 드롭다운 선택)
- EAS Update / 모바일 네이티브 (RN WebView 임베드는 stub만)
- Audit 7년 보존 / CSV Export
- 다환자 시연 (1명만)

## LLM Mock 모드

가드레일은 사전 키워드 매칭이라 Mock과 실제 LLM 결과가 동일합니다.

| 입력 | Mock 응답 | 차단 |
|---|---|---|
| "숨이 안 쉬어져요" | 119 응급 escalation 화면 강제 전환 | ✅ 응급 키워드 12개 100% |
| "약 더 먹어도 되나요?" | "복용량은 주치의 상담이 필요해요" 고정 응답 | ✅ Out-of-Scope 20 패턴 100% |
| "어제 좀 힘들었어요" | "지난 시간 힘드셨겠어요" 공감 응답 | 정상 (32 합성 프롬프트로 회귀 검증) |

`LLM_MODE=real`로 환경변수 변경 + `ANTHROPIC_API_KEY` 입력 시 실제 Anthropic API 호출로 자동 전환.

## RN WebView 임베드 (Phase 1 참고)

POC 환자앱은 다음 인터페이스를 미리 갖추고 있어 Phase 1 React Native 앱에서 즉시 임베드 가능:

- URL 쿼리로 환자 ID 주입: `?patient_id=C-1042`
- `window.ReactNativeWebView?.postMessage()` stub 1개 — PRO 완료 시 네이티브에 알림
- Viewport meta + 터치 최적화 (44×44pt+)

```typescript
// Phase 1 RN 앱 측
<WebView
  source={{ uri: 'https://tri-pro.example.com/home?patient_id=C-1042' }}
  onMessage={(event) => {
    const data = JSON.parse(event.nativeEvent.data)
    if (data.type === 'pro_complete') { /* 푸시 알림 처리 */ }
  }}
/>
```

## 알려진 제약

1. **SQLite 단일 사용자** — POC라 동시 접속자 1–2명 가정. Phase 1엔 Aurora 전환
2. **Mock 인증** — 의료진 로그인 없음, 환자 ID 드롭다운 선택. Phase 1엔 Cognito
3. **Web Push iOS Safari 제약** — PWA 설치 후에만 동작. macOS Chrome/Safari, Android Chrome에선 즉시 동작
4. **시계열 데이터** — 환자 1명 7일치만. 시연 데이터 한정
5. **차트 라이브러리** — Recharts (Phase 1엔 visx로 확장)

## 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| `ModuleNotFoundError: No module named 'sqlmodel'` | venv 미활성화 | `source backend/venv/bin/activate` |
| 포트 3000/3001/8000 이미 사용 중 | 다른 프로세스 | `lsof -ti:3000 \| xargs kill` |
| Web Push 알림 안 뜸 | 브라우저 알림 권한 거부 | 환경설정 → 알림 → localhost 허용 |
| Pre-Visit Report 비어있음 | seed 미실행 | `python seed.py` |
| `puppeteer browsers install` 에러 | Playwright e2e 부분만 영향 | `cd e2e && npx playwright install chromium` |

## 라이선스 / 데이터

- POC 코드: AITRICS 내부용
- PRO-CTCAE: NCI 공개 (한국어판 표준 번역)
- HADS: Zigmond & Snaith 1983 (인용 의무)
- 합성 환자 데이터: Faker 시드, 실 환자 데이터 사용 안 함

---

문의: TricSquare Platform Architecture Lead
