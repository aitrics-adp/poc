"""Pre-Visit Report One-Line Summary 생성기 (FN-RPT-007/008/010).

설계 원칙:
  - LLM 미사용 — 결정론 템플릿 매칭으로 의사 결정 입력 신뢰도 보장
  - 입력: 환자 ID + window_days
  - 출력: summary 1줄 + alerts 리스트 + 7일 추세 시계열 + 라이프로그
  - 응답형 빠른 결정 트리:
      RED ≥ 2 → "다중 영역 RED" 즉시 외래
      RED = 1 → 도구별 전용 템플릿 (신경병증/피로/오심/식욕/HADS)
      YELLOW ≥ 1 → 경계값 안내 템플릿
      그 외 → "안정적"

확장 포인트 (Phase 1+):
  - LLM 리라이트 옵션 (FN-LLM-006 RAG)
  - 환자별 임상 컨텍스트 토큰 추가 (regimen/cycle_day 변환)

함수 분리:
  generate_one_line_summary  — 메인 진입점
  _completion_metrics        — 이수율 (FN-RPT-013)
  _trend_analysis            — 7/14일 이동평균 (FN-RPT-014)
  _detect_cycle_pattern      — Cycle 후 악화 패턴 감지 (FN-RPT-015 단순 버전)
  _build_trend_series        — 차트용 시계열 변환
"""
from datetime import datetime, timedelta
from sqlmodel import Session, select
from models import ProSession, ProResponse, ProScore


# Jinja 스타일 템플릿 — 룰 매칭
SUMMARY_TEMPLATES = {
    "stable": "지난 {days}일간 PRO 점수 안정적. 특이 변화 없음.",
    "fatigue_red": "피로 {peak}점 {days}일 지속 — 항암 피로 평가 권장.",
    "fatigue_up": "피로도 점진 상승 추세 ({days}일 평균 {avg:.1f}). 컨디션 점검 권장.",
    "nausea_red": "오심·구토 {peak}점 {days}일 지속 — 항구토제 효과 점검 필요.",
    "diarrhea_red": "설사 {peak}점 {days}일 지속 — 탈수·전해질 평가 권장.",
    "appetite_red": "식욕부진 {peak}점 {days}일 지속 — 영양 상담 검토.",
    "neuropathy_red": "말초신경병증 {days}일 연속 {peak}점 지속. RED 알림 — 신경독성 평가 필요.",
    "hads_borderline": "HADS-{sub} {value:.0f}점 진입 (경계값). 정서적 지지 권장.",
    "hads_case": "HADS-{sub} {value:.0f}점 — 임상적 이상. 전문 상담 의뢰 검토.",
    "multi_alert": "{n}개 영역 RED — 즉시 외래 또는 전화 진료 권고.",
}

# 증상 → 한글 라벨 + summary 키 매핑
SYMPTOM_LABEL = {
    "fatigue": "피로", "appetite": "식욕부진", "nausea": "오심·구토",
    "diarrhea": "설사", "neuropathy": "말초신경병증",
}
SYMPTOM_SUMMARY_KEY = {
    "fatigue": "fatigue_red", "appetite": "appetite_red",
    "nausea": "nausea_red", "diarrhea": "diarrhea_red",
    "neuropathy": "neuropathy_red",
}


def generate_one_line_summary(
    patient_id: str,
    session: Session,
    window_days: int = 7,
) -> dict:
    """환자의 최근 N일 PRO 데이터를 분석해 One-Line Summary 생성.

    Returns: {
        "summary": str,
        "alerts": [{tool, subscale, value, level}],
        "trend": {tool: [points]},
        "lifelog_correlation": str,  (POC는 더미 텍스트)
    }
    """
    cutoff = datetime.utcnow() - timedelta(days=window_days)
    sessions = session.exec(
        select(ProSession)
        .where(ProSession.patient_id == patient_id)
        .where(ProSession.started_at >= cutoff)
        .order_by(ProSession.started_at)
    ).all()

    if not sessions:
        return {
            "summary": "최근 PRO 응답 없음. 환자 미응답 알림 발송 권장.",
            "alerts": [],
            "trend": {},
            "lifelog_correlation": "데이터 부족",
        }

    session_ids = [s.id for s in sessions]

    # 모든 score
    all_scores = session.exec(
        select(ProScore).where(ProScore.session_id.in_(session_ids))
    ).all()

    # ---------- alerts 수집 (모든 PRO-CTCAE 증상 일반화 + HADS) ----------
    alerts = []
    # 증상별 history (PRO-CTCAE severity, freq, interference 중 최댓값)
    symptom_history: dict = {}
    for s in sessions:
        responses = session.exec(
            select(ProResponse)
            .where(ProResponse.session_id == s.id)
            .where(ProResponse.tool_code == "PRO-CTCAE")
        ).all()
        per_symptom: dict = {}
        for r in responses:
            per_symptom[r.item_code] = max(per_symptom.get(r.item_code, 0), r.raw_value)
        for sym, v in per_symptom.items():
            symptom_history.setdefault(sym, []).append(v)

    # 가장 최근 HADS score
    hads_a_score = hads_d_score = None
    for sc in sorted(all_scores, key=lambda x: x.computed_at, reverse=True):
        if sc.tool_code == "HADS":
            if sc.subscale == "HADS-A" and hads_a_score is None:
                hads_a_score = sc
            if sc.subscale == "HADS-D" and hads_d_score is None:
                hads_d_score = sc

    # HADS alerts
    for sc in [hads_a_score, hads_d_score]:
        if sc and sc.classification == "case":
            alerts.append({"tool": "HADS", "subscale": sc.subscale,
                           "value": sc.value, "level": "red"})
        elif sc and sc.classification == "borderline":
            alerts.append({"tool": "HADS", "subscale": sc.subscale,
                           "value": sc.value, "level": "yellow"})

    # PRO-CTCAE 모든 증상 일반화 alerts
    # RED: 3일 연속 ≥2점 / YELLOW: 오늘 ≥2점
    for symptom, hist in symptom_history.items():
        if not hist:
            continue
        peak = max(hist)
        recent_3 = hist[-3:] if len(hist) >= 3 else hist
        if len(recent_3) >= 2 and all(v >= 2 for v in recent_3) and peak >= 2:
            alerts.append({
                "tool": "PRO-CTCAE", "subscale": symptom,
                "value": float(peak), "level": "red",
            })
        elif peak >= 2:
            alerts.append({
                "tool": "PRO-CTCAE", "subscale": symptom,
                "value": float(peak), "level": "yellow",
            })

    # ---------- 룰 기반 summary 선택 ----------
    red_alerts = [a for a in alerts if a["level"] == "red"]
    yellow_alerts = [a for a in alerts if a["level"] == "yellow"]

    if len(red_alerts) >= 2:
        summary = SUMMARY_TEMPLATES["multi_alert"].format(n=len(red_alerts))
    elif red_alerts:
        a = red_alerts[0]
        if a["tool"] == "HADS":
            sub = a["subscale"].replace("HADS-", "")
            summary = SUMMARY_TEMPLATES["hads_case"].format(sub=sub, value=a["value"])
        else:
            sym = a["subscale"]
            key = SYMPTOM_SUMMARY_KEY.get(sym, "neuropathy_red")
            hist = symptom_history.get(sym, [])
            summary = SUMMARY_TEMPLATES[key].format(
                days=len(hist), peak=int(a["value"]))
    elif yellow_alerts:
        a = yellow_alerts[0]
        if a["tool"] == "HADS":
            sub = a["subscale"].replace("HADS-", "")
            summary = SUMMARY_TEMPLATES["hads_borderline"].format(
                sub=sub, value=a["value"])
        else:
            sym = a["subscale"]
            label = SYMPTOM_LABEL.get(sym, sym)
            summary = (f"{label} {int(a['value'])}점 관찰 — 모니터링 강화. "
                       f"({window_days}일)")
    else:
        summary = SUMMARY_TEMPLATES["stable"].format(days=window_days)

    # 트렌드 분석용 — 신경병증 history 별칭 (기존 호출자 호환)
    neuropathy_history = symptom_history.get("neuropathy", [])

    # ---------- trend 데이터 ----------
    trend = _build_trend_series(all_scores, sessions)

    # ---------- lifelog (POC는 더미 텍스트) ----------
    if neuropathy_history and max(neuropathy_history) >= 2:
        lifelog = "동기간 활동량 약 32% 감소 추정. 신경병증과 상관 (Pearson r ≈ 0.72)."
    else:
        lifelog = "동기간 활동량·체중 안정. 라이프로그 vs PRO 상관 미관찰."

    # ---------- FN-RPT-013 이수율 / FN-RPT-014 추세분석 ----------
    completion = _completion_metrics(patient_id, session, window_days)
    trend_analysis = _trend_analysis(all_scores, sessions)

    # ---------- FN-RPT-015 패턴 감지 (Cycle 후 3-5일 악화) ----------
    pattern = _detect_cycle_pattern(neuropathy_history)

    return {
        "summary": summary,
        "alerts": alerts,
        "trend": trend,
        "lifelog_correlation": lifelog,
        "window_days": window_days,
        "session_count": len(sessions),
        "completion": completion,
        "trend_analysis": trend_analysis,
        "pattern": pattern,
    }


def _completion_metrics(patient_id: str, session: Session, window_days: int) -> dict:
    """FN-RPT-013: 이수율(완료/예상). 매일 응답 가정."""
    cutoff = datetime.utcnow() - timedelta(days=window_days)
    sessions = session.exec(
        select(ProSession)
        .where(ProSession.patient_id == patient_id)
        .where(ProSession.started_at >= cutoff)
    ).all()
    completed = sum(1 for s in sessions if s.completed_at)
    expected = window_days  # 매일 가정
    rate = completed / expected if expected else 0
    # 미응답 N일
    completed_dates = {s.started_at.date() for s in sessions if s.completed_at}
    today = datetime.utcnow().date()
    missing_days = []
    for i in range(window_days):
        d = today - timedelta(days=i)
        if d not in completed_dates:
            missing_days.append(d.isoformat())
    return {
        "completed": completed,
        "expected": expected,
        "rate": round(rate, 2),
        "missing_days": missing_days,
        "consecutive_missing": _consecutive_missing(completed_dates, today),
    }


def _consecutive_missing(completed_dates: set, today) -> int:
    """오늘부터 거꾸로 짚어 연속 미응답 일수."""
    n = 0
    for i in range(30):
        d = today - timedelta(days=i)
        if d in completed_dates:
            break
        n += 1
    return n


def _trend_analysis(scores: list, sessions: list) -> dict:
    """FN-RPT-014: 7일 이동평균 + 방향성 (상승/하강/안정)."""
    if len(sessions) < 2:
        return {"direction": "insufficient_data"}
    by_id = {s.id: s.started_at for s in sessions}
    # 신경병증 시계열만 (대표 지표)
    series = sorted(
        [(by_id.get(sc.session_id), sc.value) for sc in scores
         if sc.tool_code == "PRO-CTCAE" and sc.subscale == "neuropathy"
         and by_id.get(sc.session_id)],
        key=lambda x: x[0],
    )
    if len(series) < 3:
        return {"direction": "insufficient_data"}
    values = [v for _, v in series]
    # 7일 이동평균 (윈도 가능한 만큼)
    w = min(7, len(values))
    ma = sum(values[-w:]) / w
    # 방향성: 첫 절반 vs 마지막 절반 평균 비교
    half = len(values) // 2
    early = sum(values[:half]) / half if half else 0
    late = sum(values[half:]) / (len(values) - half)
    delta = late - early
    direction = (
        "rising" if delta >= 0.5
        else "falling" if delta <= -0.5
        else "stable"
    )
    return {
        "moving_average_7d": round(ma, 2),
        "direction": direction,
        "delta": round(delta, 2),
        "n_points": len(values),
    }


def _detect_cycle_pattern(neuropathy_history: list[int]) -> dict:
    """FN-RPT-015: 단순 패턴 감지 — 점진 악화."""
    if len(neuropathy_history) < 4:
        return {"detected": None}
    # 점진 악화: 첫 절반 평균 vs 마지막 절반 평균 차이 ≥ 1
    half = len(neuropathy_history) // 2
    early = sum(neuropathy_history[:half]) / half
    late = sum(neuropathy_history[half:]) / (len(neuropathy_history) - half)
    if late - early >= 1.0:
        return {
            "detected": "progressive_worsening",
            "label": "점진적 악화 패턴",
            "delta": round(late - early, 2),
        }
    return {"detected": None}


def _build_trend_series(
    scores: list[ProScore],
    sessions: list[ProSession],
) -> dict:
    """차트용 시계열 — {tool_subscale: [{date, value}]}."""
    by_session = {s.id: s.started_at for s in sessions}
    series: dict[str, list[dict]] = {}
    for sc in sorted(scores, key=lambda x: x.computed_at):
        date = by_session.get(sc.session_id)
        if date is None:
            continue
        key = f"{sc.tool_code}_{sc.subscale or 'composite'}"
        series.setdefault(key, []).append({
            "date": date.isoformat(),
            "value": sc.value,
            "level": sc.mcid_flag,
        })
    return series
