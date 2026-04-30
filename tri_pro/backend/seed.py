"""5명 환자 합성 시드.

나이대·암종·치료 레지멘·심각도를 분산해서 어드민 대시보드에서
🔴/🟡/🟢 분포가 한 화면에 보이도록 구성.

| ID      | 이름   | 나이 | 진단        | 사이클 | 모드   | 심각도 | 핵심 패턴                     |
|---------|--------|------|-------------|--------|--------|--------|-------------------------------|
| C-1042  | 이○○ |  73  | C18.9 결장 |  D14   | general| 🔴 RED | Oxaliplatin 신경병증 1→3 진행 |
| C-2103  | 박○○ |  58  | C20 직장   |  D7    | general| 🔴 RED | Chemoradiation 피로 3 지속    |
| C-3027  | 최○○ |  67  | C34.1 폐  |  D21   | general| 🟢 GR  | Pembrolizumab 안정             |
| C-4581  | 김○○ |  81  | C18.0 결장 |  D3    | elder  | 🟡 YEL | FOLFIRI 오심·식욕 YELLOW       |
| C-5219  | 정○○ |  45  | C16 위    |  D10   | general| 🔴 RED | FOLFOX HADS-A 11 (case)       |
"""
import os
import sys
from datetime import datetime, timedelta
from sqlmodel import Session, SQLModel, select, delete

from models import (
    engine, init_db,
    Patient, ProSession, ProResponse, ProScore, LlmAudit, PushSubscription,
    PatientProConfig, ProSetAuditLog, EducationCard,
    CustomProSet, CustomQuestionResponse,
    recommend_default_pro_set,
)
from scoring import (
    score_hads, evaluate_mcid_hads, evaluate_mcid_pro_ctcae,
    score_pro_ctcae_item, score_pro_ctcae_composite,
)


# ============================================================
# 환자 프로필 — 7일 PRO 패턴
# ============================================================
PROFILES = [
    {
        "id": "C-1042", "name": "이○○", "birth_year": 1953,
        "icd10": "C18.9", "cycle_day": 14, "ui_mode": "general",
        "regimen": "Oxaliplatin (FOLFOX 8th)",
        "comment": "신경병증 점진 악화 — 신경독성 평가 필요",
        "patterns": {
            "fatigue":    {"freq":[1,2,3,3,2,2,1], "severity":[1,2,2,3,2,1,1], "interference":[0,1,2,2,1,1,0]},
            "appetite":   {"freq":[1,2,3,2,1,1,0], "interference":[0,1,2,1,1,0,0]},
            "nausea":     {"freq":[0,1,2,1,0,0,0], "severity":[0,1,1,1,0,0,0], "interference":[0,0,1,0,0,0,0]},
            "diarrhea":   {"freq":[0,1,1,0,0,1,0]},
            "neuropathy": {"severity":[1,1,2,2,3,3,3], "interference":[0,0,1,1,2,2,2]},
        },
        "hads_day": 6,
        "hads_target": {"A": 8, "D": 5},
    },
    {
        "id": "C-2103", "name": "박○○", "birth_year": 1968,
        "icd10": "C20", "cycle_day": 7, "ui_mode": "general",
        "regimen": "Chemoradiation (Capecitabine + RT)",
        "comment": "피로·설사 지속 — 직장 항암방사선 표준 부작용",
        "patterns": {
            "fatigue":    {"freq":[2,3,3,3,3,3,3], "severity":[2,2,3,3,3,3,3], "interference":[1,2,2,3,3,3,3]},
            "appetite":   {"freq":[1,1,2,2,2,2,2], "interference":[0,0,1,1,1,1,1]},
            "diarrhea":   {"freq":[1,2,2,3,3,2,2]},
            "neuropathy": {"severity":[0,0,1,1,1,1,1], "interference":[0,0,0,0,0,0,0]},
        },
        "hads_day": 6,
        "hads_target": {"A": 6, "D": 4},
    },
    {
        "id": "C-3027", "name": "최○○", "birth_year": 1959,
        "icd10": "C34.1", "cycle_day": 21, "ui_mode": "general",
        "regimen": "Pembrolizumab Q3W (12cycle)",
        "comment": "면역항암제 안정기 — 부작용 미미",
        "patterns": {
            "fatigue":    {"freq":[1,1,1,0,1,1,0], "severity":[1,1,0,0,1,0,0], "interference":[0,0,0,0,0,0,0]},
            "appetite":   {"freq":[0,1,0,0,0,0,0]},
            "nausea":     {"freq":[0,0,0,0,0,0,0], "severity":[0,0,0,0,0,0,0]},
        },
        "hads_day": 6,
        "hads_target": {"A": 3, "D": 2},
    },
    {
        "id": "C-4581", "name": "김○○", "birth_year": 1945,
        "icd10": "C18.0", "cycle_day": 3, "ui_mode": "elder",
        "regimen": "FOLFIRI 1cycle Day3",
        "comment": "오심·식욕부진 — 항구토제 효과 점검 필요. 어르신 모드.",
        "patterns": {
            "fatigue":    {"freq":[1,2,2,2,2,2,1], "severity":[1,1,2,2,1,1,1]},
            "appetite":   {"freq":[1,2,3,3,2,1,1], "interference":[0,1,2,2,1,0,0]},
            "nausea":     {"freq":[1,2,3,3,2,2,2], "severity":[1,1,2,2,2,1,1], "interference":[0,1,2,2,1,1,1]},
            "diarrhea":   {"freq":[0,1,2,1,0,0,0]},
        },
        "hads_day": 6,
        "hads_target": {"A": 7, "D": 6},
    },
    {
        "id": "C-5219", "name": "정○○", "birth_year": 1981,
        "icd10": "C16.9", "cycle_day": 10, "ui_mode": "general",
        "regimen": "FOLFOX 4cycle Day10 — 위절제술 후",
        "comment": "젊은 환자, HADS-A 11 RED — 정신과 협진 권고",
        "patterns": {
            "fatigue":    {"freq":[2,2,3,3,2,2,2], "severity":[1,2,2,2,2,1,1], "interference":[1,1,2,2,1,1,1]},
            "appetite":   {"freq":[1,1,2,2,1,1,1]},
            "nausea":     {"freq":[1,2,2,1,1,1,0], "severity":[1,1,1,1,0,0,0]},
            "neuropathy": {"severity":[1,1,1,1,1,1,1]},
        },
        "hads_day": 6,
        "hads_target": {"A": 11, "D": 8},
    },
]


def _mk_hads_responses(target_a: int, target_d: int) -> dict:
    """HADS-A·D가 정확히 target 점수가 되도록 14문항 응답 생성."""
    r: dict = {}

    a4 = 2
    rest_a = target_a - (3 - a4)
    base = max(0, min(3, rest_a // 6))
    extra = max(0, rest_a - base * 6)
    for i, k in enumerate(["A1","A2","A3","A5","A6","A7"]):
        r[k] = base + (1 if i < extra else 0)
    r["A4"] = a4

    d4 = 0
    target_x_sum = 18 - (target_d - d4)
    base = max(0, min(3, target_x_sum // 6))
    extra = max(0, target_x_sum - base * 6)
    for i, k in enumerate(["D1","D2","D3","D5","D6","D7"]):
        r[k] = base + (1 if i < extra else 0)
    r["D4"] = d4

    for k, v in r.items():
        r[k] = max(0, min(3, v))
    return r


def reset_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def seed():
    init_db()
    with Session(engine) as session:
        for model in [LlmAudit, ProScore, ProResponse, ProSession,
                      PushSubscription, ProSetAuditLog, PatientProConfig,
                      EducationCard, CustomQuestionResponse, CustomProSet,
                      Patient]:
            session.exec(delete(model))
        session.commit()

        # 샘플 커스텀 세트 1개 — 의사가 자주 쓰는 템플릿
        sample_set = CustomProSet(
            name="Oxaliplatin 신경병증 추적",
            description=(
                "FOLFOX 계열 환자용. PRO-CTCAE 신경병증 강조 + "
                "찬물 노출 커스텀 문항 2개."
            ),
            target_icd10="C18",
            created_by="seed",
        )
        sample_set.set_config({
            "tools": {
                "PRO-CTCAE": {
                    "enabled": True,
                    "pro_ctcae": {
                        "neuropathy": ["severity", "interference"],
                        "fatigue": ["freq", "severity"],
                    },
                    "frequency": "daily",
                },
                "HADS": {"enabled": True, "subscales": ["A", "D"],
                         "frequency": "monthly"},
                "FACT-C": {"enabled": True, "frequency": "monthly"},
            },
            "custom_questions": [
                {"code": "CUST-1", "question": "오늘 손이 차가운 느낌이 어땠나요?",
                 "response_type": "likert_5",
                 "scale_labels": ["없음","약함","보통","심함","매우 심함"]},
                {"code": "CUST-2", "question": "찬물 닿을 때 얼얼함이 있었나요?",
                 "response_type": "yes_no",
                 "scale_labels": ["없음","있음"]},
            ],
        })
        session.add(sample_set)
        session.commit()
        print("✓ 샘플 커스텀 세트 등록: Oxaliplatin 신경병증 추적")

        base_date = datetime.utcnow() - timedelta(days=7)

        for profile in PROFILES:
            patient = Patient(
                id=profile["id"],
                name=profile["name"],
                birth_year=profile["birth_year"],
                icd10=profile["icd10"],
                cycle_day=profile["cycle_day"],
                caregiver_phone=os.environ.get(
                    "NEXT_PUBLIC_CAREGIVER_TEL", "010-0000-0000"),
            )
            session.add(patient)
            session.commit()

            age = 2026 - profile["birth_year"]
            print(f"\n[{profile['id']}] {profile['name']} ({age}세, "
                  f"{profile['icd10']}, {profile['ui_mode']} 모드)")
            print(f"  └ {profile['regimen']}")

            # ICD-10 + 나이로 필수/선택 PRO 세트 자동 추천
            recommended = recommend_default_pro_set(profile["icd10"], age)
            cfg = PatientProConfig(patient_id=profile["id"])
            cfg.set_pro_ctcae(recommended.get("pro_ctcae", {
                "fatigue": ["freq", "severity"],
                "nausea": ["severity"],
            }))
            cfg.frequency = "daily"
            # tools_config: 필수+선택 모두 저장 (UI에서 lock/toggle 분기)
            tools_cfg = {}
            for tcode, tprops in recommended["tools"].items():
                tools_cfg[tcode] = {
                    **tprops,
                    "required": tcode in recommended["required"],
                }
            cfg.set_tools(tools_cfg)
            cfg.updated_by = "seed"
            session.add(cfg)
            session.commit()
            req = ", ".join(recommended["required"])
            opt = ", ".join(recommended["optional"])
            print(f"  └ 필수 PRO: {req}")
            print(f"  └ 선택 PRO: {opt}")

            for day in range(7):
                session_dt = base_date + timedelta(days=day, hours=9)
                pro_session = ProSession(
                    patient_id=profile["id"],
                    started_at=session_dt,
                    completed_at=session_dt + timedelta(minutes=4),
                    ui_mode=profile["ui_mode"],
                    flex_mode="full",
                )
                session.add(pro_session)
                session.commit()
                session.refresh(pro_session)

                for symptom, attrs in profile["patterns"].items():
                    for attr, values in attrs.items():
                        if day < len(values):
                            session.add(ProResponse(
                                session_id=pro_session.id,
                                tool_code="PRO-CTCAE",
                                item_code=symptom,
                                attribute=attr,
                                raw_value=values[day],
                            ))

                if day == profile["hads_day"]:
                    hads_resp = _mk_hads_responses(
                        profile["hads_target"]["A"],
                        profile["hads_target"]["D"],
                    )
                    for code, value in hads_resp.items():
                        session.add(ProResponse(
                            session_id=pro_session.id,
                            tool_code="HADS",
                            item_code=code,
                            raw_value=value,
                        ))
                session.commit()

                _score_session(session, pro_session, profile["id"])

            print(f"  └ 7일 시드 완료 (HADS-A={profile['hads_target']['A']}, "
                  f"HADS-D={profile['hads_target']['D']})")

    print()
    print("═" * 50)
    print(f"  ✅ {len(PROFILES)}명 환자 시드 완료")
    print("═" * 50)


def _score_session(session, ps, patient_id):
    responses = session.exec(
        select(ProResponse).where(ProResponse.session_id == ps.id)
    ).all()

    by_symptom = {}
    for r in responses:
        if r.tool_code != "PRO-CTCAE":
            continue
        item = score_pro_ctcae_item(r.item_code, r.attribute, r.raw_value)
        by_symptom.setdefault(r.item_code, []).append(item)

    for symptom, items in by_symptom.items():
        hist_q = session.exec(
            select(ProResponse, ProSession)
            .where(ProResponse.session_id == ProSession.id)
            .where(ProSession.patient_id == patient_id)
            .where(ProResponse.tool_code == "PRO-CTCAE")
            .where(ProResponse.item_code == symptom)
            .where(ProResponse.attribute == "severity")
            .where(ProSession.id != ps.id)
            .order_by(ProSession.started_at.desc())
            .limit(5)
        ).all()
        history = [r[0].raw_value for r in hist_q]

        composite = score_pro_ctcae_composite(items)
        flag = evaluate_mcid_pro_ctcae(items, history)
        session.add(ProScore(
            session_id=ps.id,
            patient_id=patient_id,
            tool_code="PRO-CTCAE",
            subscale=symptom,
            value=float(composite["composite"]),
            mcid_flag=flag,
            computed_at=ps.started_at + timedelta(minutes=5),
        ))

    hads_responses = {r.item_code: r.raw_value
                      for r in responses if r.tool_code == "HADS"}
    if hads_responses:
        hads_result = score_hads(hads_responses)
        for sub_key in ("hads_a", "hads_d"):
            rec = hads_result[sub_key]
            if rec["value"] is not None:
                flag = evaluate_mcid_hads(rec["value"], rec["subscale"])
                session.add(ProScore(
                    session_id=ps.id,
                    patient_id=patient_id,
                    tool_code="HADS",
                    subscale=rec["subscale"],
                    value=rec["value"],
                    classification=rec["classification"],
                    mcid_flag=flag,
                    computed_at=ps.started_at + timedelta(minutes=5),
                ))
    session.commit()


if __name__ == "__main__":
    if "--reset" in sys.argv:
        print("⚠️ DB 전체 리셋")
        reset_db()
    seed()
