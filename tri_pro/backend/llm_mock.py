"""Step 2 LLM-Augmented Layer — Mock 모드 + Real 폴백.

LLM_MODE=mock(기본) — 결정론 템플릿·키워드 매칭만 사용 (LLM 호출 0건).
LLM_MODE=real    — Anthropic API 호출 (응급/OoS는 여전히 사전 매칭이라 통과 시에만).

구현된 가드레일 (FSD §2.7):
  FN-LLM-008  응급 키워드 12개 감지 → 119 takeover (SLA <200ms)
  FN-LLM-007  Out-of-Scope 패턴 20개 → "주치의 상담" 고정 응답
  FN-LLM-006  Education 카드 정적 매핑 (RAG 대체)
  FN-LLM-009  답변 출처 강제 (Education 카드 source citation 자동)
  FN-LLM-011  PII 자동 마스킹 (휴대폰·주민번호·이메일·이름)
  FN-LLM-005  Empathic Response 템플릿 6종 (deterministic 선택)

분기 우선순위:
  1. PII redact (모든 분기 전)
  2. 응급 키워드 (최우선)
  3. Out-of-Scope
  4. Education 카드 키워드
  5. 정상 발화 → mock 템플릿 또는 real LLM

핵심 원칙: 응급·OoS는 사전 매칭이라 mock=real 동일 결과 보장.
LLM 응답에는 disclaimer footer 자동 부착.
"""
import random
import re
from typing import Optional
from config import settings


# ============================================================
# FN-LLM-011 PII 마스킹 — 한국 환경 휴리스틱
# ============================================================
# 휴대폰: 010-XXXX-XXXX, 010 XXXXXXXX, 01012345678
PHONE_REGEX = re.compile(
    r"(01[016789])[-\s]?(\d{3,4})[-\s]?(\d{4})"
)
# 주민번호: 6-7자리
RRN_REGEX = re.compile(r"\d{6}[-\s]?[1-4]\d{6}")
# 이메일
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
# 한국어 성+이름 (성 1자 + 이름 2자) — 흔한 성 50자 화이트리스트
KOREAN_SURNAMES = (
    "김이박최정강조윤장임한오서신권황안송류전홍고문양손배"
    "조백허유남심노하곽성차주우구민나진지엄변채원천방공"
)
# 단어 시작 위치(앞에 한글 없음)에서만 surname 매칭 — "주민번호" 같은 합성어 오탐 방지
NAME_REGEX = re.compile(
    rf"(?<![가-힣])([{KOREAN_SURNAMES}])([가-힣]{{2}})(?=[\s,.은는이가의을를과와에서])"
)


def redact_pii(text: str) -> tuple[str, list[str]]:
    """텍스트 내 PII 자동 마스킹. 변경된 카테고리 리스트 반환.

    적용 순서: RRN(13자리) → phone(11자리) → email → name.
    더 긴 패턴부터 처리해야 phone이 RRN의 일부를 침범하지 않음.
    """
    redacted = []
    if RRN_REGEX.search(text):
        text = RRN_REGEX.sub("[주민번호]", text)
        redacted.append("rrn")
    if PHONE_REGEX.search(text):
        text = PHONE_REGEX.sub("[전화번호]", text)
        redacted.append("phone")
    if EMAIL_REGEX.search(text):
        text = EMAIL_REGEX.sub("[이메일]", text)
        redacted.append("email")
    new_text = NAME_REGEX.sub(r"[이름]", text)
    if new_text != text:
        redacted.append("name")
        text = new_text
    return text, redacted


# ============================================================
# FN-LLM-006 Education Cards (정적 매핑) — RAG 대체
# ============================================================
EDUCATION_CARDS = [
    {
        "trigger_keyword": ["저림", "감각", "신경병증", "손발이"],
        "title": "손발 저림(말초신경병증) 관리",
        "body": (
            "Oxaliplatin·Paclitaxel 계열 항암제는 말초신경병증을 유발할 수 있어요. "
            "찬물·추운 환경 노출을 줄이고 따뜻하게 유지하시는 것이 도움이 됩니다. "
            "증상이 악화되면 주치의에게 알려 용량 조정을 검토할 수 있어요."
        ),
        "source_label": "ASCO Practice Guideline 2024",
        "source_url": "https://www.asco.org/practice-patients/guidelines",
    },
    {
        "trigger_keyword": ["피곤", "지친", "기력", "피로"],
        "title": "암성 피로 관리",
        "body": (
            "암성 피로는 흔하며 휴식만으로는 해결되지 않는 경우가 많아요. "
            "가벼운 운동(걷기 30분/일)과 규칙적인 수면이 도움이 된다고 알려져 있습니다. "
            "피로가 심해 일상생활이 어려우면 외래 시 알려주세요."
        ),
        "source_label": "NCCN Guidelines: Cancer-Related Fatigue v1.2024",
        "source_url": "https://www.nccn.org/guidelines/category_3",
    },
    {
        "trigger_keyword": ["메스꺼", "토할", "구역", "오심"],
        "title": "오심·구토 관리",
        "body": (
            "처방받은 항구토제는 증상 발생 전에 미리 복용하는 것이 효과적이에요. "
            "기름지거나 향이 강한 음식은 피하고, 소량씩 자주 드시는 것이 좋습니다. "
            "24시간 내 5회 이상 구토가 지속되면 병원에 연락하세요."
        ),
        "source_label": "NCCN Antiemesis Guidelines 2024",
        "source_url": "https://www.nccn.org/guidelines/category_3",
    },
    {
        "trigger_keyword": ["우울", "슬픔", "기분", "불안"],
        "title": "정서 건강 돌보기",
        "body": (
            "암 치료 중 우울·불안은 흔합니다. 혼자 견디지 않으셔도 돼요. "
            "가족과 친구에게 마음을 나누고, 필요하면 정신건강의학과 상담을 받을 수 있어요. "
            "증상이 2주 이상 지속되면 외래 때 의료진과 상의해보세요."
        ),
        "source_label": "ASCO Survivorship Care Guidelines 2024",
        "source_url": "https://www.asco.org/practice-patients/guidelines",
    },
]


def find_education_card(text: str) -> Optional[dict]:
    """발화 키워드 매칭으로 적합한 교육 카드 1건 반환."""
    for card in EDUCATION_CARDS:
        if any(kw in text for kw in card["trigger_keyword"]):
            return card
    return None


# ============================================================
# 응급 키워드 12개 (FN-LLM-008)
# ============================================================
EMERGENCY_KEYWORDS = [
    "숨이 안 쉬", "숨이 안쉬", "숨을 못 쉬",
    "피가 나",
    "가슴이 너무 아",
    "쓰러질 것 같",
    "쓰러졌",
    "의식이 없",
    "심하게 어지러",
    "토할 것 같",
    "심장이 빨라",
    "기절할 것",
    "응급실",
]

EMERGENCY_RESPONSE = (
    "지금 즉시 119에 전화하시거나 가까운 응급실로 가셔야 해요. "
    "보호자에게도 같이 알릴게요."
)


# ============================================================
# Out-of-Scope 패턴 20개 (FN-LLM-007)
# ============================================================
OUT_OF_SCOPE_PATTERNS = [
    "약 더 먹", "약 더먹", "복용량",
    "처방", "약 바꿔",
    "용량 늘",
    "끊어도 되",
    "먹어도 되나요",
    "병이 나",
    "암이 더",
    "재발했",
    "전이됐",
    "수술해야",
    "검사 결과 어떻",
    "내 병명",
    "진단",
    "수치가 좋",
    "예후",
    "오래 살",
    "치료법",
    "어떤 약이 좋",
]

OUT_OF_SCOPE_RESPONSE = (
    "복용량이나 진단 관련은 주치의 상담이 필요해요. "
    "다음 외래 때 선생님께 전해드릴 수 있도록 오늘 증상 점수를 한 번 기록해둘까요?"
)


# ============================================================
# 공감 응답 템플릿 (FN-LLM-005, mock)
# ============================================================
EMPATHIC_TEMPLATES = [
    "지난 시간 많이 힘드셨겠어요. 오늘 기분은 어떠세요?",
    "그러셨군요. 충분히 그럴 수 있어요. 오늘은 좀 어떠신가요?",
    "마음이 무거우셨겠어요. 같이 한 번 점수로 정리해볼까요?",
    "걱정이 많으셨을 것 같아요. 오늘 컨디션을 한 번 체크해드릴게요.",
    "수고 많으셨어요. 오늘도 한 걸음 내디디신 거예요.",
    "솔직하게 말씀해 주셔서 감사해요. 다음 진료 때 도움이 많이 될 거예요.",
]


# ============================================================
# 분류 + 응답 함수
# ============================================================
DISCLAIMER_FOOTER = (
    "\n\n— 이 안내는 일반 정보이며 의료 자문을 대체하지 않습니다."
)


def classify_and_respond(user_text: str) -> dict:
    """사용자 발화 분류 + 응답 생성. PII 마스킹 + Education + 출처 인용 포함.

    Returns:
        {
            "type": "emergency" | "out_of_scope" | "education" | "normal",
            "response": str,
            "matched": str,
            "pii_redacted": list[str],          # 마스킹된 카테고리
            "redacted_text": str,                # 마스킹 후 prompt (audit용)
            "education_card": dict | None,
            "source": dict | None,               # FN-LLM-009 출처
        }
    """
    # 0) PII 마스킹 — 모든 응답 분기 전에 적용
    redacted_text, redacted_categories = redact_pii(user_text)

    # 1) 응급 키워드 (최우선) — 원문 기준 매칭 (마스킹된 텍스트는 키워드 변형 가능)
    for kw in EMERGENCY_KEYWORDS:
        if kw in user_text:
            return {
                "type": "emergency",
                "response": EMERGENCY_RESPONSE,
                "matched": kw,
                "pii_redacted": redacted_categories,
                "redacted_text": redacted_text,
                "education_card": None,
                "source": None,
            }

    # 2) Out-of-Scope
    for pattern in OUT_OF_SCOPE_PATTERNS:
        if pattern in user_text:
            return {
                "type": "out_of_scope",
                "response": OUT_OF_SCOPE_RESPONSE + DISCLAIMER_FOOTER,
                "matched": pattern,
                "pii_redacted": redacted_categories,
                "redacted_text": redacted_text,
                "education_card": None,
                "source": None,
            }

    # 3) Education 카드 매칭 (FN-LLM-006)
    card = find_education_card(user_text)
    if card:
        return {
            "type": "education",
            "response": card["body"] + DISCLAIMER_FOOTER,
            "matched": card["trigger_keyword"][0],
            "pii_redacted": redacted_categories,
            "redacted_text": redacted_text,
            "education_card": {
                "title": card["title"],
                "body": card["body"],
            },
            "source": {
                "label": card["source_label"],
                "url": card["source_url"],
            },
        }

    # 4) 정상 발화 — Mock 또는 Real
    if settings.LLM_MODE == "real" and settings.ANTHROPIC_API_KEY:
        result = _real_llm_response(redacted_text)  # PII 제거된 텍스트만 LLM에 전달
        result["pii_redacted"] = redacted_categories
        result["redacted_text"] = redacted_text
        result["education_card"] = None
        result["source"] = None
        result["response"] = result["response"] + DISCLAIMER_FOOTER
        return result

    # Mock 응답 — deterministic
    template = EMPATHIC_TEMPLATES[len(user_text) % len(EMPATHIC_TEMPLATES)]
    return {
        "type": "normal",
        "response": template,
        "matched": "",
        "pii_redacted": redacted_categories,
        "redacted_text": redacted_text,
        "education_card": None,
        "source": None,
    }


def _real_llm_response(user_text: str) -> dict:
    """LLM_MODE=real일 때만 호출. Anthropic API."""
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=(
                "당신은 암 환자 케어 도우미입니다. "
                "공감 메시지를 1-2 문장으로 짧게 답하세요. "
                "진단·처방·복용량 관련 질문은 절대 답하지 마세요."
            ),
            messages=[{"role": "user", "content": user_text}],
        )
        return {
            "type": "normal",
            "response": msg.content[0].text,
            "matched": "",
        }
    except Exception as e:
        # Real 호출 실패 시 mock으로 폴백
        template = random.choice(EMPATHIC_TEMPLATES)
        return {
            "type": "normal",
            "response": template,
            "matched": f"fallback: {type(e).__name__}",
        }
