"""채점 엔진 단위 테스트 — 결정론 검증."""
import pytest
from scoring import (
    score_pro_ctcae_item, score_pro_ctcae_composite,
    score_hads, score_hads_subscale,
    evaluate_mcid_hads, evaluate_mcid_pro_ctcae,
)


# ============================================================
# PRO-CTCAE
# ============================================================
class TestProCtcae:
    def test_score_item_basic(self):
        r = score_pro_ctcae_item("fatigue", "freq", 3)
        assert r["score"] == 3
        assert r["severity_grade"] == "severe"

    def test_score_out_of_range(self):
        with pytest.raises(ValueError):
            score_pro_ctcae_item("fatigue", "freq", 5)
        with pytest.raises(ValueError):
            score_pro_ctcae_item("fatigue", "freq", -1)

    def test_composite(self):
        items = [
            {"score": 1, "attribute": "freq"},
            {"score": 3, "attribute": "severity"},
            {"score": 2, "attribute": "interference"},
        ]
        r = score_pro_ctcae_composite(items)
        assert r["composite"] == 3       # max(severity, interference)
        assert r["n"] == 2

    def test_composite_no_relevant(self):
        items = [{"score": 4, "attribute": "freq"}]  # 빈도만
        r = score_pro_ctcae_composite(items)
        assert r["composite"] == 0


# ============================================================
# HADS
# ============================================================
class TestHads:
    def test_normal_case(self):
        # 모두 0점 — 정상
        responses = {f"A{i}": 0 for i in range(1, 8)}
        responses.update({f"D{i}": 0 for i in range(1, 8)})
        r = score_hads(responses)
        # A: 0+0+0+(3-0)+0+0+0 = 3 (정상)
        assert r["hads_a"]["value"] == 3.0
        assert r["hads_a"]["classification"] == "normal"
        # D: (3-0)+(3-0)+(3-0)+0+(3-0)+(3-0)+(3-0) = 18 → case
        assert r["hads_d"]["value"] == 18.0

    def test_borderline_anxiety(self):
        # A: 1+1+1+(3-2)+1+1+2 = 8 (경계)
        responses = {"A1": 1, "A2": 1, "A3": 1, "A4": 2,
                     "A5": 1, "A6": 1, "A7": 2}
        r = score_hads_subscale(responses, "A")
        assert r["value"] == 8.0
        assert r["classification"] == "borderline"

    def test_case_anxiety(self):
        # 모두 max
        responses = {f"A{i}": 3 for i in range(1, 8)}
        responses["A4"] = 0   # reverse → 3
        r = score_hads_subscale(responses, "A")
        # 3+3+3+(3-0)+3+3+3 = 21
        assert r["value"] == 21.0
        assert r["classification"] == "case"

    def test_missing(self):
        responses = {"A1": 2, "A2": 1}  # 부족
        r = score_hads_subscale(responses, "A")
        assert r["value"] is None
        assert r["classification"] == "missing"

    def test_seed_data_target(self):
        """시드 데이터 검증 — A=8, D=5 정확히."""
        # seed.py의 HADS_DAY7와 동일
        hads = {
            "A1": 1, "A2": 1, "A3": 1, "A4": 2,
            "A5": 1, "A6": 1, "A7": 2,
            "D1": 2, "D2": 2, "D3": 3, "D4": 0,
            "D5": 2, "D6": 2, "D7": 2,
        }
        r = score_hads(hads)
        assert r["hads_a"]["value"] == 8.0
        assert r["hads_a"]["classification"] == "borderline"
        assert r["hads_d"]["value"] == 5.0
        assert r["hads_d"]["classification"] == "normal"

    def test_determinism(self):
        """동일 입력 → 동일 출력 100%."""
        responses = {f"A{i}": (i % 4) for i in range(1, 8)}
        r1 = score_hads_subscale(responses, "A")
        r2 = score_hads_subscale(responses, "A")
        r3 = score_hads_subscale(responses, "A")
        assert r1 == r2 == r3


# ============================================================
# MCID
# ============================================================
class TestMCID:
    def test_hads_red(self):
        assert evaluate_mcid_hads(11, "HADS-A") == "red"
        assert evaluate_mcid_hads(15, "HADS-A") == "red"

    def test_hads_yellow(self):
        assert evaluate_mcid_hads(8, "HADS-A") == "yellow"
        assert evaluate_mcid_hads(10, "HADS-A") == "yellow"

    def test_hads_normal(self):
        assert evaluate_mcid_hads(7, "HADS-A") is None
        assert evaluate_mcid_hads(0, "HADS-A") is None

    def test_pro_ctcae_red_persistent(self):
        # 신경병증 2점이 3일 연속
        scores = [{"score": 3, "attribute": "severity"}]
        history = [2, 2, 3]
        flag = evaluate_mcid_pro_ctcae(scores, history)
        assert flag == "red"

    def test_pro_ctcae_yellow_today(self):
        # 오늘만 2점
        scores = [{"score": 2, "attribute": "severity"}]
        history = [0, 1]
        flag = evaluate_mcid_pro_ctcae(scores, history)
        assert flag == "yellow"

    def test_pro_ctcae_clear(self):
        scores = [{"score": 1, "attribute": "severity"}]
        history = [0, 0]
        assert evaluate_mcid_pro_ctcae(scores, history) is None
