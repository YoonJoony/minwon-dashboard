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


def test_weather_strip_uses_forecasts_known_at_asof():
    w = client.get("/api/weather/strip", params={"asof": "2025-06-20"}).json()
    days = w["days"]
    assert len(days) == 8 and days[0]["label"] == "오늘" and days[0]["lead"] == 1
    assert [d["lead"] for d in days[1:]] == [1, 2, 3, 4, 5, 6, 7]
    assert [d["mode"] for d in days] == ["예보"] * 4 + ["참고"] * 4
    d22 = days[2]
    labels = {(a["source"], a["label"]) for a in d22["alerts"]}
    assert ("예보", "폭염경보 수준") in labels
    assert any(src == "NWS" for src, _ in labels)          # 6/20 오후 발표된 극한 폭염 예비특보
    for d in days:                                        # 기준일(6/20) 뒤에 발표된 NWS 특보는 없어야 함
        for a in d["alerts"]:
            if a["source"] == "NWS":
                month, day = (int(x) for x in a["issued"].split()[0].split("/"))
                assert (month, day) <= (6, 20)


def test_weather_day_history_matches_verification_doc():
    w = client.get("/api/weather/day", params={"asof": "2025-06-20", "date": "2025-06-22"}).json()
    assert [t["kind"] for t in w["tabs"]] == ["heat"]                # 그날 특보가 있는 종류만
    heat = w["tabs"][0]
    assert len(heat["years"]) == 7
    y2024 = heat["years"][0]
    assert y2024["year"] == 2024
    e = y2024["event"]
    hyd = e["issues"][0]
    # docs/기상예보_기능_검증.md 6장 예시와 같은 값
    assert (e["start"], e["win_start"], e["win_end"]) == ("2024-06-21", "2024-06-20", "2024-06-25")
    assert (hyd["received"], round(hyd["excess"]), hyd["processed"], hyd["open_end"], hyd["open_7"]) == (1459, 1300, 1300, 159, 12)


def test_weather_day_rejects_out_of_strip_and_has_no_history_without_alerts():
    r = client.get("/api/weather/day", params={"asof": "2026-10-12", "date": "2026-10-25"})
    assert r.status_code == 400 and "8일" in r.json()["detail"]
    w = client.get("/api/weather/day", params={"asof": "2026-10-12", "date": "2026-10-14"}).json()
    assert w["day"]["alerts"] == [] and w["tabs"] == []              # 특보 없는 날은 과거 7년 표 없음


def test_weather_history_uses_only_events_before_asof():
    w = client.get("/api/weather/day", params={"asof": "2024-02-12", "date": "2024-02-13"}).json()
    assert [t["kind"] for t in w["tabs"]] == ["snow"]                # 2024-02-13 대설 수준 예보
    events = [y["event"] for y in w["tabs"][0]["years"] if y["event"]]
    assert events and all(e["win_end"] < "2024-02-12" for e in events)
