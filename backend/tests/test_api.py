"""API 테스트. 사전 계산 결과(data/artifacts)가 있어야 하며, 없으면 건너뜁니다."""
from collections import Counter

import pytest
from app.config import ARTIFACTS
from app.main import app
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(not (ARTIFACTS / "manifest.json").exists(), reason="사전 계산 결과 없음")
client = TestClient(app)
S1 = {"asof": "2025-06-20", "start": "2025-06-20", "end": "2025-06-26"}
S2 = {"asof": "2026-02-20", "start": "2026-02-20", "end": "2026-02-26"}


def test_meta_lists_asofs_scenarios_and_agencies():
    m = client.get("/api/meta").json()
    assert m["app_name"] == "스마트 민원케어"
    assert len(m["agencies"]) == 8
    assert m["latest"] in m["asofs"]
    assert {s["id"] for s in m["scenarios"]} >= {"S1", "S2", "S3", "S4"}
    assert m["thresholds"] == {"x": 0.1, "y": 1.3, "support_x": -0.1}


def test_invalid_period_is_rejected_in_korean():
    r = client.get("/api/forecast", params={"asof": "2026-10-12", "end": "2027-02-01"})
    assert r.status_code == 400 and "최대" in r.json()["detail"]
    r = client.get("/api/forecast", params={"asof": "2026-10-13"})
    assert r.status_code == 400 and "기준일" in r.json()["detail"]


def test_heatwave_scenario_shows_alert_and_flag():
    issues = client.get("/api/issues", params=S1).json()
    assert any(a["type"] == "heat" and a["level"] == 2 for a in issues["alerts"])
    assert issues["cards"][0]["kind"] == "alert"
    mat = {i["agency"]: i for i in client.get("/api/matrix", params=S1).json()["items"]}
    assert mat["DEP"]["flag"] == "기상 특보"
    assert mat["DEP"]["hi"] >= mat["DEP"]["pred"] * 1.6 - 1


def test_blizzard_keeps_sanitation_out_of_support():
    mat = {i["agency"]: i for i in client.get("/api/matrix", params=S2).json()["items"]}
    assert mat["DSNY"]["flag"] == "기상 특보"
    assert mat["DSNY"]["quadrant"] != "지원 가능"
    st = client.get("/api/staffing", params=S2).json()
    assert all(s["agency"] != "DSNY" for s in st["supports"])


def test_forecast_totals_and_series_are_consistent():
    f = client.get("/api/forecast", params=S1).json()
    assert f["granularity"] == "day"
    assert abs(sum(a["pred"] for a in f["by_agency"]) - f["total"]["pred"]) < 1e-6
    fc = [p for p in f["series"] if p["kind"] == "forecast"]
    assert len(fc) == 7 and abs(sum(p["pred"] for p in fc) - f["total"]["pred"]) < 1
    assert f["total"]["actual"] is not None          # 과거 기준일은 실제값이 있음
    latest = client.get("/api/forecast", params={"asof": "2026-10-12"}).json()
    assert latest["total"]["actual"] is None         # 최신 기준일 이후는 실제값 없음


def test_summary_and_risk_list():
    s = client.get("/api/summary", params={**S1, "agency": "DEP"}).json()
    assert s["kpis"]["alert_count"] >= 1 and s["kpis"]["agency_quadrant"]
    r = client.get("/api/risk-list", params={"asof": "2026-10-12", "agency": "DCWP"}).json()
    assert all(i["method"] == "elapsed" and i["prob"] is None for i in r["items"])
    r = client.get("/api/risk-list", params={"asof": "2026-10-12", "agency": "DOT"}).json()
    probs = [i["prob"] for i in r["items"]]
    assert probs == sorted(probs, reverse=True)
    # 전체 보기: 부서마다 고르게 (limit 15 → 부서당 최대 2건)
    r = client.get("/api/risk-list", params={"asof": "2026-10-12"}).json()
    per_agency = Counter(i["agency"] for i in r["items"])
    assert len(per_agency) >= 6 and max(per_agency.values()) <= 2


def test_staffing_people_follow_assumption():
    a = client.get("/api/staffing", params={**S1, "per_person_day": 10}).json()
    b = client.get("/api/staffing", params={**S1, "per_person_day": 20}).json()
    assert a["total_need"] == pytest.approx(b["total_need"])
    assert a["total_people"] == pytest.approx(b["total_people"] * 2)
