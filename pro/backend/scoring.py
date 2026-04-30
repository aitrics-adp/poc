"""결정론 PRO 채점 엔진 — Step 1 Core (FN-PRO-006).

지원 도구 5종:
  PRO-CTCAE  (NCI 항암 부작용 — 5증상 × 빈도/강도/일상 방해)
  HADS       (불안 7 + 우울 7 = 14문항, 역채점 7개)
  FACT-C     (대장암 QoL 36문항, 5 서브스케일 + TOI/FACT-G/FACT-C)
  FACIT-F    (암성 피로 13문항, 0..52 점수)
  PSQI       (수면의 질 19문항 → 7 컴포넌트 0..21)

핵심 원칙 (FN-PRO-006):
  1. **Determinism First** — 동일 입력 → 동일 출력 100% 보장
  2. **역채점 명시** — 각 도구의 reverse 항목 하드코딩
  3. **결측 안전** — 50% 이상 응답 시 평균 보정, 미만은 None
  4. **합산 시점 분리** — score_xxx → 원시 점수, evaluate_mcid_xxx → alert flag
  5. **MCID 임계값 주입** — config로 환자별 조정 가능

ui_mode (general/elder)는 이 모듈에서 보지 않음 — 응답값(raw 0..N)만 들어오면 됨.
이로써 일반·어르신 모드 등가성(FN-MODE-007) 자동 보장.
"""
from dataclasses import dataclass
from typing import Optional


# ============================================================
# 1. PRO-CTCAE — 핵심 5문항
# ============================================================
# 각 증상은 빈도/강도/일상방해 3속성 중 일부를 가짐
# 응답: 0..4 (없음/드물게/가끔/자주/거의 항상)
# 채점 원칙: 합산하지 않고 분포 보존. Composite는 max(강도, 일상).

PRO_CTCAE_ITEMS = {
    # symptom_id : { attribute: question_text }
    "fatigue": {
        "freq": "지난 7일 동안 얼마나 피곤하셨나요?",
        "severity": "가장 피곤했을 때 얼마나 심했나요?",
        "interference": "피곤함 때문에 일상생활에 지장이 있었나요?",
    },
    "appetite": {
        "freq": "지난 7일 동안 식욕이 얼마나 없으셨나요?",
        "interference": "식욕부진 때문에 식사에 지장이 있었나요?",
    },
    "nausea": {
        "freq": "지난 7일 동안 속이 메스꺼웠던 적이 있나요?",
        "severity": "가장 메스꺼웠을 때 얼마나 심했나요?",
        "interference": "오심·구토로 인해 생활에 지장이 있었나요?",
    },
    "diarrhea": {
        "freq": "지난 7일 동안 설사가 얼마나 자주 있었나요?",
    },
    "neuropathy": {
        "severity": "손·발이 저리거나 따끔거린 정도는 어땠나요?",
        "interference": "저림 때문에 일상생활에 지장이 있었나요?",
    },
}

PRO_CTCAE_SCALE_LABELS = {
    "freq": ["없음", "드물게", "가끔", "자주", "거의 항상"],
    "severity": ["없음", "약함", "보통", "심함", "매우 심함"],
    "interference": ["없음", "약간", "보통", "많이", "매우 많이"],
}


def score_pro_ctcae_item(symptom: str, attribute: str, raw: int) -> dict:
    """단일 PRO-CTCAE 항목 채점."""
    if not (0 <= raw <= 4):
        raise ValueError(f"PRO-CTCAE raw 값은 0..4: got {raw}")
    grade_labels = ["none", "mild", "moderate", "severe", "very_severe"]
    return {
        "symptom": symptom,
        "attribute": attribute,
        "score": raw,
        "severity_grade": grade_labels[raw],
    }


def score_pro_ctcae_composite(items: list[dict]) -> dict:
    """심각도 중심 복합점수 — max(강도, 일상)."""
    relevant = [i["score"] for i in items
                if i["attribute"] in ("severity", "interference")]
    if not relevant:
        return {"composite": 0, "n": 0}
    return {"composite": max(relevant), "n": len(relevant)}


# ============================================================
# 2. HADS — 14문항 (불안 7 + 우울 7)
# ============================================================
# 각 응답: 0..3 (4단계 리커트)
# 역채점 항목: D1, D2, D3, A4, D5, D6, D7

HADS_ITEMS = [
    # (item_code, subscale, question, reverse)
    ("A1", "A", "나는 긴장되거나 마음이 조마조마하다", False),
    ("D1", "D", "전에 즐기던 일들을 여전히 즐기고 있다", True),
    ("A2", "A", "마치 무슨 나쁜 일이 생길 것 같은 두려운 느낌이 든다", False),
    ("D2", "D", "웃을 수 있고, 재미있는 일에 재미를 느낀다", True),
    ("A3", "A", "걱정되는 생각이 머리에서 떠나지 않는다", False),
    ("D3", "D", "기분이 좋다", True),
    ("A4", "A", "편안하게 앉아 있을 수 있고 마음이 가라앉는다", True),
    ("D4", "D", "어떤 일을 할 때 행동이 느려진 것 같다", False),
    ("A5", "A", "뱃속이 자꾸 울렁거리는 것 같은 두려움을 느낀다", False),
    ("D5", "D", "외모에 관심이 있다", True),
    ("A6", "A", "안절부절 못 한다", False),
    ("D6", "D", "어떤 일에 대해 기대감을 가지고 기다린다", True),
    ("A7", "A", "갑자기 심한 공포감(놀람)에 휩싸인다", False),
    ("D7", "D", "좋은 책·라디오·TV 프로그램을 즐길 수 있다", True),
]

HADS_REVERSE_MAP = {0: 3, 1: 2, 2: 1, 3: 0}


def score_hads_subscale(responses: dict[str, int], subscale: str) -> dict:
    """HADS-A 또는 HADS-D 합산.

    responses: {item_code: raw_value} (0..3)
    subscale: "A" or "D"
    """
    items = [(c, r) for c, s, _, r in HADS_ITEMS if s == subscale]
    raw_responses = {c: responses.get(c) for c, _ in items}

    # 결측 — 하나라도 없으면 MISSING
    if any(v is None for v in raw_responses.values()):
        return {"subscale": f"HADS-{subscale}", "value": None,
                "classification": "missing"}

    total = 0
    for code, reversed_ in items:
        raw = raw_responses[code]
        if not (0 <= raw <= 3):
            raise ValueError(f"HADS raw 값은 0..3: {code}={raw}")
        adjusted = HADS_REVERSE_MAP[raw] if reversed_ else raw
        total += adjusted

    classification = (
        "normal" if total <= 7
        else "borderline" if total <= 10
        else "case"
    )
    return {
        "subscale": f"HADS-{subscale}",
        "value": float(total),
        "classification": classification,
    }


def score_hads(responses: dict[str, int]) -> dict:
    """HADS 전체 채점 — A·D 분리 + 통합."""
    return {
        "hads_a": score_hads_subscale(responses, "A"),
        "hads_d": score_hads_subscale(responses, "D"),
    }


# ============================================================
# 3. MCID 판정 (PRO 매핑 Sheet 8 기준)
# ============================================================

@dataclass
class MCIDRule:
    tool: str
    subscale: Optional[str]
    threshold: float
    direction: str  # "up" (높을수록 양호) | "down" (낮을수록 양호)
    flag_red_at: float  # 절댓값 기준 (cutoff 기반 alert)


MCID_RULES = {
    "HADS-A": MCIDRule("HADS", "HADS-A", 1.5, "down", flag_red_at=11),
    "HADS-D": MCIDRule("HADS", "HADS-D", 1.5, "down", flag_red_at=11),
    "PRO-CTCAE-attr": MCIDRule("PRO-CTCAE", None, 1.0, "down", flag_red_at=2),
}


def evaluate_mcid_hads(
    value: float,
    subscale: str,
    yellow_threshold: int = 8,
    red_threshold: int = 11,
) -> Optional[str]:
    """HADS 절대값 기준 alert. 임계값은 환자별 config로 주입 가능."""
    if value is None:
        return None
    if value >= red_threshold:
        return "red"
    if value >= yellow_threshold:
        return "yellow"
    return None


def evaluate_mcid_pro_ctcae(
    scores: list[dict],
    history: list[float],
    red_threshold: int = 2,
    persist_days: int = 2,
) -> Optional[str]:
    """PRO-CTCAE 속성별: red_threshold 이상이 persist_days 이상 지속 시 RED.

    scores: 오늘의 score 리스트
    history: 같은 속성의 직전 N일 점수 (0..4)
    red_threshold: RED 판정 점수 (config로 조정)
    persist_days: 지속 일수 (config로 조정)
    """
    if not scores:
        return None
    today_max = max(s["score"] for s in scores)
    if today_max >= red_threshold and len(history) >= persist_days and \
            all(h >= red_threshold for h in history[-persist_days:]):
        return "red"
    if today_max >= red_threshold:
        return "yellow"
    return None


# ============================================================
# 4. FACT-C — 대장암 특이 QoL 36문항 (Functional Assessment of Cancer Therapy - Colorectal)
# ============================================================
# 5개 서브스케일: PWB(7) · SWB(7) · EWB(6) · FWB(7) · CCS(9) = 36
# 각 응답 0..4 (전혀 그렇지 않다 ~ 매우 그렇다)
# 일부 항목은 역채점
FACT_C_ITEMS = [
    # (item_code, subscale, question, reverse)
    # PWB - Physical Wellbeing (7) — 모두 reverse
    ("GP1", "PWB", "기력이 없다", True),
    ("GP2", "PWB", "메스꺼움을 느낀다", True),
    ("GP3", "PWB", "신체적인 상태로 가족 도움이 어렵다", True),
    ("GP4", "PWB", "통증이 있다", True),
    ("GP5", "PWB", "치료 부작용으로 힘들다", True),
    ("GP6", "PWB", "병이 든 느낌이 든다", True),
    ("GP7", "PWB", "침대에 누워있어야 한다", True),
    # SWB - Social/Family Wellbeing (7)
    ("GS1", "SWB", "가까운 사람들과 친밀감을 느낀다", False),
    ("GS2", "SWB", "가족으로부터 정서적 지지를 받는다", False),
    ("GS3", "SWB", "친구로부터 지지를 받는다", False),
    ("GS4", "SWB", "가족이 나의 병을 받아들였다", False),
    ("GS5", "SWB", "가족과 병에 관해 의사소통이 가능하다", False),
    ("GS6", "SWB", "배우자/파트너와 친밀하다", False),
    ("GS7", "SWB", "성생활에 만족한다", False),
    # EWB - Emotional Wellbeing (6) — GE2만 정채점
    ("GE1", "EWB", "슬픔을 느낀다", True),
    ("GE2", "EWB", "병에 대해 잘 대처하고 있다", False),
    ("GE3", "EWB", "병으로 인해 희망을 잃을까 두렵다", True),
    ("GE4", "EWB", "초조함을 느낀다", True),
    ("GE5", "EWB", "죽음에 대해 걱정한다", True),
    ("GE6", "EWB", "병이 악화될까 걱정한다", True),
    # FWB - Functional Wellbeing (7)
    ("GF1", "FWB", "일을 할 수 있다", False),
    ("GF2", "FWB", "일이 만족스럽다", False),
    ("GF3", "FWB", "삶을 즐길 수 있다", False),
    ("GF4", "FWB", "병을 받아들였다", False),
    ("GF5", "FWB", "잠을 잘 잔다", False),
    ("GF6", "FWB", "평소 즐기던 활동을 할 수 있다", False),
    ("GF7", "FWB", "현재 삶의 질에 만족한다", False),
    # CCS - Colorectal Cancer Subscale (9)
    ("C1", "CCS", "장 운동 조절이 어렵다", True),
    ("C2", "CCS", "체중이 감소했다", True),
    ("C3", "CCS", "신체 모양이 좋아 보인다", False),
    ("C4", "CCS", "복부의 통증이나 불편감이 있다", True),
    ("C5", "CCS", "스토마(인공장루)로 인해 당황스럽다", True),
    ("C6", "CCS", "소화 문제가 있다", True),
    ("C7", "CCS", "식욕이 좋다", False),
    ("Cx1", "CCS", "복부의 부풀어 오름이 있다", True),
    ("Cx2", "CCS", "스토마 관리에 자신이 있다", False),
]

FACT_C_SCALE_LABELS = ["전혀 그렇지 않다", "조금 그렇다", "어느 정도", "꽤 그렇다", "매우 그렇다"]
FACT_C_REVERSE_MAP = {0: 4, 1: 3, 2: 2, 3: 1, 4: 0}


def score_fact_c(responses: dict[str, int]) -> dict:
    """FACT-C 5개 서브스케일 + TOI(Trial Outcome Index) + Total."""
    by_sub: dict[str, list[float]] = {}
    for code, sub, _, reverse in FACT_C_ITEMS:
        raw = responses.get(code)
        if raw is None:
            continue
        if not (0 <= raw <= 4):
            raise ValueError(f"FACT-C raw 0..4: {code}={raw}")
        adjusted = FACT_C_REVERSE_MAP[raw] if reverse else raw
        by_sub.setdefault(sub, []).append(adjusted)

    def sub_score(sub: str, n_items: int) -> Optional[float]:
        values = by_sub.get(sub, [])
        if len(values) < n_items * 0.5:        # 50% 미만이면 결측
            return None
        # 결측 보정: 평균 × 전체 항목수
        return round(sum(values) * n_items / len(values), 2)

    pwb = sub_score("PWB", 7)
    swb = sub_score("SWB", 7)
    ewb = sub_score("EWB", 6)
    fwb = sub_score("FWB", 7)
    ccs = sub_score("CCS", 9)

    # TOI = PWB + FWB + CCS (외래에서 가장 추적되는 지표)
    toi = sum(s for s in [pwb, fwb, ccs] if s is not None) if all(
        s is not None for s in [pwb, fwb, ccs]) else None
    # FACT-G = PWB + SWB + EWB + FWB
    fact_g = sum(s for s in [pwb, swb, ewb, fwb] if s is not None) if all(
        s is not None for s in [pwb, swb, ewb, fwb]) else None
    # FACT-C = FACT-G + CCS
    fact_c_total = fact_g + ccs if fact_g is not None and ccs is not None else None

    return {
        "PWB": pwb, "SWB": swb, "EWB": ewb, "FWB": fwb, "CCS": ccs,
        "TOI": toi, "FACT-G": fact_g, "FACT-C": fact_c_total,
    }


def evaluate_mcid_fact_c(
    current: float,
    previous: Optional[float],
    subscale: str,
) -> Optional[str]:
    """FACT-C MCID: 서브스케일별 임상적 의미 변화량 (Cella 2002).

    PWB/SWB/EWB/FWB: ≥2점 변화 / TOI: ≥5점 / FACT-C: ≥7점.
    direction='up' (높을수록 양호) — 감소가 악화.
    """
    if current is None or previous is None:
        return None
    delta = previous - current  # 양수면 악화
    mcid = {
        "PWB": 2, "SWB": 2, "EWB": 2, "FWB": 2, "CCS": 3,
        "TOI": 5, "FACT-G": 5, "FACT-C": 7,
    }.get(subscale, 2)
    if delta >= mcid * 1.5:
        return "red"
    if delta >= mcid:
        return "yellow"
    return None


# ============================================================
# 5. FACIT-F — 피로도 13문항 (Functional Assessment of Chronic Illness Therapy - Fatigue)
# ============================================================
# 모든 응답 0..4. 11개 항목 reverse, 2개 항목(HI7, HI12) 정채점.
FACIT_F_ITEMS = [
    ("HI7", "FAT", "기력이 있다", False),                   # 정채점
    ("HI12", "FAT", "활동을 시작할 의욕이 있다", False),     # 정채점
    ("An1", "FAT", "지친다", True),
    ("An2", "FAT", "전반적으로 약한 느낌이 든다", True),
    ("An3", "FAT", "나른하다 (기운이 없다)", True),
    ("An4", "FAT", "피로함을 느낀다", True),
    ("An5", "FAT", "피로해서 일을 시작하기 어렵다", True),
    ("An7", "FAT", "피로해서 일을 끝내기 어렵다", True),
    ("An8", "FAT", "기운이 있다", False),
    ("An12", "FAT", "평소 활동을 할 수 있다", False),
    ("An14", "FAT", "낮 동안 자야 한다", True),
    ("An15", "FAT", "피곤해서 식사하기 어렵다", True),
    ("An16", "FAT", "사람들과 어울리는 데 도움이 필요하다", True),
]


def score_facit_f(responses: dict[str, int]) -> dict:
    """FACIT-F 단일 점수 (0..52). 높을수록 양호."""
    total: list[float] = []
    for code, _, _, reverse in FACIT_F_ITEMS:
        raw = responses.get(code)
        if raw is None:
            continue
        if not (0 <= raw <= 4):
            raise ValueError(f"FACIT-F raw 0..4: {code}={raw}")
        total.append(FACT_C_REVERSE_MAP[raw] if reverse else raw)
    if len(total) < len(FACIT_F_ITEMS) * 0.5:
        return {"FACIT-F": None, "classification": "missing"}
    score = round(sum(total) * len(FACIT_F_ITEMS) / len(total), 2)
    # cutoff: ≤30 = severe / 31~43 = moderate / 44~52 = normal
    classification = (
        "severe" if score <= 30
        else "moderate" if score < 44
        else "normal"
    )
    return {"FACIT-F": score, "classification": classification}


def evaluate_mcid_facit_f(
    current: float,
    previous: Optional[float],
) -> Optional[str]:
    """FACIT-F MCID: 3점 변화. 감소가 악화."""
    if current is None:
        return None
    if current <= 30:
        return "red"
    if current < 44:
        return "yellow"
    if previous is not None and (previous - current) >= 3:
        return "yellow"
    return None


# ============================================================
# 6. PSQI — 수면의 질 19문항 (Pittsburgh Sleep Quality Index)
# ============================================================
# 7개 컴포넌트 점수(0..3). Total 0..21. ≥5 = poor sleep.
# 채점 규칙이 복잡 — 간소화 버전 (POC).
# 응답 형식:
#   - Q1 취침시각 (HH:MM 문자열) - 채점에 미사용 (참고용)
#   - Q2 잠드는데 걸린 시간 (분, 정수)
#   - Q3 기상시각 - 미사용
#   - Q4 실수면시간 (시간, float)
#   - Q5a~Q5j 수면 방해 요인 (각 0..3)
#   - Q6 전반적 수면의 질 (0..3, 0=매우 좋음 ~ 3=매우 나쁨)
#   - Q7 수면제 사용 (0..3)
#   - Q8 일상 졸림 (0..3)
#   - Q9 일상 의욕 (0..3)
PSQI_ITEMS = [
    {"code": "Q2", "type": "minutes", "question": "잠드는 데 보통 몇 분 걸리시나요?"},
    {"code": "Q4", "type": "hours", "question": "실제로 주무시는 시간은 몇 시간인가요?"},
    {"code": "Q5a", "type": "scale", "question": "30분 안에 잠들지 못해서 잠을 설친 빈도",
     "scale": ["없음", "주 1회 미만", "주 1-2회", "주 3회 이상"]},
    {"code": "Q5b", "type": "scale", "question": "한밤중·새벽에 깨서 잠을 설친 빈도",
     "scale": ["없음", "주 1회 미만", "주 1-2회", "주 3회 이상"]},
    {"code": "Q5c", "type": "scale", "question": "화장실 가기 위해 깨야 했던 빈도",
     "scale": ["없음", "주 1회 미만", "주 1-2회", "주 3회 이상"]},
    {"code": "Q5d", "type": "scale", "question": "숨 쉬기가 편치 않아 잠을 설친 빈도",
     "scale": ["없음", "주 1회 미만", "주 1-2회", "주 3회 이상"]},
    {"code": "Q5e", "type": "scale", "question": "기침·코골이로 잠을 설친 빈도",
     "scale": ["없음", "주 1회 미만", "주 1-2회", "주 3회 이상"]},
    {"code": "Q5f", "type": "scale", "question": "춥다고 느껴서 잠을 설친 빈도",
     "scale": ["없음", "주 1회 미만", "주 1-2회", "주 3회 이상"]},
    {"code": "Q5g", "type": "scale", "question": "덥다고 느껴서 잠을 설친 빈도",
     "scale": ["없음", "주 1회 미만", "주 1-2회", "주 3회 이상"]},
    {"code": "Q5h", "type": "scale", "question": "악몽 때문에 잠을 설친 빈도",
     "scale": ["없음", "주 1회 미만", "주 1-2회", "주 3회 이상"]},
    {"code": "Q5i", "type": "scale", "question": "통증으로 잠을 설친 빈도",
     "scale": ["없음", "주 1회 미만", "주 1-2회", "주 3회 이상"]},
    {"code": "Q5j", "type": "scale", "question": "기타 이유로 잠을 설친 빈도",
     "scale": ["없음", "주 1회 미만", "주 1-2회", "주 3회 이상"]},
    {"code": "Q6", "type": "scale", "question": "지난 한 달 전반적인 수면의 질은?",
     "scale": ["매우 좋음", "좋음", "나쁨", "매우 나쁨"]},
    {"code": "Q7", "type": "scale", "question": "수면제(처방·일반) 복용 빈도",
     "scale": ["없음", "주 1회 미만", "주 1-2회", "주 3회 이상"]},
    {"code": "Q8", "type": "scale", "question": "낮에 활동 중 졸음 때문에 어려움 빈도",
     "scale": ["없음", "주 1회 미만", "주 1-2회", "주 3회 이상"]},
    {"code": "Q9", "type": "scale", "question": "활동에 의욕을 유지하기가 어떠셨나요?",
     "scale": ["전혀 어렵지 않음", "약간 어려움", "꽤 어려움", "매우 어려움"]},
]


def score_psqi(responses: dict) -> dict:
    """PSQI 7 컴포넌트 + Total Score (0..21)."""
    # C1 — Subjective sleep quality
    c1 = responses.get("Q6")

    # C2 — Sleep latency
    q2 = responses.get("Q2")
    q5a = responses.get("Q5a")
    if q2 is None or q5a is None:
        c2 = None
    else:
        latency_score = 0 if q2 <= 15 else 1 if q2 <= 30 else 2 if q2 <= 60 else 3
        c2_sum = latency_score + q5a
        c2 = 0 if c2_sum == 0 else 1 if c2_sum <= 2 else 2 if c2_sum <= 4 else 3

    # C3 — Sleep duration
    q4 = responses.get("Q4")
    if q4 is None:
        c3 = None
    else:
        c3 = 0 if q4 > 7 else 1 if q4 >= 6 else 2 if q4 >= 5 else 3

    # C4 — Habitual sleep efficiency (간소화: Q4 vs Q1/Q3 시간차 → 생략, q4 단독)
    # POC에서는 c4 = 단순히 c3과 동일한 logic 사용 (시간 비율 계산 생략)
    c4 = c3

    # C5 — Sleep disturbance (Q5b ~ Q5j 평균)
    disturbance = [responses.get(f"Q5{x}") for x in "bcdefghij"]
    if all(d is None for d in disturbance):
        c5 = None
    else:
        valid = [d for d in disturbance if d is not None]
        # PSQI 원 알고리즘: 합산값 0=0, 1-9=1, 10-18=2, 19-27=3
        total_d = sum(valid)
        c5 = 0 if total_d == 0 else 1 if total_d <= 9 else 2 if total_d <= 18 else 3

    # C6 — Use of sleep medication
    c6 = responses.get("Q7")

    # C7 — Daytime dysfunction (Q8 + Q9)
    q8 = responses.get("Q8")
    q9 = responses.get("Q9")
    if q8 is None or q9 is None:
        c7 = None
    else:
        s = q8 + q9
        c7 = 0 if s == 0 else 1 if s <= 2 else 2 if s <= 4 else 3

    components = {"C1": c1, "C2": c2, "C3": c3, "C4": c4, "C5": c5, "C6": c6, "C7": c7}
    if any(v is None for v in components.values()):
        return {"PSQI": None, "components": components, "classification": "missing"}

    total = sum(components.values())
    return {
        "PSQI": total,
        "components": components,
        "classification": "poor" if total >= 5 else "good",
    }


def evaluate_mcid_psqi(value: Optional[int]) -> Optional[str]:
    """PSQI: ≥5 = 수면 장애 (poor sleep). ≥10 = severe."""
    if value is None:
        return None
    if value >= 10:
        return "red"
    if value >= 5:
        return "yellow"
    return None
