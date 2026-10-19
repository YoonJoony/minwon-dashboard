"""계산 규칙 테스트 (데이터 없이 실행)."""
import pandas as pd
import pytest
from app import config  # noqa: F401  (engine 패키지 경로 등록)

from engine.dashboard import AsofData, matrix, quadrant, staffing


def test_quadrant_thresholds():
    assert quadrant(0.20, 1.5) == "집중관리"
    assert quadrant(0.20, 1.0) == "접수증가 주의"
    assert quadrant(0.0, 1.5) == "처리지연 주의"
    assert quadrant(0.0, 1.0) == "안정"
    assert quadrant(-0.20, 1.0) == "지원 가능"
    assert quadrant(-0.20, 1.5) == "처리지연 주의"


def _asof_data(flag_agency=None):
    asof = pd.Timestamp("2026-01-05")
    days = pd.date_range(asof, periods=7)
    preds = {"DSNY": 70.0, "DEP": 140.0, "DOT": 140.0, "DOB": 140.0, "DOHMH": 140.0, "DPR": 140.0, "DCWP": 140.0, "DHS": 140.0}
    fd = pd.DataFrame([(ag, d, "short", v / 7) for ag, v in preds.items() for d in days], columns=["agency", "date", "source", "pred"])
    iv = pd.DataFrame([(ag, "short", 1, 0.9, 1.1) for ag in preds], columns=["agency", "source", "block", "lo_ratio", "hi_ratio"])
    af = pd.DataFrame(columns=["agency", "flag", "level", "reason", "factor", "start", "end", "extra_per_day"])
    if flag_agency:
        af = pd.DataFrame([{"agency": flag_agency, "flag": "기상 특보", "level": 1, "reason": "대설", "factor": 3.1,
                            "start": asof, "end": asof + pd.Timedelta(days=6), "extra_per_day": 0.0}])
    st = pd.DataFrame([(ag, 12.0 if ag == "DSNY" else 16.0, 100.0, 100.0, 1.0, 0.0) for ag in preds],
                      columns=["agency", "recent_day", "backlog_open", "backlog_normal", "backlog_multiple", "instant_share"])
    return AsofData(asof, fd, iv, af, st), days


def test_support_and_flag_rules():
    a, days = _asof_data()
    m = matrix(a, days[0], days[-1]).set_index("agency")
    assert m.at["DSNY", "quadrant"] == "지원 가능"          # 70 ÷ (12 × 7) − 1 = −17%, 적체 1.0배
    assert m.at["DEP", "quadrant"] == "접수증가 주의"       # 140 ÷ (16 × 7) − 1 = +25%
    assert m.at["DEP", "x"] == pytest.approx(140 / (16 * 7) - 1)
    a2, _ = _asof_data(flag_agency="DSNY")
    m2 = matrix(a2, days[0], days[-1]).set_index("agency")
    assert m2.at["DSNY", "quadrant"] == "안정"               # 특보 영향 부서는 지원 후보에서 제외
    assert m2.at["DSNY", "hi"] == pytest.approx(70 * 3.1)


def test_staffing_matches_need_to_support():
    a, days = _asof_data()
    m = matrix(a, days[0], days[-1])
    r = staffing(m, days[0], days[-1], per_person_day=10)
    assert r["total_need"] > 0 and r["supports"]
    assert r["covered"] <= sum(s["slack"] for s in r["supports"]) + 1e-6
    assert r["workdays"] == 5
