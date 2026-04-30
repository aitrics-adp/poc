"""TRI-PRO POC Backend — FastAPI 단일 모듈.

주요 책임:
  - PRO 도구 카탈로그·라이브러리·환자별 config (FN-CUST)
  - PRO 세션·응답 수집·결정론 채점 (FN-PRO, FN-FLEX)
  - Pre-Visit Report One-Line Summary (FN-RPT)
  - LLM Free Talk + 4종 가드레일 (FN-LLM)
  - Web Push 구독·발송 (FN-EVENT)
  - 변경 이력 audit (FN-CUST-008, FN-AUDIT)
  - Cron-style jobs (사전계산·자동 푸시·미응답 감지)

채점·LLM은 별도 모듈(scoring·llm_mock·report)에 위임.
"""
from datetime import datetime, timedelta
from typing import Optional
import json as _json

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session, select

from config import settings
from models import (
    # 도메인 엔티티
    Patient, ProSession, ProResponse, ProScore, LlmAudit, PushSubscription,
    PatientProConfig, ProSetAuditLog, CustomProSet,
    # 도구 함수
    default_pro_config, recommend_default_pro_set,
    # DB 라이프사이클
    init_db, get_session, engine,
)
from scoring import (
    # PRO-CTCAE
    score_pro_ctcae_item, score_pro_ctcae_composite, evaluate_mcid_pro_ctcae,
    PRO_CTCAE_ITEMS, PRO_CTCAE_SCALE_LABELS,
    # HADS
    score_hads, evaluate_mcid_hads, HADS_ITEMS,
    # 추가 PRO 도구 메타 (도구 라이브러리 detail에서 사용)
    FACT_C_ITEMS, FACT_C_SCALE_LABELS, FACIT_F_ITEMS, PSQI_ITEMS,
)
from llm_mock import classify_and_respond
from push import send_push
from report import generate_one_line_summary


app = FastAPI(title="TRI-PRO POC", version="0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    # 배포 환경에서 첫 부팅 시 자동 시드 (환자 0명일 때만)
    try:
        with Session(engine) as s:
            has_patient = s.exec(select(Patient).limit(1)).first()
            if not has_patient:
                print("🌱 첫 부팅 — 합성 환자 5명 자동 시드")
                from seed import seed
                seed()
    except Exception as e:
        print(f"⚠ auto-seed 건너뜀: {e}")


# =====================================================================
# Patients
# =====================================================================
@app.get("/api/patients")
def list_patients(session: Session = Depends(get_session)):
    return session.exec(select(Patient)).all()


@app.get("/api/patients/{patient_id}")
def get_patient(patient_id: str, session: Session = Depends(get_session)):
    p = session.get(Patient, patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    return p


# =====================================================================
# PRO Tools (도구 메타) — 환자앱이 폼 렌더링용으로 받음
# =====================================================================
@app.get("/api/pro-tools")
def get_tool_definitions():
    return {
        "PRO-CTCAE": {
            "items": PRO_CTCAE_ITEMS,
            "scale_labels": PRO_CTCAE_SCALE_LABELS,
        },
        "HADS": {
            "items": [
                {"code": code, "subscale": sub, "question": q, "reverse": r}
                for code, sub, q, r in HADS_ITEMS
            ],
            "scale_labels": ["전혀 없었다 (0)", "때때로 (1)", "자주 (2)", "대부분 (3)"],
        },
    }


@app.get("/api/pro-tools/catalog")
def get_pro_tools_catalog():
    """어드민 PRO 커스터마이징 화면용 — 선택 가능한 모든 도구·증상·속성 카탈로그."""
    return {
        "pro_ctcae": [
            {
                "symptom": symptom,
                "label": symptom,
                "attributes": list(attrs.keys()),
                "questions": attrs,
            }
            for symptom, attrs in PRO_CTCAE_ITEMS.items()
        ],
        "hads": {
            "subscales": [
                {"code": "A", "label": "불안 (HADS-A)", "items": 7},
                {"code": "D", "label": "우울 (HADS-D)", "items": 7},
            ],
        },
        "frequencies": [
            {"code": "daily", "label": "매일"},
            {"code": "every_3_days", "label": "3일마다"},
            {"code": "weekly", "label": "주 1회"},
            {"code": "monthly", "label": "월 1회"},
            {"code": "cycle", "label": "사이클 기반 (D1·D7·D14)"},
        ],
    }


@app.get("/api/pro-tools/library")
def get_pro_tools_library(q: Optional[str] = None):
    """FN-CUST-003 도구 라이브러리 검색 — 키워드 기반."""
    library = [
        {
            "tool_code": "PRO-CTCAE",
            "name": "PRO-CTCAE",
            "domain": "항암 부작용 (빈도/강도/일상)",
            "items": "가변 (핵심 7~)",
            "duration_min": 4,
            "license": "NCI 공개 / 무료",
            "evidence_grade": "A",
            "default_frequency": "daily",
        },
        {
            "tool_code": "HADS",
            "name": "HADS",
            "domain": "불안·우울 (Hospital Anxiety & Depression Scale)",
            "items": 14,
            "duration_min": 3,
            "license": "공개 (학술용 무료)",
            "evidence_grade": "A",
            "default_frequency": "monthly",
        },
        {
            "tool_code": "FACT-C",
            "name": "FACT-C",
            "domain": "대장암 특이 QoL (PWB·SWB·EWB·FWB·CCS)",
            "items": 36,
            "duration_min": 7,
            "license": "FACIT.org / 무료 학술 사용",
            "evidence_grade": "A",
            "default_frequency": "monthly",
        },
        {
            "tool_code": "FACIT-F",
            "name": "FACIT-F",
            "domain": "암성 피로 (Fatigue Subscale)",
            "items": 13,
            "duration_min": 3,
            "license": "FACIT.org / 무료 학술 사용",
            "evidence_grade": "A",
            "default_frequency": "weekly",
        },
        {
            "tool_code": "PSQI",
            "name": "PSQI",
            "domain": "수면의 질 (Pittsburgh Sleep Quality Index)",
            "items": 19,
            "duration_min": 5,
            "license": "공개",
            "evidence_grade": "A",
            "default_frequency": "monthly",
        },
    ]
    if q:
        ql = q.lower()
        library = [t for t in library if ql in t["name"].lower()
                   or ql in t["domain"].lower()]
    return library


@app.get("/api/pro-tools/recommend")
def recommend_pro_set(icd10: str, age: Optional[int] = None):
    """FN-CUST-002 ICD-10 + 나이 기반 기본 세트 추천."""
    return recommend_default_pro_set(icd10, age)


# ============================================================
# 도구 상세 — 실제 질문/응답 보기 (FN-CUST-003)
# ============================================================
@app.get("/api/pro-tools/library/{tool_code}")
def get_tool_detail(tool_code: str):
    """단일 도구의 실제 질문 + 응답 옵션."""
    code = tool_code.upper()
    if code == "PRO-CTCAE":
        items = []
        for symptom, attrs in PRO_CTCAE_ITEMS.items():
            for attr, question in attrs.items():
                items.append({
                    "code": f"{symptom}_{attr}",
                    "symptom": symptom,
                    "attribute": attr,
                    "question": question,
                    "scale_labels": PRO_CTCAE_SCALE_LABELS[attr],
                    "scale_max": 4,
                })
        return {
            "tool_code": "PRO-CTCAE",
            "name": "PRO-CTCAE",
            "domain": "항암 부작용 (빈도/강도/일상)",
            "license": "NCI 공개 / 무료",
            "evidence_grade": "A",
            "items": items,
            "scoring_note": "각 증상별로 빈도/강도/일상 방해를 0~4로 응답. 합산하지 않고 분포 보존.",
        }
    if code == "HADS":
        return {
            "tool_code": "HADS",
            "name": "HADS",
            "domain": "불안·우울 (Hospital Anxiety & Depression Scale)",
            "license": "공개",
            "evidence_grade": "A",
            "items": [
                {"code": c, "subscale": s, "question": q, "reverse": r,
                 "scale_labels": ["전혀 없었다", "때때로", "자주", "대부분"],
                 "scale_max": 3}
                for c, s, q, r in HADS_ITEMS
            ],
            "scoring_note": (
                "A·D 각 7문항 합산 (0..21). ≤7 정상 / 8~10 경계 / ≥11 임상적 이상."
            ),
        }
    if code == "FACT-C":
        return {
            "tool_code": "FACT-C",
            "name": "FACT-C",
            "domain": "대장암 특이 QoL (PWB·SWB·EWB·FWB·CCS)",
            "license": "FACIT.org / 무료 학술",
            "evidence_grade": "A",
            "items": [
                {"code": c, "subscale": s, "question": q, "reverse": r,
                 "scale_labels": FACT_C_SCALE_LABELS, "scale_max": 4}
                for c, s, q, r in FACT_C_ITEMS
            ],
            "scoring_note": (
                "5개 서브스케일(PWB·SWB·EWB·FWB·CCS) 합산. "
                "TOI = PWB+FWB+CCS, FACT-C = FACT-G + CCS. 높을수록 양호."
            ),
        }
    if code == "FACIT-F":
        return {
            "tool_code": "FACIT-F",
            "name": "FACIT-F",
            "domain": "암성 피로 (Fatigue Subscale)",
            "license": "FACIT.org / 무료 학술",
            "evidence_grade": "A",
            "items": [
                {"code": c, "subscale": s, "question": q, "reverse": r,
                 "scale_labels": FACT_C_SCALE_LABELS, "scale_max": 4}
                for c, s, q, r in FACIT_F_ITEMS
            ],
            "scoring_note": (
                "13문항 합산 (0..52). ≤30 severe / 31~43 moderate / ≥44 normal. "
                "MCID 3점."
            ),
        }
    if code == "PSQI":
        return {
            "tool_code": "PSQI",
            "name": "PSQI",
            "domain": "수면의 질 (Pittsburgh Sleep Quality Index)",
            "license": "공개",
            "evidence_grade": "A",
            "items": PSQI_ITEMS,
            "scoring_note": (
                "7개 컴포넌트 합산 (0..21). ≥5 = poor sleep / ≥10 = severe."
            ),
        }
    raise HTTPException(404, f"unknown tool_code: {tool_code}")


# ============================================================
# Custom PRO Set CRUD (커스텀 세트)
# ============================================================
class CustomToolBlock(BaseModel):
    enabled: bool = True
    pro_ctcae: Optional[dict[str, list[str]]] = None    # PRO-CTCAE 전용
    subscales: Optional[list[str]] = None                # HADS 전용
    frequency: str = "daily"


class CustomQuestion(BaseModel):
    code: str                                           # "CUST-1"
    question: str
    response_type: str = "likert_5"                     # likert_5|likert_4|nrs_10|yes_no|text
    scale_labels: list[str] = []


class CustomProSetReq(BaseModel):
    name: str
    description: str = ""
    target_icd10: str = ""
    tools: dict[str, CustomToolBlock] = {}
    custom_questions: list[CustomQuestion] = []
    created_by: str = "doctor"


def _serialize_custom_set(s: CustomProSet) -> dict:
    cfg = s.get_config()
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "target_icd10": s.target_icd10,
        "tools": cfg.get("tools", {}),
        "custom_questions": cfg.get("custom_questions", []),
        "created_by": s.created_by,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
    }


@app.get("/api/pro-sets")
def list_custom_sets(session: Session = Depends(get_session)):
    rows = session.exec(
        select(CustomProSet).order_by(CustomProSet.updated_at.desc())
    ).all()
    return [_serialize_custom_set(s) for s in rows]


@app.post("/api/pro-sets")
def create_custom_set(
    req: CustomProSetReq,
    session: Session = Depends(get_session),
):
    s = CustomProSet(
        name=req.name,
        description=req.description,
        target_icd10=req.target_icd10,
        created_by=req.created_by,
    )
    s.set_config({
        "tools": {k: v.model_dump() for k, v in req.tools.items()},
        "custom_questions": [q.model_dump() for q in req.custom_questions],
    })
    session.add(s)
    session.commit()
    session.refresh(s)
    return _serialize_custom_set(s)


@app.get("/api/pro-sets/{set_id}")
def get_custom_set(set_id: int, session: Session = Depends(get_session)):
    s = session.get(CustomProSet, set_id)
    if not s:
        raise HTTPException(404, "Custom set not found")
    return _serialize_custom_set(s)


@app.put("/api/pro-sets/{set_id}")
def update_custom_set(
    set_id: int,
    req: CustomProSetReq,
    session: Session = Depends(get_session),
):
    s = session.get(CustomProSet, set_id)
    if not s:
        raise HTTPException(404, "Custom set not found")
    s.name = req.name
    s.description = req.description
    s.target_icd10 = req.target_icd10
    s.set_config({
        "tools": {k: v.model_dump() for k, v in req.tools.items()},
        "custom_questions": [q.model_dump() for q in req.custom_questions],
    })
    s.updated_at = datetime.utcnow()
    session.add(s)
    session.commit()
    session.refresh(s)
    return _serialize_custom_set(s)


@app.delete("/api/pro-sets/{set_id}")
def delete_custom_set(set_id: int, session: Session = Depends(get_session)):
    s = session.get(CustomProSet, set_id)
    if not s:
        raise HTTPException(404, "Custom set not found")
    session.delete(s)
    session.commit()
    return {"deleted": True}


@app.post("/api/patients/{patient_id}/load-defaults")
def load_default_pro_set(
    patient_id: str,
    session: Session = Depends(get_session),
):
    """환자 ICD-10·나이 기반 기본 PRO 세트로 config 초기화."""
    p = session.get(Patient, patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    age = 2026 - p.birth_year
    rec = recommend_default_pro_set(p.icd10, age)
    cfg = _ensure_config(patient_id, session)

    before = {"pro_ctcae": cfg.get_pro_ctcae(), "tools": cfg.get_tools()}

    cfg.set_pro_ctcae(rec.get("pro_ctcae", {}))
    # HADS — recommend의 tools.HADS 기준
    hads = rec["tools"].get("HADS", {})
    cfg.hads_enabled = bool(hads.get("enabled", True))
    cfg.hads_subscales = ",".join(hads.get("subscales") or ["A", "D"])
    # 다른 도구
    other = {}
    for tcode, tprops in rec["tools"].items():
        other[tcode] = {
            **tprops,
            "required": tcode in rec["required"],
        }
    cfg.set_tools(other)
    # PRO-CTCAE 빈도
    pc = rec["tools"].get("PRO-CTCAE", {})
    if pc.get("frequency"):
        cfg.frequency = pc["frequency"]
    cfg.updated_at = datetime.utcnow()
    cfg.updated_by = f"load_defaults:{p.icd10}"
    session.add(cfg)

    after = {"pro_ctcae": cfg.get_pro_ctcae(), "tools": cfg.get_tools()}
    session.add(ProSetAuditLog(
        patient_id=patient_id,
        changed_by=cfg.updated_by,
        action="load_defaults",
        diff=_json.dumps({
            "before": before, "after": after,
            "rationale": rec.get("rationale", ""),
            "icd10": p.icd10, "age": age,
        }, ensure_ascii=False),
    ))
    session.commit()
    return {
        "loaded": True,
        "icd10": p.icd10,
        "age": age,
        "required": rec["required"],
        "optional": rec["optional"],
        "rationale": rec["rationale"],
    }


@app.post("/api/patients/{patient_id}/apply-pro-set/{set_id}")
def apply_custom_set_to_patient(
    patient_id: str,
    set_id: int,
    session: Session = Depends(get_session),
):
    """커스텀 세트를 환자 PRO Config에 적용."""
    p = session.get(Patient, patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    custom = session.get(CustomProSet, set_id)
    if not custom:
        raise HTTPException(404, "Custom set not found")

    cfg = _ensure_config(patient_id, session)
    custom_cfg = custom.get_config()
    custom_tools = custom_cfg.get("tools", {})

    # Before snapshot
    before = {
        "pro_ctcae": cfg.get_pro_ctcae(),
        "tools": cfg.get_tools(),
    }

    # PRO-CTCAE 매핑 적용
    pc = custom_tools.get("PRO-CTCAE", {})
    if pc.get("enabled"):
        cfg.set_pro_ctcae(pc.get("pro_ctcae") or {})
        cfg.frequency = pc.get("frequency", "daily")
    # HADS
    hd = custom_tools.get("HADS", {})
    cfg.hads_enabled = bool(hd.get("enabled"))
    cfg.hads_subscales = ",".join(hd.get("subscales") or ["A", "D"])
    # 다른 도구
    cfg.set_tools({
        k: {
            "enabled": v.get("enabled", False),
            "frequency": v.get("frequency", "monthly"),
            **({k2: v2 for k2, v2 in v.items() if k2 not in ("enabled","frequency")}),
        }
        for k, v in custom_tools.items()
        if k not in ("PRO-CTCAE", "HADS")
    })
    # 커스텀 문항도 tools_config에 보관
    if custom_cfg.get("custom_questions"):
        cur = cfg.get_tools()
        cur["__custom_questions__"] = {
            "set_id": set_id,
            "set_name": custom.name,
            "questions": custom_cfg["custom_questions"],
        }
        cfg.set_tools(cur)
    cfg.updated_at = datetime.utcnow()
    cfg.updated_by = f"applied_set:{custom.name}"
    session.add(cfg)

    # Audit
    after = {"pro_ctcae": cfg.get_pro_ctcae(), "tools": cfg.get_tools()}
    session.add(ProSetAuditLog(
        patient_id=patient_id,
        changed_by=cfg.updated_by,
        action="apply_custom_set",
        diff=_json.dumps({"before": before, "after": after,
                          "set_id": set_id, "set_name": custom.name},
                         ensure_ascii=False),
    ))
    session.commit()
    return {"applied": True, "set_name": custom.name, "patient_id": patient_id}


# =====================================================================
# PRO Config (FN-CONFIG-001~005) — 환자별 도구 선택/주기/임계값
# =====================================================================
def _ensure_config(patient_id: str, session: Session) -> PatientProConfig:
    cfg = session.get(PatientProConfig, patient_id)
    if not cfg:
        cfg = default_pro_config(patient_id)
        session.add(cfg)
        session.commit()
        session.refresh(cfg)
    return cfg


@app.get("/api/patients/{patient_id}/pro-config")
def get_pro_config(patient_id: str, session: Session = Depends(get_session)):
    p = session.get(Patient, patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    cfg = _ensure_config(patient_id, session)
    return {
        "patient_id": cfg.patient_id,
        "pro_ctcae": cfg.get_pro_ctcae(),
        "hads_enabled": cfg.hads_enabled,
        "hads_subscales": cfg.get_hads_subscales(),
        "frequency": cfg.frequency,
        "cycle_trigger_days": cfg.get_cycle_trigger_days(),
        "thresholds": {
            "pro_ctcae_red": cfg.threshold_pro_ctcae_red,
            "pro_ctcae_persist_days": cfg.threshold_pro_ctcae_persist_days,
            "hads_yellow": cfg.threshold_hads_yellow,
            "hads_red": cfg.threshold_hads_red,
        },
        "tools": cfg.get_tools(),
        "updated_at": cfg.updated_at,
        "updated_by": cfg.updated_by,
    }


@app.get("/api/patients/{patient_id}/pro-config/audit")
def get_pro_config_audit(
    patient_id: str,
    limit: int = 50,
    session: Session = Depends(get_session),
):
    """FN-CUST-008 / FN-AUDIT-001: PRO 세트 변경 이력."""
    rows = session.exec(
        select(ProSetAuditLog)
        .where(ProSetAuditLog.patient_id == patient_id)
        .order_by(ProSetAuditLog.changed_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "changed_at": r.changed_at,
            "changed_by": r.changed_by,
            "action": r.action,
            "diff": _json.loads(r.diff or "{}"),
        }
        for r in rows
    ]


class UpdateProConfigReq(BaseModel):
    pro_ctcae: dict[str, list[str]]
    hads_enabled: bool = True
    hads_subscales: list[str] = ["A", "D"]
    frequency: str = "daily"
    cycle_trigger_days: list[int] = []
    thresholds: Optional[dict[str, int]] = None
    tools: Optional[dict] = None                       # FN-CUST-005 도구별 빈도 등
    updated_by: str = "doctor"


VALID_PRO_CTCAE_SYMPTOMS = set(PRO_CTCAE_ITEMS.keys())
VALID_PRO_CTCAE_ATTRS = {"freq", "severity", "interference"}
VALID_FREQUENCIES = {"daily", "every_3_days", "weekly", "cycle"}


@app.put("/api/patients/{patient_id}/pro-config")
def update_pro_config(
    patient_id: str,
    req: UpdateProConfigReq,
    session: Session = Depends(get_session),
):
    p = session.get(Patient, patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")

    # ---- 검증 ----
    if req.frequency not in VALID_FREQUENCIES:
        raise HTTPException(400, f"frequency must be one of {VALID_FREQUENCIES}")
    if req.frequency == "cycle" and not req.cycle_trigger_days:
        raise HTTPException(400, "cycle frequency requires cycle_trigger_days")
    for symptom, attrs in req.pro_ctcae.items():
        if symptom not in VALID_PRO_CTCAE_SYMPTOMS:
            raise HTTPException(400, f"unknown symptom: {symptom}")
        for a in attrs:
            if a not in VALID_PRO_CTCAE_ATTRS:
                raise HTTPException(400, f"invalid attr {a} for {symptom}")
            # 해당 증상이 실제로 그 attribute를 가지는지
            if a not in PRO_CTCAE_ITEMS[symptom]:
                raise HTTPException(400, f"{symptom} has no {a}")
    for sub in req.hads_subscales:
        if sub not in ("A", "D"):
            raise HTTPException(400, "hads subscale must be A or D")
    if req.hads_enabled and not req.hads_subscales:
        raise HTTPException(400, "hads_enabled but no subscales")

    cfg = _ensure_config(patient_id, session)

    # ---- before snapshot (audit) ----
    before = {
        "pro_ctcae": cfg.get_pro_ctcae(),
        "hads_enabled": cfg.hads_enabled,
        "hads_subscales": cfg.get_hads_subscales(),
        "frequency": cfg.frequency,
        "cycle_trigger_days": cfg.get_cycle_trigger_days(),
        "thresholds": {
            "pro_ctcae_red": cfg.threshold_pro_ctcae_red,
            "pro_ctcae_persist_days": cfg.threshold_pro_ctcae_persist_days,
            "hads_yellow": cfg.threshold_hads_yellow,
            "hads_red": cfg.threshold_hads_red,
        },
        "tools": cfg.get_tools(),
    }

    cfg.set_pro_ctcae(req.pro_ctcae)
    cfg.hads_enabled = req.hads_enabled
    cfg.hads_subscales = ",".join(req.hads_subscales) if req.hads_subscales else ""
    cfg.frequency = req.frequency
    cfg.cycle_trigger_days = ",".join(str(d) for d in req.cycle_trigger_days)
    if req.thresholds:
        cfg.threshold_pro_ctcae_red = req.thresholds.get(
            "pro_ctcae_red", cfg.threshold_pro_ctcae_red)
        cfg.threshold_pro_ctcae_persist_days = req.thresholds.get(
            "pro_ctcae_persist_days", cfg.threshold_pro_ctcae_persist_days)
        cfg.threshold_hads_yellow = req.thresholds.get(
            "hads_yellow", cfg.threshold_hads_yellow)
        cfg.threshold_hads_red = req.thresholds.get(
            "hads_red", cfg.threshold_hads_red)
    if req.tools is not None:
        cfg.set_tools(req.tools)
    cfg.updated_at = datetime.utcnow()
    cfg.updated_by = req.updated_by

    # ---- audit log (FN-CUST-008, FN-AUDIT-001) ----
    after = {
        "pro_ctcae": cfg.get_pro_ctcae(),
        "hads_enabled": cfg.hads_enabled,
        "hads_subscales": cfg.get_hads_subscales(),
        "frequency": cfg.frequency,
        "cycle_trigger_days": cfg.get_cycle_trigger_days(),
        "thresholds": {
            "pro_ctcae_red": cfg.threshold_pro_ctcae_red,
            "pro_ctcae_persist_days": cfg.threshold_pro_ctcae_persist_days,
            "hads_yellow": cfg.threshold_hads_yellow,
            "hads_red": cfg.threshold_hads_red,
        },
        "tools": cfg.get_tools(),
    }
    session.add(ProSetAuditLog(
        patient_id=patient_id,
        changed_by=req.updated_by,
        action="updated",
        diff=_json.dumps({"before": before, "after": after}, ensure_ascii=False),
    ))
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return {
        "updated": True,
        "config": {
            "patient_id": cfg.patient_id,
            "pro_ctcae": cfg.get_pro_ctcae(),
            "hads_enabled": cfg.hads_enabled,
            "hads_subscales": cfg.get_hads_subscales(),
            "frequency": cfg.frequency,
            "cycle_trigger_days": cfg.get_cycle_trigger_days(),
            "thresholds": {
                "pro_ctcae_red": cfg.threshold_pro_ctcae_red,
                "pro_ctcae_persist_days": cfg.threshold_pro_ctcae_persist_days,
                "hads_yellow": cfg.threshold_hads_yellow,
                "hads_red": cfg.threshold_hads_red,
            },
            "updated_at": cfg.updated_at,
            "updated_by": cfg.updated_by,
        },
    }


@app.get("/api/patients/{patient_id}/pro-form")
def get_dynamic_pro_form(
    patient_id: str,
    session: Session = Depends(get_session),
):
    """환자앱 PRO 폼 렌더링용 — config 적용된 질문 리스트."""
    p = session.get(Patient, patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    cfg = _ensure_config(patient_id, session)

    pro_ctcae_items = []
    for symptom, attrs in cfg.get_pro_ctcae().items():
        for attr in attrs:
            q_text = PRO_CTCAE_ITEMS.get(symptom, {}).get(attr)
            if not q_text:
                continue
            pro_ctcae_items.append({
                "symptom": symptom,
                "attribute": attr,
                "question": q_text,
                "scale_labels": PRO_CTCAE_SCALE_LABELS[attr],
            })

    hads_items = []
    if cfg.hads_enabled:
        subs = set(cfg.get_hads_subscales())
        for code, sub, question, reverse in HADS_ITEMS:
            if sub in subs:
                hads_items.append({
                    "code": code, "subscale": sub,
                    "question": question, "reverse": reverse,
                })

    return {
        "pro_ctcae": pro_ctcae_items,
        "hads": hads_items,
        "frequency": cfg.frequency,
        "patient_id": patient_id,
    }


# =====================================================================
# PRO Sessions + Responses
# =====================================================================
class StartSessionReq(BaseModel):
    patient_id: str
    ui_mode: str = "general"
    flex_mode: str = "full"                            # full | quick | no_change


@app.post("/api/pro-sessions")
def start_session(req: StartSessionReq, session: Session = Depends(get_session)):
    p = session.get(Patient, req.patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    if req.flex_mode not in ("full", "quick", "no_change"):
        raise HTTPException(400, "flex_mode must be full|quick|no_change")

    # ---- FN-FLEX-007/008/009 가드 ----
    last_full = session.exec(
        select(ProSession)
        .where(ProSession.patient_id == req.patient_id)
        .where(ProSession.flex_mode == "full")
        .where(ProSession.completed_at != None)
        .order_by(ProSession.started_at.desc())
        .limit(1)
    ).first()

    if req.flex_mode == "no_change":
        if not last_full:
            raise HTTPException(400, "직전 Full 응답이 없어 No-Change를 사용할 수 없습니다.")
        # FN-FLEX-008 Carry-Over 30일 만료
        days_since = (datetime.utcnow() - last_full.started_at).days
        if days_since > 30:
            raise HTTPException(
                400, f"직전 Full 응답이 {days_since}일 경과했습니다. Full 모드로 진행해주세요."
            )
        # FN-FLEX-007 No-Change 연속 3회 상한
        recent = session.exec(
            select(ProSession)
            .where(ProSession.patient_id == req.patient_id)
            .where(ProSession.completed_at != None)
            .order_by(ProSession.started_at.desc())
            .limit(3)
        ).all()
        if len(recent) >= 3 and all(s.flex_mode == "no_change" for s in recent):
            raise HTTPException(400, "No-Change를 연속 3회 사용했습니다. Full/Quick으로 전환하세요.")

    carry_id = last_full.id if req.flex_mode == "no_change" else None
    s = ProSession(
        patient_id=req.patient_id,
        ui_mode=req.ui_mode,
        flex_mode=req.flex_mode,
        carry_over_from_session_id=carry_id,
    )
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


# ---------------- FN-FLEX-002/003 Quick Mode 카테고리 스크리닝 ----------------
QUICK_CATEGORIES = [
    {"id": "fatigue_pain", "label": "피로·통증", "symptoms": ["fatigue"]},
    {"id": "gi", "label": "소화·식욕", "symptoms": ["nausea", "appetite", "diarrhea"]},
    {"id": "neuro", "label": "감각·신경", "symptoms": ["neuropathy"]},
    {"id": "mood", "label": "기분·불안", "symptoms": []},      # HADS-A로 매핑
    {"id": "sleep", "label": "수면", "symptoms": []},          # PSQI로 매핑 (있으면)
]


@app.get("/api/quick-categories")
def get_quick_categories():
    """FN-FLEX-002 Quick Mode 5개 카테고리."""
    return QUICK_CATEGORIES


class QuickScreeningReq(BaseModel):
    session_id: int
    selected_categories: list[str]                     # 양성 응답한 카테고리 id 목록


@app.post("/api/pro-sessions/{session_id}/quick-screening")
def submit_quick_screening(
    session_id: int,
    req: QuickScreeningReq,
    session: Session = Depends(get_session),
):
    """FN-FLEX-003: Quick 양성 카테고리만 세부 문항 반환."""
    s = session.get(ProSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    cfg = _ensure_config(s.patient_id, session)
    enabled_symptoms = set(cfg.get_pro_ctcae().keys())

    selected_symptoms = []
    selected_hads = False
    for cat_id in req.selected_categories:
        cat = next((c for c in QUICK_CATEGORIES if c["id"] == cat_id), None)
        if not cat:
            continue
        for sym in cat["symptoms"]:
            if sym in enabled_symptoms:
                selected_symptoms.append(sym)
        if cat_id == "mood" and cfg.hads_enabled:
            selected_hads = True

    pro_ctcae_items = []
    for sym in selected_symptoms:
        for attr in cfg.get_pro_ctcae().get(sym, []):
            q = PRO_CTCAE_ITEMS.get(sym, {}).get(attr)
            if not q:
                continue
            pro_ctcae_items.append({
                "symptom": sym, "attribute": attr,
                "question": q,
                "scale_labels": PRO_CTCAE_SCALE_LABELS[attr],
            })
    hads_items = []
    if selected_hads:
        subs = set(cfg.get_hads_subscales())
        for code, sub, q, rev in HADS_ITEMS:
            if sub in subs:
                hads_items.append({"code": code, "subscale": sub, "question": q, "reverse": rev})

    return {
        "session_id": session_id,
        "selected_categories": req.selected_categories,
        "pro_ctcae": pro_ctcae_items,
        "hads": hads_items,
    }


# ---------------- FN-FLEX-005 Carry-Over: No-Change 일괄 적용 ----------------
@app.post("/api/pro-sessions/{session_id}/apply-carry-over")
def apply_carry_over(session_id: int, session: Session = Depends(get_session)):
    """FN-FLEX-004/005: 직전 Full 응답을 그대로 복제하여 source='carry_over'로 저장."""
    s = session.get(ProSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    if s.flex_mode != "no_change" or not s.carry_over_from_session_id:
        raise HTTPException(400, "현재 세션이 No-Change 모드가 아닙니다.")

    src = session.exec(
        select(ProResponse).where(ProResponse.session_id == s.carry_over_from_session_id)
    ).all()
    for r in src:
        session.add(ProResponse(
            session_id=session_id,
            tool_code=r.tool_code,
            item_code=r.item_code,
            attribute=r.attribute,
            raw_value=r.raw_value,
            source="carry_over",
        ))
    session.commit()
    return {"copied": len(src), "from_session": s.carry_over_from_session_id}


# ---------------- FN-FLEX-006 Full Mode 월 1회 의무화 (조회 API) ----------------
@app.get("/api/patients/{patient_id}/full-mode-status")
def get_full_mode_status(
    patient_id: str,
    session: Session = Depends(get_session),
):
    """직전 Full 응답 시점 + Full 의무화 필요 여부."""
    last_full = session.exec(
        select(ProSession)
        .where(ProSession.patient_id == patient_id)
        .where(ProSession.flex_mode == "full")
        .where(ProSession.completed_at != None)
        .order_by(ProSession.started_at.desc())
        .limit(1)
    ).first()
    if not last_full:
        return {"requires_full": True, "reason": "Full 응답 이력 없음", "days_since_last_full": None}
    days = (datetime.utcnow() - last_full.started_at).days
    return {
        "requires_full": days >= 30,
        "reason": "직전 Full 후 30일 경과" if days >= 30 else None,
        "days_since_last_full": days,
        "last_full_at": last_full.started_at,
    }


class ResponseItem(BaseModel):
    tool_code: str
    item_code: str
    raw_value: int
    attribute: Optional[str] = None


class SubmitResponsesReq(BaseModel):
    session_id: int
    responses: list[ResponseItem]


@app.post("/api/pro-sessions/{session_id}/responses")
def submit_responses(
    session_id: int,
    req: SubmitResponsesReq,
    session: Session = Depends(get_session),
):
    s = session.get(ProSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    for r in req.responses:
        session.add(ProResponse(
            session_id=session_id,
            tool_code=r.tool_code,
            item_code=r.item_code,
            attribute=r.attribute,
            raw_value=r.raw_value,
        ))
    session.commit()
    return {"saved": len(req.responses)}


@app.post("/api/pro-sessions/{session_id}/complete")
def complete_session(session_id: int, session: Session = Depends(get_session)):
    """채점 → ProScore append + MCID 판정."""
    s = session.get(ProSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    if s.completed_at:
        raise HTTPException(400, "Already completed")

    responses = session.exec(
        select(ProResponse).where(ProResponse.session_id == session_id)
    ).all()

    # 환자별 config 로드 (없으면 기본값)
    cfg = _ensure_config(s.patient_id, session)

    # ---------- HADS 채점 ----------
    hads_responses = {r.item_code: r.raw_value for r in responses
                      if r.tool_code == "HADS"}
    if hads_responses:
        hads_result = score_hads(hads_responses)
        for sub_key in ("hads_a", "hads_d"):
            r = hads_result[sub_key]
            if r["value"] is not None:
                flag = evaluate_mcid_hads(
                    r["value"], r["subscale"],
                    yellow_threshold=cfg.threshold_hads_yellow,
                    red_threshold=cfg.threshold_hads_red,
                )
                session.add(ProScore(
                    session_id=session_id,
                    patient_id=s.patient_id,
                    tool_code="HADS",
                    subscale=r["subscale"],
                    value=r["value"],
                    classification=r["classification"],
                    mcid_flag=flag,
                ))

    # ---------- PRO-CTCAE 채점 ----------
    pro_ctcae_responses = [r for r in responses if r.tool_code == "PRO-CTCAE"]
    by_symptom: dict[str, list[dict]] = {}
    for r in pro_ctcae_responses:
        item = score_pro_ctcae_item(r.item_code, r.attribute or "freq", r.raw_value)
        by_symptom.setdefault(r.item_code, []).append(item)

    # 각 증상별 attribute별로 score 저장 (POC: composite만 ProScore에)
    for symptom, items in by_symptom.items():
        # 직전 N일 history (같은 환자, 같은 symptom severity)
        hist_query = session.exec(
            select(ProResponse, ProSession)
            .where(ProResponse.session_id == ProSession.id)
            .where(ProSession.patient_id == s.patient_id)
            .where(ProResponse.tool_code == "PRO-CTCAE")
            .where(ProResponse.item_code == symptom)
            .where(ProResponse.attribute == "severity")
            .where(ProSession.id != session_id)
            .order_by(ProSession.started_at.desc())
            .limit(5)
        ).all()
        history = [r[0].raw_value for r in hist_query]

        flag = evaluate_mcid_pro_ctcae(
            items, history,
            red_threshold=cfg.threshold_pro_ctcae_red,
            persist_days=cfg.threshold_pro_ctcae_persist_days,
        )
        composite = score_pro_ctcae_composite(items)

        session.add(ProScore(
            session_id=session_id,
            patient_id=s.patient_id,
            tool_code="PRO-CTCAE",
            subscale=symptom,
            value=float(composite["composite"]),
            classification=None,
            mcid_flag=flag,
        ))

    s.completed_at = datetime.utcnow()
    session.add(s)
    session.commit()

    # 산출된 점수 반환
    scores = session.exec(
        select(ProScore).where(ProScore.session_id == session_id)
    ).all()
    return {"completed": True, "scores": scores}


# =====================================================================
# Pre-Visit Report
# =====================================================================
@app.get("/api/patients/{patient_id}/pre-visit-report")
def get_pre_visit_report(
    patient_id: str,
    session: Session = Depends(get_session),
):
    p = session.get(Patient, patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    report = generate_one_line_summary(patient_id, session, window_days=7)
    report["patient"] = {
        "id": p.id, "name": p.name,
        "birth_year": p.birth_year, "icd10": p.icd10,
        "cycle_day": p.cycle_day,
    }
    return report


@app.get("/api/patients/{patient_id}/pro-history")
def get_pro_history(
    patient_id: str,
    session: Session = Depends(get_session),
):
    """환자 PRO 응답·점수 전체 (환자앱 추세 차트용)."""
    sessions = session.exec(
        select(ProSession)
        .where(ProSession.patient_id == patient_id)
        .order_by(ProSession.started_at)
    ).all()
    session_ids = [s.id for s in sessions]
    scores = session.exec(
        select(ProScore).where(ProScore.session_id.in_(session_ids))
    ).all() if session_ids else []
    return {
        "sessions": sessions,
        "scores": scores,
    }


@app.get("/api/patients/{patient_id}/responses-by-day")
def get_responses_by_day(
    patient_id: str,
    days: int = 30,
    session: Session = Depends(get_session),
):
    """일별 실제 PRO 응답 상세 — 응답값 + 라벨 + 점수까지 조인.

    Returns:
        {"patient_id": "C-1042",
         "days": [
            {"date": "2026-04-22",
             "sessions": [
                {"id": 1, "started_at", "completed_at",
                 "ui_mode", "flex_mode",
                 "responses": [
                    {"tool_code": "PRO-CTCAE", "item_code": "fatigue",
                     "attribute": "freq", "raw_value": 1,
                     "label": "드물게", "question": "지난 7일 동안 ..."}
                 ],
                 "scores": [{tool_code, subscale, value, mcid_flag}]
                }]
            }]
        }
    """
    p = session.get(Patient, patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")

    cutoff = datetime.utcnow() - timedelta(days=days)
    sessions = session.exec(
        select(ProSession)
        .where(ProSession.patient_id == patient_id)
        .where(ProSession.started_at >= cutoff)
        .order_by(ProSession.started_at.desc())
    ).all()

    if not sessions:
        return {"patient_id": patient_id, "days": []}

    session_ids = [s.id for s in sessions]
    all_responses = session.exec(
        select(ProResponse).where(ProResponse.session_id.in_(session_ids))
    ).all()
    all_scores = session.exec(
        select(ProScore).where(ProScore.session_id.in_(session_ids))
    ).all()

    # 응답에 라벨/질문 첨부 — UI 가독성
    def enrich_response(r):
        label = None
        question = None
        if r.tool_code == "PRO-CTCAE":
            attrs = PRO_CTCAE_ITEMS.get(r.item_code, {})
            question = attrs.get(r.attribute or "")
            scale = PRO_CTCAE_SCALE_LABELS.get(r.attribute or "", [])
            if 0 <= r.raw_value < len(scale):
                label = scale[r.raw_value]
        elif r.tool_code == "HADS":
            for code, sub, q, rev in HADS_ITEMS:
                if code == r.item_code:
                    question = q
                    break
            scale = ["전혀 없었다", "때때로", "자주", "대부분"]
            if 0 <= r.raw_value < len(scale):
                label = scale[r.raw_value]
        return {
            "tool_code": r.tool_code,
            "item_code": r.item_code,
            "attribute": r.attribute,
            "raw_value": r.raw_value,
            "label": label,
            "question": question,
            "source": r.source,
        }

    # 세션별 묶기
    sessions_by_id: dict = {}
    for s in sessions:
        sessions_by_id[s.id] = {
            "id": s.id,
            "started_at": s.started_at,
            "completed_at": s.completed_at,
            "ui_mode": s.ui_mode,
            "flex_mode": s.flex_mode,
            "responses": [],
            "scores": [],
        }
    for r in all_responses:
        if r.session_id in sessions_by_id:
            sessions_by_id[r.session_id]["responses"].append(enrich_response(r))
    for sc in all_scores:
        if sc.session_id in sessions_by_id:
            sessions_by_id[sc.session_id]["scores"].append({
                "tool_code": sc.tool_code,
                "subscale": sc.subscale,
                "value": sc.value,
                "classification": sc.classification,
                "mcid_flag": sc.mcid_flag,
            })

    # 날짜별 그룹
    by_day: dict = {}
    for s in sessions:
        d = s.started_at.strftime("%Y-%m-%d")
        by_day.setdefault(d, []).append(sessions_by_id[s.id])

    return {
        "patient_id": patient_id,
        "patient_name": p.name,
        "days": [
            {"date": d, "sessions": by_day[d]}
            for d in sorted(by_day.keys(), reverse=True)
        ],
    }


# =====================================================================
# LLM Free Talk (Mock)
# =====================================================================
class TalkReq(BaseModel):
    patient_id: Optional[str] = None
    text: str


@app.post("/api/llm/talk")
def llm_talk(req: TalkReq, session: Session = Depends(get_session)):
    result = classify_and_respond(req.text)
    # PII 마스킹된 텍스트로 audit 저장 (원문 저장 안 함)
    audit = LlmAudit(
        patient_id=req.patient_id,
        prompt=result.get("redacted_text", req.text),
        response=result["response"],
        guardrail_triggered=result["type"] if result["type"] != "normal" else None,
        llm_mode=settings.LLM_MODE,
    )
    session.add(audit)
    session.commit()
    return result


@app.get("/api/llm/audit")
def list_audit(
    patient_id: Optional[str] = None,
    limit: int = 50,
    session: Session = Depends(get_session),
):
    q = select(LlmAudit).order_by(LlmAudit.created_at.desc()).limit(limit)
    if patient_id:
        q = q.where(LlmAudit.patient_id == patient_id)
    return session.exec(q).all()


# =====================================================================
# Web Push
# =====================================================================
class SubscribeReq(BaseModel):
    patient_id: str
    endpoint: str
    p256dh: str
    auth: str


@app.post("/api/push/subscribe")
def push_subscribe(req: SubscribeReq, session: Session = Depends(get_session)):
    existing = session.exec(
        select(PushSubscription).where(PushSubscription.endpoint == req.endpoint)
    ).first()
    if existing:
        # endpoint는 같지만 patient_id가 바뀌었을 수 있음 → 갱신
        if existing.patient_id != req.patient_id:
            existing.patient_id = req.patient_id
            session.add(existing)
            session.commit()
            return {"subscribed": True, "reason": "patient_id updated"}
        return {"subscribed": False, "reason": "already exists"}
    sub = PushSubscription(**req.model_dump())
    session.add(sub)
    session.commit()
    return {"subscribed": True}


@app.get("/api/push/subscriptions/{patient_id}")
def list_push_subscriptions(
    patient_id: str,
    session: Session = Depends(get_session),
):
    """디버깅용: 환자별 구독 디바이스 목록."""
    subs = session.exec(
        select(PushSubscription).where(PushSubscription.patient_id == patient_id)
    ).all()
    return {
        "patient_id": patient_id,
        "count": len(subs),
        "subscriptions": [
            {
                "id": s.id,
                "endpoint_host": s.endpoint.split("/")[2] if "://" in s.endpoint else s.endpoint[:30],
                "endpoint_truncated": s.endpoint[:80] + "..." if len(s.endpoint) > 80 else s.endpoint,
                "created_at": s.created_at,
            }
            for s in subs
        ],
    }


@app.delete("/api/push/subscriptions/{patient_id}")
def clear_push_subscriptions(
    patient_id: str,
    session: Session = Depends(get_session),
):
    """환자 구독 전체 삭제 (재구독 테스트용)."""
    subs = session.exec(
        select(PushSubscription).where(PushSubscription.patient_id == patient_id)
    ).all()
    n = len(subs)
    for s in subs:
        session.delete(s)
    session.commit()
    return {"deleted": n}


class SendPushReq(BaseModel):
    patient_id: str
    title: str = "오늘의 PRO 설문"
    body: str = "5분만 시간 내주세요"
    url: str = "/pro"


@app.post("/api/push/send")
def push_send(req: SendPushReq, session: Session = Depends(get_session)):
    """푸시 발송 + 디버깅 정보 풍부하게 반환."""
    # 구독 사전 체크
    subs = session.exec(
        select(PushSubscription).where(PushSubscription.patient_id == req.patient_id)
    ).all()
    if not subs:
        return {
            "sent": 0,
            "failed": [],
            "subscription_count": 0,
            "reason": "no_subscriptions",
            "hint": (
                "환자앱에서 'Web Push 알림 구독' 버튼을 먼저 눌러야 합니다. "
                "환자앱 홈에서 알림 권한 허용 후 다시 시도하세요."
            ),
        }
    if not settings.VAPID_PRIVATE_KEY:
        return {
            "sent": 0, "failed": [],
            "subscription_count": len(subs),
            "reason": "no_vapid_key",
            "hint": "VAPID_PRIVATE_KEY 미설정. setup.sh 또는 .env 확인.",
        }
    result = send_push(req.patient_id, req.title, req.body, req.url)
    result["subscription_count"] = len(subs)
    return result


# =====================================================================
# Scheduled / Cron-style Tasks (FN-RPT-007, FN-EVENT-001/002)
# 외부 cron이 호출하거나 데모용으로 어드민에서 트리거.
# =====================================================================
@app.post("/api/jobs/precompute-pre-visit")
def job_precompute_pre_visit(session: Session = Depends(get_session)):
    """FN-RPT-007: 외래 D-2 가정 — 모든 환자 Pre-Visit Report를 미리 계산.
    POC에서는 단순히 모든 환자에 대해 generate_one_line_summary 실행."""
    patients = session.exec(select(Patient)).all()
    results = []
    for p in patients:
        rpt = generate_one_line_summary(p.id, session, window_days=7)
        results.append({
            "patient_id": p.id,
            "name": p.name,
            "summary": rpt["summary"],
            "alert_count": len(rpt["alerts"]),
            "completion_rate": rpt.get("completion", {}).get("rate"),
        })
    return {"computed": len(results), "patients": results}


@app.post("/api/jobs/check-mcid-and-push")
def job_check_mcid_and_push(session: Session = Depends(get_session)):
    """FN-EVENT-001: 모든 환자의 최신 점수에서 RED 알림 발생 시 자동 푸시."""
    patients = session.exec(select(Patient)).all()
    notified = []
    for p in patients:
        rpt = generate_one_line_summary(p.id, session, window_days=7)
        red = [a for a in rpt["alerts"] if a["level"] == "red"]
        if not red:
            continue
        # 환자에게 알림 푸시 (자기 점수 확인 권장)
        result = send_push(
            p.id,
            "🔴 PRO 알림",
            f"{red[0]['tool']} {red[0]['subscale']} 임계값 초과 — 의료진 확인 예정",
            "/result",
        )
        notified.append({
            "patient_id": p.id,
            "alerts": red,
            "push_sent": result.get("sent", 0),
        })
    return {"notified": len(notified), "details": notified}


@app.post("/api/jobs/check-non-response")
def job_check_non_response(session: Session = Depends(get_session)):
    """FN-EVENT-002: 3일 연속 미응답 환자 감지하여 푸시."""
    patients = session.exec(select(Patient)).all()
    detected = []
    for p in patients:
        rpt = generate_one_line_summary(p.id, session, window_days=7)
        consec = rpt.get("completion", {}).get("consecutive_missing", 0)
        if consec >= 3:
            result = send_push(
                p.id,
                "PRO 응답 알림",
                f"{consec}일째 응답이 없습니다. 잠시만 시간을 내주세요.",
                "/pro/start",
            )
            detected.append({
                "patient_id": p.id,
                "consecutive_missing": consec,
                "push_sent": result.get("sent", 0),
            })
    return {"detected": len(detected), "details": detected}


@app.get("/api/push/vapid-public-key")
def vapid_public_key():
    return {"public_key": settings.VAPID_PUBLIC_KEY}


# =====================================================================
# 의료진 모니터링 — 담당 환자 목록 (긴급/주의/안정 분류)
# =====================================================================
@app.get("/api/admin/dashboard")
def admin_dashboard(session: Session = Depends(get_session)):
    patients = session.exec(select(Patient)).all()
    rows = []
    for p in patients:
        report = generate_one_line_summary(p.id, session, window_days=7)
        red = sum(1 for a in report["alerts"] if a["level"] == "red")
        yellow = sum(1 for a in report["alerts"] if a["level"] == "yellow")
        if red >= 1:
            level = "critical"
        elif yellow >= 1:
            level = "warning"
        else:
            level = "stable"
        rows.append({
            "patient": p,
            "level": level,
            "red_count": red,
            "yellow_count": yellow,
            "summary": report["summary"],
            "session_count": report.get("session_count", 0),
        })
    return rows


# =====================================================================
# Health
# =====================================================================
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "llm_mode": settings.LLM_MODE,
        "vapid_configured": bool(settings.VAPID_PRIVATE_KEY),
    }
