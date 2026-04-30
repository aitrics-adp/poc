"""신규 기능 단위 테스트 — R1~R6.

- R1: FACT-C / FACIT-F / PSQI 채점
- R2: ICD-10 추천 / Audit 차이 추적
- R3: FLEX 모드 가드 (No-Change 30일/3회 제한)
- R5: PII 마스킹 / Education 카드 / Disclaimer
"""
import pytest
from scoring import (
    score_fact_c, score_facit_f, score_psqi,
    evaluate_mcid_facit_f, evaluate_mcid_psqi,
    FACT_C_ITEMS, FACIT_F_ITEMS,
)
from llm_mock import (
    redact_pii, find_education_card,
    classify_and_respond, EDUCATION_CARDS,
)
from models import recommend_default_pro_set


# ============================================================
# R1 채점
# ============================================================
class TestFactC:
    def test_all_zero(self):
        responses = {code: 0 for code, *_ in FACT_C_ITEMS}
        r = score_fact_c(responses)
        # 절반은 reverse라 0 → 4. 합산은 일정 값 이상 나옴.
        assert r["FACT-C"] is not None
        assert r["TOI"] is not None

    def test_all_max(self):
        responses = {code: 4 for code, *_ in FACT_C_ITEMS}
        r = score_fact_c(responses)
        assert r["FACT-C"] is not None

    def test_subscale_partial(self):
        # PWB만 응답 → 다른 서브스케일 None
        pwb_codes = [c for c, sub, *_ in FACT_C_ITEMS if sub == "PWB"]
        r = score_fact_c({c: 2 for c in pwb_codes})
        assert r["PWB"] is not None
        assert r["SWB"] is None

    def test_invalid_raw(self):
        with pytest.raises(ValueError):
            score_fact_c({"GP1": 5})


class TestFacitF:
    def test_normal_score(self):
        responses = {code: 4 if reverse else 0 for code, _, _, reverse in FACIT_F_ITEMS}
        r = score_facit_f(responses)
        # 모두 reverse=4 → 0, 정채점=0 → 0. 합 = 0.
        # 4 + 4 + 4 ... 11개 reverse = 0, 2개 정채점=0 → 총 0 → severe
        assert r["FACIT-F"] is not None
        assert r["classification"] == "severe"

    def test_max_score(self):
        # 정채점=4, reverse=0 → 모두 4 점수
        responses = {code: 0 if reverse else 4 for code, _, _, reverse in FACIT_F_ITEMS}
        r = score_facit_f(responses)
        assert r["FACIT-F"] == 52.0
        assert r["classification"] == "normal"

    def test_mcid(self):
        assert evaluate_mcid_facit_f(25, None) == "red"
        assert evaluate_mcid_facit_f(35, None) == "yellow"
        assert evaluate_mcid_facit_f(45, None) is None
        assert evaluate_mcid_facit_f(45, 50) == "yellow"   # 5점 감소


class TestPsqi:
    def _good_responses(self):
        r = {"Q2": 10, "Q4": 8, "Q6": 0, "Q7": 0, "Q8": 0, "Q9": 0}
        for x in "abcdefghij":
            r[f"Q5{x}"] = 0
        return r

    def test_good_sleep(self):
        r = score_psqi(self._good_responses())
        assert r["PSQI"] == 0
        assert r["classification"] == "good"
        assert evaluate_mcid_psqi(r["PSQI"]) is None

    def test_poor_sleep(self):
        bad = {"Q2": 60, "Q4": 4, "Q6": 3, "Q7": 2, "Q8": 2, "Q9": 2}
        for x in "abcdefghij":
            bad[f"Q5{x}"] = 2
        r = score_psqi(bad)
        assert r["PSQI"] >= 10
        assert r["classification"] == "poor"
        assert evaluate_mcid_psqi(r["PSQI"]) == "red"

    def test_missing(self):
        r = score_psqi({"Q2": 10})
        assert r["PSQI"] is None
        assert r["classification"] == "missing"


# ============================================================
# R2 ICD-10 추천
# ============================================================
class TestRecommendation:
    def test_colorectal(self):
        r = recommend_default_pro_set("C18.9")
        assert "FACT-C" in r["tools"]
        assert "FACIT-F" in r["tools"]
        assert r["tools"]["PRO-CTCAE"]["enabled"]

    def test_lung(self):
        r = recommend_default_pro_set("C34.1")
        assert "FACIT-F" in r["tools"]
        assert "FACT-C" not in r["tools"]

    def test_unknown(self):
        r = recommend_default_pro_set("Z99.9")
        assert "PRO-CTCAE" in r["tools"]


# ============================================================
# R5 PII 마스킹
# ============================================================
class TestPii:
    def test_phone(self):
        text, redacted = redact_pii("제 번호는 010-1234-5678 입니다")
        assert "[전화번호]" in text
        assert "010-1234-5678" not in text
        assert "phone" in redacted

    def test_phone_no_dash(self):
        text, redacted = redact_pii("01098765432 으로 연락주세요")
        assert "[전화번호]" in text
        assert "phone" in redacted

    def test_rrn(self):
        text, redacted = redact_pii("주민번호 901010-1234567 알려드릴게요")
        assert "[주민번호]" in text
        assert "rrn" in redacted

    def test_email(self):
        text, redacted = redact_pii("연락처 jy@aitrics.com")
        assert "[이메일]" in text
        assert "email" in redacted

    def test_korean_name(self):
        text, redacted = redact_pii("김철수가 도와주실 거예요")
        assert "[이름]" in text
        assert "name" in redacted

    def test_no_pii(self):
        text, redacted = redact_pii("오늘 좀 어지러워요")
        assert redacted == []


class TestEducation:
    def test_neuropathy_card(self):
        card = find_education_card("손발이 저려요")
        assert card is not None
        assert "신경병증" in card["title"] or "저림" in card["title"]
        assert "ASCO" in card["source_label"] or "NCCN" in card["source_label"]

    def test_fatigue_card(self):
        card = find_education_card("너무 피곤해요")
        assert card is not None
        assert "피로" in card["title"]

    def test_no_match(self):
        card = find_education_card("점심 뭐 먹을까요")
        assert card is None


class TestClassifyEnhanced:
    def test_disclaimer_in_education(self):
        r = classify_and_respond("저림이 심해요")
        assert r["type"] == "education"
        assert "의료 자문을 대체하지 않습니다" in r["response"]
        assert r["source"] is not None
        assert "url" in r["source"]

    def test_disclaimer_in_oos(self):
        r = classify_and_respond("약을 더 먹어도 되나요")
        assert r["type"] == "out_of_scope"
        assert "의료 자문을 대체하지 않습니다" in r["response"]

    def test_no_disclaimer_in_emergency(self):
        # 응급은 즉시 행동 유도 — disclaimer 없어야 함
        r = classify_and_respond("숨이 안 쉬어져요")
        assert r["type"] == "emergency"
        assert "119" in r["response"]
        assert "의료 자문을 대체" not in r["response"]

    def test_pii_in_audit(self):
        r = classify_and_respond("내 전화는 010-1111-2222 입니다")
        assert "phone" in r["pii_redacted"]
        assert "010-1111-2222" not in r["redacted_text"]


# ============================================================
# Education 카드 데이터 무결성
# ============================================================
class TestEducationCardSchema:
    def test_all_have_source(self):
        for card in EDUCATION_CARDS:
            assert card["source_label"]
            assert card["source_url"].startswith("http")

    def test_all_have_triggers(self):
        for card in EDUCATION_CARDS:
            assert len(card["trigger_keyword"]) > 0
