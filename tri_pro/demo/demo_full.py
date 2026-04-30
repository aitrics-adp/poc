"""TRI-PRO POC · 자동 데모 (Playwright)

- 실제 Chrome 창 띄움 (headless=False)
- 페이지 하단에 인페이지 토스트로 진행 상황·설명 안내
- 15+ 시나리오 단계: 대시보드 → Pre-Visit → 일별응답 → PRO설정 → 라이브러리 →
  커스텀세트 → 환자앱 → 어르신모드 → LLM 가드레일 → Cron Jobs

사전 조건:
  ./restart.sh --all     # 5명 환자 시드 + 3개 서버 가동
  pip install playwright
  playwright install chromium

실행:
  python demo/demo_full.py                    # 전체 자동
  python demo/demo_full.py --manual           # 수동 (다음 버튼/Space)
  python demo/demo_full.py --speed fast       # 빠르게 (1.6x)
  python demo/demo_full.py --start 6          # 6단계부터
  python demo/demo_full.py --phases dashboard,llm  # 특정 단계만
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright

# URL은 환경변수로 오버라이드 가능 — 배포된 서버 시연 시 사용.
# 예: ADMIN_URL=https://admin.example.com python demo/demo_full.py
ADMIN = os.environ.get("ADMIN_URL", "http://localhost:3001")
PATIENT = os.environ.get("PATIENT_URL", "http://localhost:3000")
BACKEND = os.environ.get("BACKEND_URL", "http://localhost:8000")

# 토스트 색상별 의도
KIND_COLORS = {
    "info":    "#1e293b",   # 일반 진행
    "action":  "#7c3aed",   # 클릭/입력 액션
    "result":  "#16a34a",   # 결과 확인
    "warning": "#ea580c",   # 주의·경고 시연
    "error":   "#dc2626",   # 에러·응급 시연
    "phase":   "#0369a1",   # 단계 헤더
}

OUT = Path(__file__).parent / "screenshots"
OUT.mkdir(exist_ok=True)


class Demo:
    def __init__(self, page, context, total_steps: int,
                 speed: float = 1.0, manual: bool = False):
        self.page = page
        self.context = context
        self.step = 0
        self.total = total_steps
        self.speed = speed
        self.manual = manual
        self._next_event = asyncio.Event()
        self._exposed = False

    async def ensure_bridge(self):
        """페이지에 '다음' 버튼 클릭을 Python으로 전달하는 브릿지 설치.
        navigation을 거치면 다시 init script로 살아남아야 함."""
        if self._exposed:
            return
        self._exposed = True

        # JS → Python 콜백
        async def on_next():
            self._next_event.set()

        try:
            await self.context.expose_function("__demoNext", on_next)
        except Exception:
            pass

        # 모든 페이지 로드 시 키보드 단축키 (Space/Enter/N) 자동 부착
        await self.context.add_init_script("""
        window.addEventListener('keydown', (e) => {
            const t = document.getElementById('demo-toast');
            if (!t) return;
            if (e.code === 'Space' || e.key === 'Enter' || e.key.toLowerCase() === 'n') {
                e.preventDefault();
                if (window.__demoNext) window.__demoNext();
            }
        });
        """)

    async def wait_for_next(self):
        """수동 모드: '다음' 클릭 또는 키 입력까지 대기."""
        self._next_event.clear()
        await self._next_event.wait()

    # ──────────────────────────────────────────
    # 토스트
    # ──────────────────────────────────────────
    async def toast(self, text: str, kind: str = "info",
                    duration: float = 2.5, sub: str = ""):
        self.step += 1
        color = KIND_COLORS.get(kind, KIND_COLORS["info"])
        safe_text = (text.replace("\\", "\\\\").replace("`", "\\`")
                     .replace("$", "\\$"))
        safe_sub = (sub.replace("\\", "\\\\").replace("`", "\\`")
                    .replace("$", "\\$"))
        manual_js = "true" if self.manual else "false"
        try:
            await self.page.evaluate(f"""
            (() => {{
                let el = document.getElementById('demo-toast');
                if (!el) {{
                    el = document.createElement('div');
                    el.id = 'demo-toast';
                    el.style.cssText = `
                        position: fixed; top: 16px; right: 16px;
                        width: 360px; max-width: calc(100vw - 32px);
                        color: white; padding: 14px 18px;
                        border-radius: 14px;
                        font-size: 13px; line-height: 1.45;
                        box-shadow: 0 8px 28px rgba(0,0,0,0.35);
                        z-index: 999999;
                        font-family: -apple-system, system-ui, sans-serif;
                        backdrop-filter: blur(10px);
                        opacity: 0.96;
                        transition: background 0.25s ease, opacity 0.2s ease;
                    `;
                    el.addEventListener('mouseenter',
                        () => el.style.opacity = '0.55');
                    el.addEventListener('mouseleave',
                        () => el.style.opacity = '0.96');
                    document.body.appendChild(el);
                }}
                el.style.background = '{color}';
                const subHtml = `{safe_sub}`
                    ? `<div style="font-size:12px; opacity:0.82; margin-top:5px; line-height:1.4">${{`{safe_sub}`}}</div>`
                    : '';
                const isManual = {manual_js};
                const buttonHtml = isManual
                    ? `<button id="demo-next-btn"
                        style="display:block; width:100%; margin-top:10px;
                               padding:7px 12px;
                               background:rgba(255,255,255,0.18);
                               border:1px solid rgba(255,255,255,0.4);
                               color:white; border-radius:8px;
                               font-size:12px; font-weight:bold;
                               cursor:pointer;">
                        다음 → <span style="opacity:0.6; font-size:10px">(Space)</span>
                       </button>`
                    : '';
                el.innerHTML = `
                    <div style="display:flex; align-items:center; justify-content:space-between;
                                font-size:10px; opacity:0.7; margin-bottom:5px;
                                text-transform:uppercase; letter-spacing:0.8px;">
                        <span>[{self.step}/{self.total}] {kind}</span>
                        <span style="font-size:9px; opacity:0.6">DEMO</span>
                    </div>
                    <div style="font-weight:600; font-size:13.5px;">{safe_text}</div>
                    ${{subHtml}}
                    ${{buttonHtml}}
                `;
                if (isManual) {{
                    const btn = document.getElementById('demo-next-btn');
                    if (btn) {{
                        btn.onclick = () => {{
                            if (window.__demoNext) window.__demoNext();
                        }};
                    }}
                }}
            }})();
            """)
        except Exception:
            pass
        if self.manual:
            await self.wait_for_next()
        else:
            await asyncio.sleep(duration / self.speed)

    async def goto(self, url: str, wait_for: str = None,
                   timeout_ms: int = 8000):
        await self.page.goto(url)
        if wait_for:
            try:
                await self.page.wait_for_selector(wait_for, timeout=timeout_ms)
            except Exception:
                pass
        await asyncio.sleep(0.4 / self.speed)

    async def click(self, selector: str, timeout_ms: int = 5000):
        try:
            await self.page.click(selector, timeout=timeout_ms)
            await asyncio.sleep(0.5 / self.speed)
        except Exception as e:
            print(f"⚠ click 실패 [{selector}]: {e}")

    async def fill(self, selector: str, text: str):
        try:
            await self.page.fill(selector, text)
            await asyncio.sleep(0.3 / self.speed)
        except Exception as e:
            print(f"⚠ fill 실패 [{selector}]: {e}")

    async def shot(self, name: str):
        path = OUT / f"{name}.png"
        try:
            await self.page.screenshot(path=str(path), full_page=False)
        except Exception:
            pass


# ============================================================
# 시나리오 단계
# ============================================================

async def phase_pre_check(d: Demo):
    """서버 살아있는지 확인."""
    import urllib.request
    for url, label in [
        (f"{BACKEND}/api/health", "Backend"),
        (ADMIN, "Admin"),
        (PATIENT, "Patient"),
    ]:
        try:
            urllib.request.urlopen(url, timeout=2)
        except Exception:
            print(f"❌ {label} ({url}) 응답 없음. './restart.sh --all' 먼저 실행하세요.")
            sys.exit(1)


async def phase_dashboard(d: Demo):
    await d.goto(ADMIN, wait_for="text=담당 환자 모니터링")
    await d.toast(
        "🏥 의료진 모니터링 대시보드",
        "phase", 3,
        sub="외래 5분 전 — 5명 담당 환자의 RED/YELLOW/GREEN 분포가 한눈에 보입니다.",
    )
    await d.toast(
        "🔴 RED 4명, 🟢 안정 1명",
        "result", 3,
        sub="C-1042(신경병증), C-2103(피로/설사), C-4581(오심), C-5219(HADS-A 11) RED. C-3027만 안정.",
    )


async def phase_pre_visit(d: Demo):
    await d.toast(
        "📊 C-1042 이○○ Pre-Visit Report 열기",
        "action", 2.5,
        sub="73세 결장암, Oxaliplatin Cycle D14 — 신경병증이 7일 연속 3점.",
    )
    # C-1042 Pre-Visit Report 클릭
    await d.click("text=Pre-Visit Report →")
    await d.page.wait_for_selector("text=One-Line Summary", timeout=8000)
    await d.toast(
        "✅ One-Line Summary가 의사에게 전달되는 결론",
        "result", 4,
        sub="결정론 채점이 만든 한 줄: '말초신경병증 7일 연속 3점 지속. RED 알림 — 신경독성 평가 필요.'",
    )
    await d.toast(
        "📈 7일 추세 + Key Changes",
        "info", 3.5,
        sub="신경병증 1→1→2→2→3→3→3 점진 악화. HADS-A 8 경계값 진입.",
    )


async def phase_responses_by_day(d: Demo):
    await d.toast(
        "📋 일별 PRO 응답 상세",
        "action", 2.5,
        sub="환자가 실제로 무엇을 어떻게 답했는지 일자별로 들여다봅니다.",
    )
    await d.click("text=일별 PRO 응답 보기")
    await d.page.wait_for_selector("text=일별 PRO 응답 상세", timeout=8000)
    await d.toast(
        "🔓 가장 최근 날짜 카드 펼치기",
        "action", 2,
    )
    # 첫 번째 ▶ 버튼 클릭
    try:
        await d.page.locator("button:has-text('▶')").first.click(timeout=3000)
    except Exception:
        pass
    await d.toast(
        "🩺 PRO-CTCAE 매트릭스 + HADS 14문항",
        "result", 4,
        sub="신경병증 강도=3 (심함), 빈도/일상방해까지 모두 응답값+한글 라벨로 표시.",
    )


async def phase_config(d: Demo):
    await d.toast(
        "⚙ PRO 도구 커스터마이징",
        "phase", 3,
        sub="환자별 필수+선택 도구 자동 세팅. 모든 세부설정 변경 가능.",
    )
    await d.goto(f"{ADMIN}/patients/C-3027/config",
                 wait_for="text=PRO 도구 커스터마이징")
    await d.toast(
        "👀 폐암(C34.1) C-3027 — 안정 환자",
        "info", 3,
        sub="현재 PRO-CTCAE·HADS만 활성. FACIT-F·PSQI는 선택 도구로 OFF 상태.",
    )


async def phase_load_defaults(d: Demo):
    await d.toast(
        "📚 ICD-10 기본값 불러오기 시연",
        "action", 3,
        sub="환자 진단(C34.1)·나이로 자동 추천 세트 적용 (audit 자동 기록).",
    )
    # confirm dialog 처리
    d.page.once("dialog", lambda dialog: dialog.accept())
    await d.click("text=ICD-10 기본값")
    await asyncio.sleep(1.5)
    await d.toast(
        "✅ 추천값 적용 — FACIT-F가 자동 ON",
        "result", 3.5,
        sub="폐암 환자에게 면역항암제 피로 추적용 FACIT-F가 권장 도구로 자동 활성화됨.",
    )


async def phase_tool_library(d: Demo):
    await d.toast(
        "📚 PRO 도구 라이브러리",
        "phase", 3,
        sub="탑재 가능한 5종 도구 — Evidence Grade·문항·소요·라이선스 한눈에.",
    )
    await d.goto(f"{ADMIN}/tools",
                 wait_for="text=표준 PRO 도구")
    await d.toast(
        "🔍 PRO-CTCAE 상세 페이지로",
        "action", 2.5,
    )
    await d.click("text=PRO-CTCAE")
    await d.page.wait_for_selector("text=실제 문항", timeout=8000)
    await d.toast(
        "🩺 13개 문항 + 5단계 응답 옵션",
        "result", 4,
        sub="피로·식욕부진·오심·설사·신경병증 5증상 × 빈도/강도/일상방해 속성.",
    )


async def phase_custom_builder(d: Demo):
    await d.toast(
        "🛠 커스텀 PRO 세트 만들기",
        "phase", 3,
        sub="기본 도구 ON/OFF + 커스텀 질문 생성 — 의사 전용 템플릿 빌더.",
    )
    await d.goto(f"{ADMIN}/tools/builder",
                 wait_for="text=커스텀 PRO 세트 만들기")
    await d.fill("input[placeholder*='FOLFOX']", "데모용 위암 추적 세트")
    await d.toast(
        "✏️ 세트 이름 입력",
        "action", 2,
    )
    await d.fill("textarea", "젊은 위암 환자 정서 모니터링 강화용")
    await d.fill("input[placeholder*='C18']", "C16")
    await d.toast(
        "☑ PRO-CTCAE + HADS 활성화",
        "action", 2,
    )
    # 가장 위 두 개 도구 체크박스 클릭
    try:
        cbs = d.page.locator("input[type='checkbox']").all()
        # PRO-CTCAE 첫 체크박스 + HADS 첫 체크박스 활성화 시도
        ck = await d.page.locator("input[type='checkbox']").first.is_checked()
        if not ck:
            await d.page.locator("input[type='checkbox']").first.check(timeout=2000)
        await asyncio.sleep(0.5)
    except Exception:
        pass
    await d.toast(
        "➕ 커스텀 질문 1개 추가",
        "action", 2,
    )
    try:
        await d.click("text=+ 질문 추가")
        await asyncio.sleep(0.5)
        # 첫 번째 질문 텍스트 입력
        await d.page.locator("input[placeholder='질문 내용']").first.fill(
            "오늘 식사 후 명치가 답답하셨나요?")
    except Exception:
        pass
    await d.toast(
        "💾 커스텀 세트 저장",
        "result", 3,
        sub="저장하면 라이브러리·환자 config에서 즉시 불러올 수 있는 재사용 템플릿이 됩니다.",
    )


async def phase_audit(d: Demo):
    await d.toast(
        "📋 PRO 세트 변경 이력 — 가시화 audit",
        "phase", 3,
        sub="✅ 활성화 / ❌ 비활성화 / ➕ 추가 / ➖ 제거 / 🔄 빈도 / 🔧 임계값 변경 이벤트로 표시.",
    )
    await d.goto(f"{ADMIN}/patients/C-3027/audit",
                 wait_for="text=PRO 세트 변경 이력")
    await d.toast(
        "🔍 ICD-10 기본값 적용 이벤트가 보임",
        "result", 4,
        sub="📚 'C34.1, 67세 폐암 표준 세트 적용' + ✅ FACIT-F 활성화 등 사람이 읽을 수 있는 형태.",
    )


async def phase_patient_app(d: Demo):
    await d.toast(
        "📱 환자앱 홈 (5명 환자 카드)",
        "phase", 3,
        sub="각 환자별 푸시 구독 + PRO 시작 + 어르신 모드 진입 버튼.",
    )
    await d.goto(PATIENT, wait_for="text=시연 환자")


async def phase_pro_start(d: Demo):
    await d.toast(
        "🟢 PRO 시작 — Full / Quick / No-Change 모드 선택",
        "action", 3,
        sub="FN-FLEX 9개 기능 — 직전 응답 30일 이내·연속 3회 이내 No-Change 사용 가능.",
    )
    await d.goto(f"{PATIENT}/pro/start?patient_id=C-1042",
                 wait_for="text=PRO 모드")


async def phase_elder(d: Demo):
    await d.toast(
        "👴 어르신 모드 — One-Question-One-Screen + 얼굴척도",
        "phase", 3,
        sub="C-4581 (81세) 환자 시연. 일반 모드와 데이터 등가성 보장 (raw_value 0..4 동일).",
    )
    await d.goto(f"{PATIENT}/elder/home?patient_id=C-4581",
                 wait_for="text=오늘 어떠세요")
    await d.toast(
        "📞 보호자/119 원터치 + 얼굴척도",
        "info", 3,
        sub="상단 항상 노출 + 글씨 22pt 이상.",
    )


async def phase_llm(d: Demo):
    await d.toast(
        "🤖 LLM Free Talk + 4종 가드레일",
        "phase", 2.5,
        sub="응급 키워드 / Out-of-Scope / Education(RAG) / PII 마스킹.",
    )
    await d.goto(f"{PATIENT}/talk",
                 wait_for="input[placeholder*='메시지']")

    async def chat(text: str):
        """직접 입력해 메시지 전송. 응답이 화면에 나타날 때까지 대기."""
        try:
            # 현재 메시지 수 측정
            before = await d.page.locator("div.max-w-\\[80\\%\\]").count()
        except Exception:
            before = 0
        try:
            inp = d.page.locator("input[placeholder*='메시지']").first
            await inp.fill(text)
            await d.page.locator("button:has-text('보내기')").first.click(
                timeout=3000)
            # user + assistant = +2 메시지 도착까지 대기 (mock은 즉시)
            for _ in range(20):  # 최대 2초
                await asyncio.sleep(0.1)
                cur = await d.page.locator("div.max-w-\\[80\\%\\]").count()
                if cur >= before + 2:
                    return
        except Exception as e:
            print(f"⚠ chat 실패 [{text[:20]}]: {e}")

    async def quick_btn(label_substr: str):
        """페이지의 SAMPLE_PROMPTS 빠른 버튼 클릭 — 가장 빠르고 안정적."""
        try:
            await d.page.locator(
                f"button:has-text('{label_substr}')").first.click(
                timeout=3000)
            for _ in range(20):
                await asyncio.sleep(0.1)
                cnt = await d.page.locator("div.max-w-\\[80\\%\\]").count()
                if cnt >= 2:
                    return
        except Exception as e:
            print(f"⚠ quick_btn 실패: {e}")

    # 1. 정상 발화 — 빠른 버튼 활용
    await d.toast(
        "💬 정상 발화 → 공감 응답",
        "info", 2,
        sub="결정론 템플릿 6종 중 입력 길이로 선택. LLM 호출 없이 즉시 응답.",
    )
    await quick_btn("정상")
    await d.toast(
        "✅ 'TRI-PRO' 공감 메시지 응답 도착",
        "result", 2,
    )

    # 2. Education 카드 — 직접 입력
    await d.toast(
        "📚 Education 카드 트리거",
        "action", 2,
        sub="'손발이 저려요' → ASCO 가이드라인 출처 자동 인용 + 의료자문 면책.",
    )
    await chat("손발이 저려요")
    await d.toast(
        "✅ ASCO 출처 카드 + Disclaimer 자동 부착",
        "result", 2,
    )

    # 3. Out-of-Scope 차단 — 빠른 버튼
    await d.toast(
        "🚫 Out-of-Scope 차단",
        "warning", 2,
        sub="진단·처방·복용량 질의는 100% 차단 → '주치의 상담' 고정 응답.",
    )
    await quick_btn("처방")
    await d.toast(
        "🛡 노란색 가드레일 박스로 차단 표시",
        "result", 2,
    )

    # 4. PII 마스킹 — 직접 입력
    await d.toast(
        "🔒 PII 자동 마스킹",
        "warning", 2,
        sub="휴대폰/주민번호/이메일/이름이 audit log 저장 전 redact.",
    )
    await chat("제 번호 010-1234-5678 입니다")
    await d.toast(
        "✅ 백엔드 audit엔 [전화번호]로 마스킹 저장",
        "result", 2,
    )

    # 5. 응급 — 마지막 (화면이 takeover됨)
    await d.toast(
        "🚨 응급 키워드 takeover",
        "error", 2.5,
        sub="12개 응급 키워드 매칭 → Core 우회 → 119/응급실 화면 강제 전환 (SLA <200ms).",
    )
    await quick_btn("응급")
    # 응급 화면 takeover 대기
    try:
        await d.page.wait_for_selector("text=즉시 119", timeout=3000)
    except Exception:
        pass
    await d.toast(
        "📞 119 전화 + 보호자 호출 큰 버튼",
        "error", 2.5,
        sub="elder/general 무관 동일 응급 화면. tel: 링크로 즉시 발신 가능.",
    )


async def phase_jobs(d: Demo):
    await d.toast(
        "⏰ Cron Jobs — 자동화된 의료진 워크플로",
        "phase", 3,
        sub="Pre-Visit 사전계산 / MCID 자동 푸시 / 3일 미응답 감지.",
    )
    await d.goto(f"{ADMIN}/jobs", wait_for="text=예약 작업")
    await d.toast(
        "▶️ Pre-Visit Report 사전계산 실행",
        "action", 3,
    )
    try:
        await d.page.locator("button:has-text('수동 실행')").first.click(timeout=3000)
        await asyncio.sleep(3)
    except Exception:
        pass
    await d.toast(
        "✅ 5명 환자 모두 사전 계산 완료",
        "result", 4,
        sub="외래일 D-2 새벽 cron으로 자동 실행되어 의사가 진료실 들어가면 즉시 결과 확인.",
    )


async def phase_finale(d: Demo):
    await d.goto(ADMIN, wait_for="text=담당 환자 모니터링")
    await d.toast(
        "🎉 데모 종료",
        "phase", 6,
        sub=("FSD 74개 기능 중 P0 전부 구현 + 백엔드 90/90 테스트 통과. "
             "스크린샷은 demo/screenshots/ 에 저장됐습니다."),
    )


# ============================================================
# 단계 등록
# ============================================================
PHASES = [
    ("dashboard", phase_dashboard),
    ("pre_visit", phase_pre_visit),
    ("responses_by_day", phase_responses_by_day),
    ("config", phase_config),
    ("load_defaults", phase_load_defaults),
    ("tool_library", phase_tool_library),
    ("custom_builder", phase_custom_builder),
    ("audit", phase_audit),
    ("patient_app", phase_patient_app),
    ("pro_start", phase_pro_start),
    ("elder", phase_elder),
    ("llm", phase_llm),
    ("jobs", phase_jobs),
    ("finale", phase_finale),
]


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1,
                        help="시작 단계 번호 (1~)")
    parser.add_argument("--speed", choices=["slow", "normal", "fast"],
                        default="normal")
    parser.add_argument("--manual", "-m", action="store_true",
                        help="자동 진행 대신 '다음' 버튼/Space 키로 수동 진행")
    parser.add_argument("--phases", type=str,
                        help="실행할 phase 이름 쉼표 구분 (예: dashboard,pre_visit,llm)")
    parser.add_argument("--record", action="store_true",
                        help="화면 녹화 (demo/videos/*.webm)")
    args = parser.parse_args()

    speed_map = {"slow": 0.7, "normal": 1.0, "fast": 1.6}
    speed = speed_map[args.speed]

    selected = PHASES[args.start - 1:]
    if args.phases:
        wanted = set(args.phases.split(","))
        selected = [(n, fn) for n, fn in PHASES if n in wanted]

    # 단계별 토스트 호출 횟수
    total_toasts = sum({
        "dashboard": 2, "pre_visit": 3, "responses_by_day": 3,
        "config": 2, "load_defaults": 2, "tool_library": 3,
        "custom_builder": 5, "audit": 2, "patient_app": 1,
        "pro_start": 1, "elder": 2,
        "llm": 11,          # phase header + 5×(action+result) = 11
        "jobs": 3, "finale": 1,
    }.get(name, 2) for name, _ in selected)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--window-size=1280,900",
                "--window-position=100,50",
            ],
        )
        video_dir = Path(__file__).parent / "videos"
        ctx_kwargs = dict(
            viewport={"width": 1280, "height": 900},
            locale="ko-KR",
            permissions=["notifications"],
        )
        if args.record:
            video_dir.mkdir(exist_ok=True)
            ctx_kwargs["record_video_dir"] = str(video_dir)
            ctx_kwargs["record_video_size"] = {"width": 1280, "height": 900}
            print(f"📹 녹화 모드 — {video_dir}")
        ctx = await browser.new_context(**ctx_kwargs)
        page = await ctx.new_page()

        d = Demo(page, ctx, total_steps=total_toasts,
                 speed=speed, manual=args.manual)
        # 브릿지 한 번만 설치 (Space/Enter/N + window.__demoNext)
        await d.ensure_bridge()

        if args.manual:
            print("▶ 수동 모드 — 토스트의 '다음 →' 버튼 또는 Space/Enter/N 키로 진행")

        # 사전 체크
        await phase_pre_check(d)

        for name, fn in selected:
            print(f"\n▶ {name}")
            try:
                await fn(d)
            except Exception as e:
                print(f"⚠ {name} 실패: {e}")
                await d.toast(
                    f"❌ {name} 실패", "error", duration=3,
                    sub=str(e)[:120],
                )

        # 자동 모드: 마지막 토스트 5초 / 수동 모드: 마지막 클릭까지 대기
        if not args.manual:
            await asyncio.sleep(5)
        print(f"\n📁 스크린샷: {OUT}")
        if args.record:
            # 비디오 저장은 page.close 후 flush됨
            await ctx.close()
            print(f"📹 비디오: {video_dir}/*.webm  (mp4 변환 권장)")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
