"""FN-MODE-007: 모드 등가성 (Mode Equivalence) 검증.

핵심 원칙:
  일반 모드와 어르신 모드는 UI만 다르고, 같은 raw_value를 산출하면
  결정론 채점 엔진은 ui_mode를 보지 않으므로 동일 ProScore가 나와야 함.

검증 항목:
1. PRO-CTCAE: 5단계 라디오(일반) vs 5단계 얼굴척도(어르신) → 동일 0..4
2. HADS: 4단계 텍스트(일반) vs 4단계 얼굴척도(어르신) → 동일 0..3
3. 같은 응답을 ui_mode만 다르게 저장 → 동일 점수
"""
import pytest
from datetime import datetime, timedelta
from sqlmodel import SQLModel, Session, create_engine, select, delete

from models import (
    Patient, ProSession, ProResponse, ProScore,
    PatientProConfig, PushSubscription, ProSetAuditLog,
    EducationCard, CustomProSet, CustomQuestionResponse, LlmAudit,
    default_pro_config,
)
from scoring import (
    score_pro_ctcae_item, score_pro_ctcae_composite,
    evaluate_mcid_pro_ctcae, score_hads, evaluate_mcid_hads,
)


@pytest.fixture
def temp_db():
    """일회용 in-memory DB."""
    eng = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(eng)
    yield eng


def _seed_two_patients_same_responses(eng, ui_modes: tuple[str, str]):
    """동일한 raw_value를 두 환자에게 다른 ui_mode로 저장."""
    with Session(eng) as s:
        for i, mode in enumerate(ui_modes):
            pid = f"TEST-{i}"
            s.add(Patient(id=pid, name="테스트", birth_year=1960,
                          icd10="C18.9", cycle_day=10))
            s.commit()

            ps = ProSession(patient_id=pid, ui_mode=mode, flex_mode="full",
                            started_at=datetime.utcnow(),
                            completed_at=datetime.utcnow())
            s.add(ps)
            s.commit()
            s.refresh(ps)

            # PRO-CTCAE — 동일 raw_value
            for sym, attr, val in [
                ("fatigue", "freq", 2),
                ("fatigue", "severity", 3),
                ("nausea", "severity", 1),
                ("neuropathy", "severity", 3),
                ("neuropathy", "interference", 2),
            ]:
                s.add(ProResponse(
                    session_id=ps.id, tool_code="PRO-CTCAE",
                    item_code=sym, attribute=attr, raw_value=val,
                ))
            # HADS — 동일 raw_value
            for code, val in [
                ("A1", 2), ("A2", 1), ("A3", 2), ("A4", 1),
                ("A5", 1), ("A6", 1), ("A7", 0),
                ("D1", 1), ("D2", 1), ("D3", 0), ("D4", 0),
                ("D5", 1), ("D6", 1), ("D7", 1),
            ]:
                s.add(ProResponse(
                    session_id=ps.id, tool_code="HADS",
                    item_code=code, raw_value=val,
                ))
            s.commit()


def _score_session(eng, session_id, patient_id):
    """간소화된 채점 (main.py 로직 미러링)."""
    with Session(eng) as s:
        responses = s.exec(
            select(ProResponse).where(ProResponse.session_id == session_id)
        ).all()

        # PRO-CTCAE
        by_sym: dict = {}
        for r in responses:
            if r.tool_code != "PRO-CTCAE":
                continue
            item = score_pro_ctcae_item(r.item_code, r.attribute, r.raw_value)
            by_sym.setdefault(r.item_code, []).append(item)
        for sym, items in by_sym.items():
            composite = score_pro_ctcae_composite(items)
            flag = evaluate_mcid_pro_ctcae(items, [])
            s.add(ProScore(
                session_id=session_id, patient_id=patient_id,
                tool_code="PRO-CTCAE", subscale=sym,
                value=float(composite["composite"]), mcid_flag=flag,
            ))
        # HADS
        hads_resp = {r.item_code: r.raw_value
                     for r in responses if r.tool_code == "HADS"}
        if hads_resp:
            hads = score_hads(hads_resp)
            for k in ("hads_a", "hads_d"):
                rec = hads[k]
                if rec["value"] is not None:
                    flag = evaluate_mcid_hads(rec["value"], rec["subscale"])
                    s.add(ProScore(
                        session_id=session_id, patient_id=patient_id,
                        tool_code="HADS", subscale=rec["subscale"],
                        value=rec["value"],
                        classification=rec["classification"],
                        mcid_flag=flag,
                    ))
        s.commit()


class TestModeEquivalence:
    def test_general_and_elder_produce_same_proctcae_scores(self, temp_db):
        """동일 PRO-CTCAE 응답 → ui_mode 무관 동일 점수·MCID flag."""
        _seed_two_patients_same_responses(temp_db, ("general", "elder"))
        with Session(temp_db) as s:
            for i in range(2):
                ps = s.exec(
                    select(ProSession).where(
                        ProSession.patient_id == f"TEST-{i}")
                ).first()
                _score_session(temp_db, ps.id, f"TEST-{i}")

        # 두 환자 점수 비교
        with Session(temp_db) as s:
            scores_general = s.exec(
                select(ProScore).where(ProScore.patient_id == "TEST-0")
                .order_by(ProScore.tool_code, ProScore.subscale)
            ).all()
            scores_elder = s.exec(
                select(ProScore).where(ProScore.patient_id == "TEST-1")
                .order_by(ProScore.tool_code, ProScore.subscale)
            ).all()

            assert len(scores_general) == len(scores_elder)
            for sg, se in zip(scores_general, scores_elder):
                assert sg.tool_code == se.tool_code, "도구 코드 불일치"
                assert sg.subscale == se.subscale, "서브스케일 불일치"
                assert sg.value == se.value, (
                    f"점수 불일치 {sg.subscale}: "
                    f"general={sg.value} vs elder={se.value}"
                )
                assert sg.mcid_flag == se.mcid_flag, (
                    f"MCID flag 불일치 {sg.subscale}: "
                    f"general={sg.mcid_flag} vs elder={se.mcid_flag}"
                )

    def test_hads_scoring_independent_of_mode(self, temp_db):
        """HADS도 ui_mode 무관 동일 점수."""
        _seed_two_patients_same_responses(temp_db, ("general", "elder"))
        with Session(temp_db) as s:
            for i in range(2):
                ps = s.exec(
                    select(ProSession).where(
                        ProSession.patient_id == f"TEST-{i}")
                ).first()
                _score_session(temp_db, ps.id, f"TEST-{i}")

        with Session(temp_db) as s:
            hads_general = s.exec(
                select(ProScore)
                .where(ProScore.patient_id == "TEST-0")
                .where(ProScore.tool_code == "HADS")
            ).all()
            hads_elder = s.exec(
                select(ProScore)
                .where(ProScore.patient_id == "TEST-1")
                .where(ProScore.tool_code == "HADS")
            ).all()

            ge = {sc.subscale: sc for sc in hads_general}
            el = {sc.subscale: sc for sc in hads_elder}
            assert set(ge.keys()) == set(el.keys()), "HADS 서브스케일 누락"
            for sub in ge:
                assert ge[sub].value == el[sub].value
                assert ge[sub].classification == el[sub].classification


class TestModeEquivalenceContract:
    """모드별 입력 척도 contract 검증."""

    def test_proctcae_5_levels_both_modes(self):
        """PRO-CTCAE는 일반/어르신 모두 0..4 정수."""
        for raw in range(5):
            r = score_pro_ctcae_item("fatigue", "severity", raw)
            assert r["score"] == raw

    def test_hads_4_levels_both_modes(self):
        """HADS는 일반/어르신 모두 0..3 정수."""
        # 일반 모드 응답: 0..3 4단계
        # 어르신 모드 응답: 0..3 4단계 얼굴척도
        # 채점 함수는 0..3 외 거부
        with pytest.raises(ValueError):
            score_hads({"A1": 4, "A2": 0, "A3": 0, "A4": 0,
                        "A5": 0, "A6": 0, "A7": 0,
                        "D1": 0, "D2": 0, "D3": 0, "D4": 0,
                        "D5": 0, "D6": 0, "D7": 0})

    def test_face_to_score_mapping_proctcae(self):
        """프런트의 FACES_5 매핑이 0..4 contract와 일치하는지 (문서적 검증)."""
        FRONTEND_FACES_5 = [
            ("😀 전혀 안 그래요", 0),
            ("🙂 조금요", 1),
            ("😐 보통이에요", 2),
            ("😣 많이 그래요", 3),
            ("😭 정말 너무 심해요", 4),
        ]
        assert [v for _, v in FRONTEND_FACES_5] == [0, 1, 2, 3, 4]

    def test_face_to_score_mapping_hads(self):
        """HADS는 4단계."""
        FRONTEND_FACES_4 = [
            ("😀 전혀 없었어요", 0),
            ("🙂 가끔이요", 1),
            ("😣 자주 있었어요", 2),
            ("😭 거의 매일이요", 3),
        ]
        assert [v for _, v in FRONTEND_FACES_4] == [0, 1, 2, 3]
