"""
TRI-PRO POC · Playwright 자동 데모
Chrome (Chromium)을 띄워 7단계 시나리오를 자동 실행하고 screenshots/ 에 캡처.

실행 전:
  ./venv/bin/python -m pip install playwright
  ./venv/bin/python -m playwright install chromium
실행:
  ./venv/bin/python demo/demo_auto.py
"""
import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright

BACKEND = "http://localhost:8000"
PATIENT = "http://localhost:3000"
ADMIN = "http://localhost:3001"

OUT = Path(__file__).parent / "screenshots"
OUT.mkdir(exist_ok=True)

NARRATION = []

def say(step: int, text: str):
    line = f"[{step}] {text}"
    print(line)
    NARRATION.append(line)


async def shot(page, name: str):
    path = OUT / f"{name}.png"
    await page.screenshot(path=str(path), full_page=True)
    print(f"     📸 {path.name}")


async def wait(ms: int = 1500):
    await asyncio.sleep(ms / 1000)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--window-size=1280,900"],
        )
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="ko-KR",
            permissions=["notifications"],
        )

        # ── 1. 어드민 대시보드 ────────────────────────────────
        admin = await ctx.new_page()
        say(1, "의료진 모니터링 대시보드 (C-1042 🔴 긴급)")
        await admin.goto(ADMIN)
        await admin.wait_for_selector("text=담당 환자 모니터링")
        await wait(2000)
        await shot(admin, "01_admin_dashboard")

        # ── 2. Pre-Visit Report ──────────────────────────────
        say(2, "Pre-Visit Report (요약·추세·Key Changes)")
        await admin.click("text=Pre-Visit Report")
        await admin.wait_for_selector("text=One-Line Summary")
        await wait(2500)
        await shot(admin, "02_pre_visit_report")

        # ── 3. 환자앱 홈 + Web Push 구독 ───────────────────────
        patient = await ctx.new_page()
        say(3, "환자앱 홈 — Web Push 구독")
        await patient.goto(PATIENT)
        await patient.wait_for_selector("text=PRO 설문")
        await wait(1500)
        # 구독 버튼 시도 (이름이 페이지마다 다를 수 있어 best-effort)
        try:
            await patient.click("text=Web Push 알림 구독", timeout=2000)
            await wait(1500)
        except Exception:
            pass
        await shot(patient, "03_patient_home_subscribed")

        # ── 4. 어드민에서 푸시 발송 ───────────────────────────
        say(4, "어드민 → 환자 PRO 푸시 발송")
        await admin.bring_to_front()
        try:
            await admin.click("text=환자에게 PRO 알림 푸시")
            await wait(2500)
            await shot(admin, "04_push_sent")
        except Exception as e:
            print(f"     ⚠ 푸시 버튼 클릭 실패: {e}")

        # ── 5. PRO 설문 → 결과 ────────────────────────────────
        say(5, "PRO 설문 (신경병증=3, HADS-A 약간) 후 결과")
        await patient.bring_to_front()
        await patient.goto(f"{PATIENT}/pro")
        await patient.wait_for_selector("text=PRO-CTCAE", timeout=5000)
        await wait(1500)
        await shot(patient, "05a_pro_form")
        # 자동 응답: 모든 라디오의 3번째 옵션 선택 (best-effort)
        try:
            radios = await patient.query_selector_all('input[type="radio"]')
            for i, r in enumerate(radios):
                if i % 5 == 2:  # 5단계 중 중간값
                    await r.click()
            submit = await patient.query_selector('button[type="submit"]')
            if submit:
                await submit.click()
                await patient.wait_for_url("**/result", timeout=5000)
                await wait(2000)
                await shot(patient, "05b_pro_result")
        except Exception as e:
            print(f"     ⚠ 자동 응답 실패: {e}")

        # ── 6. 어르신 모드 ───────────────────────────────────
        say(6, "어르신 모드 (One-Question-One-Screen + 얼굴척도)")
        await patient.goto(f"{PATIENT}/elder/home")
        await patient.wait_for_selector("text=오늘 어떠세요", timeout=5000)
        await wait(1500)
        await shot(patient, "06a_elder_home")
        try:
            await patient.click("text=설문 시작")
            await wait(2000)
            await shot(patient, "06b_elder_face_scale")
        except Exception:
            pass

        # ── 7. LLM Free Talk · Guardrail ─────────────────────
        say(7, "LLM Free Talk — 공감 / Out-of-Scope / 응급 takeover")
        await patient.goto(f"{PATIENT}/talk")
        await patient.wait_for_selector("textarea, input[type='text']", timeout=5000)
        await wait(1000)

        async def chat(text: str, label: str):
            box = await patient.query_selector("textarea") or \
                  await patient.query_selector("input[type='text']")
            if not box:
                print(f"     ⚠ 입력창 못 찾음 ({label})")
                return
            await box.fill(text)
            send = await patient.query_selector("button:has-text('전송')") or \
                   await patient.query_selector("button[type='submit']")
            if send:
                await send.click()
            await wait(2500)
            await shot(patient, f"07_talk_{label}")

        await chat("오늘 좀 우울해요", "a_empathy")
        await chat("약 더 먹어도 되나요?", "b_oos")
        await chat("숨이 안 쉬어져요", "c_emergency")

        print()
        print("=" * 50)
        print(" ✅ 데모 자동 실행 완료")
        print(f" 📁 스크린샷: {OUT}")
        print("=" * 50)
        await wait(3000)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
