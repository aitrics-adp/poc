"""POC 데이터 모델 — SQLModel 기반 11개 테이블 정의.

테이블 구성:
  1. Patient                  — 환자 마스터 (5명 합성 데이터)
  2. ProSession               — PRO 응답 세션 (full/quick/no_change 모드)
  3. ProResponse              — 문항별 raw 응답 (append-only)
  4. ProScore                 — 채점 결과 (append-only, MCID flag 포함)
  5. LlmAudit                 — LLM 발화·응답·가드레일 트리거 로그
  6. PushSubscription         — 환자별 Web Push endpoint·키
  7. PatientProConfig         — 환자별 PRO 도구·임계값·빈도 (FN-CUST-001~005)
  8. ProSetAuditLog           — PRO 세트 변경 이력 (FN-CUST-008, FN-AUDIT-001)
  9. EducationCard            — 정적 교육 카드 (FN-LLM-006, 현재 미사용)
 10. CustomProSet             — 의사가 만든 재사용 PRO 템플릿
 11. CustomQuestionResponse   — 커스텀 문항 응답 (Phase 2용 스키마)

원칙:
  - ProResponse·ProScore는 append-only — 절대 수정·삭제하지 않음
  - 다중 PRO 도구가 들어가는 자리는 JSON Text 컬럼으로 보관 (helper 메서드 제공)
  - 모든 datetime은 UTC
"""
import json
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, create_engine, Session
from sqlalchemy import Column, Text
from config import settings


# ---------- 1. Patient ----------
class Patient(SQLModel, table=True):
    id: str = Field(primary_key=True)              # "C-1042"
    name: str                                       # "이○○"
    birth_year: int                                 # 1953
    icd10: str = "C18.9"                            # 대장암
    cycle_day: int = 0                              # 항암 사이클 진행일
    caregiver_phone: str = "010-0000-0000"
    enrolled_at: datetime = Field(default_factory=datetime.utcnow)


# ---------- 2. ProSession ----------
class ProSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: str = Field(foreign_key="patient.id")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    ui_mode: str = "general"                        # general | elder
    flex_mode: str = "full"                         # full | quick | no_change (FN-FLEX-001~004)
    carry_over_from_session_id: Optional[int] = None  # FN-FLEX-005


# ---------- 3. ProResponse ----------
class ProResponse(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="prosession.id")
    tool_code: str                                  # "PRO-CTCAE" | "HADS"
    item_code: str                                  # "fatigue_freq", "A1", ...
    attribute: Optional[str] = None                 # 빈도/강도/일상 (PRO-CTCAE만)
    raw_value: int                                  # 0..4 or 0..3
    source: str = "user"                            # user | mock | carry_over


# ---------- 4. ProScore (append-only) ----------
class ProScore(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="prosession.id")
    patient_id: str = Field(foreign_key="patient.id")
    tool_code: str
    subscale: Optional[str] = None                  # "HADS-A", "HADS-D", item_code
    value: float
    classification: Optional[str] = None            # "normal" | "borderline" | "case"
    mcid_flag: Optional[str] = None                 # "red" | "yellow" | None
    computed_at: datetime = Field(default_factory=datetime.utcnow)


# ---------- 5. LlmAudit ----------
class LlmAudit(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: Optional[str] = Field(default=None, foreign_key="patient.id")
    prompt: str
    response: str
    guardrail_triggered: Optional[str] = None       # "emergency" | "out_of_scope" | None
    llm_mode: str = "mock"
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------- 6. PushSubscription (Web Push) ----------
class PushSubscription(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: str = Field(foreign_key="patient.id")
    endpoint: str = Field(unique=True)
    p256dh: str
    auth: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------- 7. PatientProConfig (FN-CONFIG-001~005, FN-CUST-001~005) ----------
class PatientProConfig(SQLModel, table=True):
    patient_id: str = Field(primary_key=True, foreign_key="patient.id")
    pro_ctcae_config: str = Field(default="{}", sa_column=Column(Text))
    hads_enabled: bool = True
    hads_subscales: str = Field(default="A,D")
    frequency: str = "daily"                          # 전체 PRO-CTCAE 빈도 (legacy)
    cycle_trigger_days: str = Field(default="", sa_column=Column(Text))
    threshold_pro_ctcae_red: int = 2
    threshold_pro_ctcae_persist_days: int = 2
    threshold_hads_yellow: int = 8
    threshold_hads_red: int = 11
    # ---- 신규 (FN-CUST-003/005/006) ----
    # JSON: {"FACT-C":{"enabled":true,"frequency":"monthly","start_at":"2026-04-01","end_at":null}, ...}
    tools_config: str = Field(default="{}", sa_column=Column(Text))
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: str = "system"

    # ---- helpers ----
    def get_pro_ctcae(self) -> dict[str, list[str]]:
        try:
            return json.loads(self.pro_ctcae_config or "{}")
        except Exception:
            return {}

    def set_pro_ctcae(self, mapping: dict[str, list[str]]):
        self.pro_ctcae_config = json.dumps(mapping, ensure_ascii=False)

    def get_hads_subscales(self) -> list[str]:
        return [s.strip() for s in self.hads_subscales.split(",") if s.strip()]

    def get_cycle_trigger_days(self) -> list[int]:
        if not self.cycle_trigger_days:
            return []
        return [int(x) for x in self.cycle_trigger_days.split(",") if x.strip()]

    def get_tools(self) -> dict:
        try:
            return json.loads(self.tools_config or "{}")
        except Exception:
            return {}

    def set_tools(self, mapping: dict):
        self.tools_config = json.dumps(mapping, ensure_ascii=False)


# ---------- 8. ProSetAuditLog (FN-CUST-008, FN-AUDIT-001) ----------
class ProSetAuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: str = Field(foreign_key="patient.id")
    changed_at: datetime = Field(default_factory=datetime.utcnow)
    changed_by: str                                # "doctor" | "system" | "seed"
    action: str                                    # "created" | "updated" | "tool_added" | "tool_removed"
    diff: str = Field(default="{}", sa_column=Column(Text))   # JSON diff (before / after)


# ---------- 9. PROEducationCard (FN-LLM-006) ----------
class EducationCard(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    trigger_tool: str
    trigger_subscale: str
    threshold: int = 2
    title: str
    body: str = Field(sa_column=Column(Text))
    source_label: str = "ASCO 2024 Practice Guideline"
    source_url: str = "https://www.asco.org/practice-patients/guidelines"


# ---------- 10. CustomProSet — 의사가 만든 PRO 템플릿 ----------
class CustomProSet(SQLModel, table=True):
    """의사가 라이브러리에서 만든 재사용 가능한 PRO 세트.

    config JSON 구조:
    {
        "tools": {
            "PRO-CTCAE": {"enabled": true,
                         "pro_ctcae": {"fatigue":["freq","severity"], ...},
                         "frequency": "daily"},
            "HADS":      {"enabled": true, "subscales":["A","D"], "frequency":"monthly"},
            "FACT-C":    {"enabled": false},
            "FACIT-F":   {"enabled": true, "frequency": "weekly"},
            "PSQI":      {"enabled": false}
        },
        "custom_questions": [
            {"code":"CUST-1", "question":"...", "response_type":"likert_5",
             "scale_labels":["없음","약함","보통","심함","매우 심함"]}
        ]
    }
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: str = Field(default="", sa_column=Column(Text))
    target_icd10: str = ""                          # "C18" 같은 prefix (선택)
    config: str = Field(default="{}", sa_column=Column(Text))
    created_by: str = "doctor"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def get_config(self) -> dict:
        try:
            return json.loads(self.config or "{}")
        except Exception:
            return {}

    def set_config(self, cfg: dict):
        self.config = json.dumps(cfg, ensure_ascii=False)


# ---------- 11. CustomQuestionResponse — 환자가 커스텀 문항에 답한 응답 ----------
class CustomQuestionResponse(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="prosession.id")
    custom_set_id: Optional[int] = Field(default=None, foreign_key="customproset.id")
    question_code: str                              # "CUST-1" 등
    raw_value: int                                  # 0..N (response_type별)
    text_value: str = ""                            # text 응답 시
    created_at: datetime = Field(default_factory=datetime.utcnow)


# 기본값 헬퍼 — POC 표준 (PRO-CTCAE 5증상 + HADS-A,D, 매일)
def default_pro_config(patient_id: str) -> PatientProConfig:
    cfg = PatientProConfig(patient_id=patient_id)
    cfg.set_pro_ctcae({
        "fatigue": ["freq", "severity"],
        "appetite": ["freq"],
        "nausea": ["severity"],
        "neuropathy": ["severity"],
        # diarrhea는 기본 OFF (필요 시 의사가 ON)
    })
    cfg.hads_enabled = True
    cfg.hads_subscales = "A,D"
    cfg.frequency = "daily"
    return cfg


# ICD-10 + 나이 → 기본 PRO 세트 매핑 (FN-CUST-002)
# required: 필수 도구 (UI에서 제거 불가) / optional: 선택 도구 (의사 ON/OFF)
def recommend_default_pro_set(icd10: str, age: Optional[int] = None) -> dict:
    """질환 코드 + 나이 기반 PRO 세트 자동 추천.

    Returns:
        {
            "required": [...],     # 필수 도구 코드 (제거 X)
            "optional": [...],     # 선택 도구 (의사가 ON/OFF)
            "pro_ctcae": {...},    # 증상×속성
            "tools": {tool: {enabled, frequency, ...}},
            "rationale": "임상 근거"
        }
    """
    code = (icd10 or "").upper()

    # ── 대장/직장암 (C18~C21) ───────────────────────────────
    if code.startswith("C18") or code.startswith("C19") or \
       code.startswith("C20") or code.startswith("C21"):
        elder = age is not None and age >= 75
        required = ["PRO-CTCAE", "HADS"] if elder else ["PRO-CTCAE", "HADS", "FACT-C"]
        optional = ["FACT-C", "FACIT-F", "PSQI"] if elder else ["FACIT-F", "PSQI"]
        return {
            "required": required,
            "optional": optional,
            "pro_ctcae": {
                "fatigue": ["freq", "severity"],
                "appetite": ["freq"],
                "nausea": ["severity"],
                "neuropathy": ["severity"],
                "diarrhea": ["freq"],
            },
            "tools": {
                "PRO-CTCAE": {"enabled": True, "frequency": "daily"},
                "HADS": {"enabled": True, "frequency": "monthly",
                         "subscales": ["A", "D"]},
                "FACT-C": {"enabled": not elder, "frequency": "monthly"},
                "FACIT-F": {"enabled": False, "frequency": "weekly"},
                "PSQI": {"enabled": False, "frequency": "monthly"},
            },
            "rationale": (
                "대장암 표준: PRO-CTCAE·HADS·FACT-C 필수. "
                "어르신(≥75세)은 FACT-C를 선택으로 두어 응답 부담 감소."
            ),
        }

    # ── 폐암 (C34) ──────────────────────────────────────────
    if code.startswith("C34"):
        return {
            "required": ["PRO-CTCAE", "HADS"],
            "optional": ["FACIT-F", "PSQI"],
            "pro_ctcae": {
                "fatigue": ["freq", "severity"],
                "appetite": ["freq"],
                "nausea": ["severity"],
            },
            "tools": {
                "PRO-CTCAE": {"enabled": True, "frequency": "daily"},
                "HADS": {"enabled": True, "frequency": "monthly",
                         "subscales": ["A", "D"]},
                "FACIT-F": {"enabled": True, "frequency": "weekly"},
                "PSQI": {"enabled": False, "frequency": "monthly"},
            },
            "rationale": "폐암: PRO-CTCAE·HADS 필수. 면역항암제 피로 추적용 FACIT-F 권장.",
        }

    # ── 위암 (C16) ──────────────────────────────────────────
    if code.startswith("C16"):
        young = age is not None and age <= 50
        return {
            "required": ["PRO-CTCAE", "HADS"],
            "optional": ["FACT-C", "FACIT-F", "PSQI"],
            "pro_ctcae": {
                "fatigue": ["freq", "severity"],
                "appetite": ["freq"],
                "nausea": ["severity"],
                "neuropathy": ["severity"],
            },
            "tools": {
                "PRO-CTCAE": {"enabled": True, "frequency": "daily"},
                "HADS": {"enabled": True,
                         "frequency": "weekly" if young else "monthly",
                         "subscales": ["A", "D"]},
                "FACT-C": {"enabled": False, "frequency": "monthly"},
                "FACIT-F": {"enabled": False, "frequency": "weekly"},
                "PSQI": {"enabled": False, "frequency": "monthly"},
            },
            "rationale": (
                "위암 표준 세트. 젊은 환자(≤50세)는 HADS 주 1회로 정서 모니터 강화."
                if young else
                "위암: PRO-CTCAE·HADS 필수."
            ),
        }

    # ── 유방암 (C50) ────────────────────────────────────────
    if code.startswith("C50"):
        return {
            "required": ["PRO-CTCAE", "HADS"],
            "optional": ["FACIT-F", "PSQI"],
            "pro_ctcae": {
                "fatigue": ["freq", "severity"],
                "nausea": ["severity"],
                "neuropathy": ["severity"],
            },
            "tools": {
                "PRO-CTCAE": {"enabled": True, "frequency": "daily"},
                "HADS": {"enabled": True, "frequency": "monthly",
                         "subscales": ["A", "D"]},
                "FACIT-F": {"enabled": True, "frequency": "weekly"},
                "PSQI": {"enabled": False, "frequency": "monthly"},
            },
            "rationale": "유방암: 호르몬·항암 부작용 추적용 PRO-CTCAE·FACIT-F.",
        }

    # ── 기본값 ──────────────────────────────────────────────
    return {
        "required": ["PRO-CTCAE", "HADS"],
        "optional": ["FACIT-F", "PSQI", "FACT-C"],
        "pro_ctcae": {
            "fatigue": ["freq", "severity"],
            "nausea": ["severity"],
        },
        "tools": {
            "PRO-CTCAE": {"enabled": True, "frequency": "daily"},
            "HADS": {"enabled": True, "frequency": "monthly",
                     "subscales": ["A", "D"]},
            "FACIT-F": {"enabled": False, "frequency": "weekly"},
            "PSQI": {"enabled": False, "frequency": "monthly"},
            "FACT-C": {"enabled": False, "frequency": "monthly"},
        },
        "rationale": "기본 세트: PRO-CTCAE·HADS.",
    }


# ---------- DB Engine ----------
engine = create_engine(settings.DATABASE_URL, echo=False)


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
