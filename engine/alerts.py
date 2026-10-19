"""기상 특보 — 미국 기상청(NWS 뉴욕 지청) 기준 (검증 ⑩, analysis/verify_nws_alerts.py와 같은 정의).

- 폭염: 주의보 = 열지수 95°F 이상 2일 연속 또는 100~104°F / 경보 = 105°F 이상 2시간 연속
- 강풍: 주의보 = 지속 풍속 30mph 이상 또는 돌풍 46mph 이상 / 경보 = 40mph 이상 또는 돌풍 58mph 이상
- 대설: 주의보 = 12시간 3인치 / 경보 = 12시간 6인치 또는 24시간 8인치
- 호우: NWS 고정 기준이 없어 1시간 강수 0.5인치(주의)·1인치(강함)로 대신 (참고 정보)
기준일 + k일의 날씨는 k일 전 발표 예보(engine.config.LEAD), 기준일 전 이틀은 관측을 씁니다.
"""
import numpy as np
import pandas as pd

from engine.config import AGENCIES, ALERT_INFO, LEAD, LINKS, WIDEN, WIDEN_DEFAULT
from engine.data import forecast_lead, hourly_obs

D = pd.Timedelta


def heat_index(t: pd.Series, rh: pd.Series) -> pd.Series:
    """NWS 열지수 (°F). Rothfusz 회귀식과 NWS 보정."""
    simple = 0.5 * (t + 61.0 + (t - 68.0) * 1.2 + rh * 0.094)
    full = (-42.379 + 2.04901523 * t + 10.14333127 * rh - 0.22475541 * t * rh - 0.00683783 * t**2
            - 0.05481717 * rh**2 + 0.00122874 * t**2 * rh + 0.00085282 * t * rh**2 - 0.00000199 * t**2 * rh**2)
    adj_dry = ((13 - rh) / 4) * np.sqrt(((17 - (t - 95).abs()) / 17).clip(lower=0))
    full = full - adj_dry.where((rh < 13) & (t >= 80) & (t <= 112), 0)
    adj_wet = ((rh - 85) / 10) * ((87 - t) / 5)
    full = full + adj_wet.where((rh > 85) & (t >= 80) & (t <= 87), 0)
    return full.where((simple + t) / 2 >= 80, simple)


def daily_levels(h: pd.DataFrame) -> pd.DataFrame:
    """시간별 값(t °F, rh %, prcp in, snow in, wind mph, gust mph) → 날짜별 특보 단계(0·1·2)와 대표값."""
    h = h.set_index("time").sort_index()
    hi = heat_index(h.t, h.rh)
    day = h.index.normalize()
    hi_max = hi.groupby(day).max()
    hot2h = (hi >= 105).astype(int).rolling(2).sum().eq(2).groupby(day).any()
    run95 = hi_max >= 95
    two_day = run95 & (run95.shift(1, fill_value=False) | run95.shift(-1, fill_value=False))
    heat = pd.Series(0, index=hi_max.index)
    heat[two_day | (hi_max >= 100)] = 1
    heat[hot2h] = 2

    wind_h = h.wind.groupby(day).max()
    gust_h = h.gust.groupby(day).max()
    wind = pd.Series(0, index=wind_h.index)
    wind[(wind_h >= 30) | (gust_h >= 46)] = 1
    wind[(wind_h >= 40) | (gust_h >= 58)] = 2

    s12 = h.snow.rolling(12, min_periods=12).sum().groupby(day).max()
    s24 = h.snow.rolling(24, min_periods=24).sum().groupby(day).max()
    snow = pd.Series(0, index=s12.index)
    snow[s12 >= 3] = 1
    snow[(s12 >= 6) | (s24 >= 8)] = 2

    p1 = h.prcp.groupby(day).max()
    rain = pd.Series(0, index=p1.index)
    rain[p1 >= 0.5] = 1
    rain[p1 >= 1.0] = 2
    valid = h[["t", "rh", "prcp", "snow", "wind", "gust"]].notna().groupby(day).mean()
    return pd.DataFrame({
        "heat": heat, "wind": wind, "snow": snow, "rain": rain,
        "hi_max": hi_max, "gust_max": gust_h, "wind_max": wind_h, "snow12_max": s12, "snow24_max": s24, "prcp1h_max": p1,
        "valid_heat": valid[["t", "rh"]].min(axis=1) > 0.9, "valid_wind": valid[["wind", "gust"]].min(axis=1) > 0.9,
        "valid_snow": valid.snow > 0.9, "valid_rain": valid.prcp > 0.9,
    })


def all_levels() -> tuple[pd.DataFrame, dict[int, pd.DataFrame]]:
    """관측과 예보 시점별(1·2·3·5·7일 전) 날짜별 특보 단계."""
    obs = daily_levels(hourly_obs())
    fc = {lead: daily_levels(forecast_lead(lead)) for lead in sorted(set(LEAD.values()))}
    return obs, fc


def _value_label(kind: str, r: pd.Series) -> str:
    if kind == "heat":
        return f"열지수 최고 {r.hi_max:.0f}°F ({(r.hi_max - 32) / 1.8:.0f}°C)"
    if kind == "snow":
        return f"12시간 적설 최대 {r.snow12_max * 2.54:.0f}cm"
    if kind == "wind":
        return f"돌풍 최대 {r.gust_max * 1.609:.0f}km/h"
    return f"1시간 강수 최대 {r.prcp1h_max * 25.4:.0f}mm"


def alerts_for(asof: pd.Timestamp, obs: pd.DataFrame, fc: dict[int, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """기준일에 볼 수 있는 특보 목록(향후 7일 예보 + 직전 이틀 관측)과 특보 영향 부서."""
    rows = []
    for k in range(-2, 7):
        d = asof + D(days=k)
        if k < 0:
            src, lead, lv = "관측", 0, obs
        else:
            src, lead, lv = "예보", LEAD[k], fc[LEAD[k]]
        if d not in lv.index:
            continue
        r = lv.loc[d]
        for kind in ALERT_INFO:
            level = r[kind]
            if not r[f"valid_{kind}"] or pd.isna(level) or level < 1:
                continue
            rows.append({"date": d, "offset": k, "type": kind, "level": int(level), "source": src, "lead_days": lead,
                         "value": _value_label(kind, r)})
    alerts = pd.DataFrame(rows, columns=["date", "offset", "type", "level", "source", "lead_days", "value"])

    # 특보 영향 부서: 특보일 + 영향일(LINKS)이 기간(기준일~+6일) 안에 걸리면 표시 (verify_alert_uplift.alert_flags와 같음)
    hit: dict[str, dict] = {}
    for kind, issue, dept, (lo, hi) in LINKS:
        sub = alerts[alerts.type == kind]
        for a in sub.itertuples():
            if any(0 <= a.offset + j <= 6 for j in range(lo, hi + 1)):
                h = hit.setdefault(dept, {"level": 0, "kinds": set(), "issues": set()})
                h["level"] = max(h["level"], a.level)
                h["kinds"].add(kind)
                h["issues"].add(issue)
    affected = pd.DataFrame([
        {"agency": ag, "flag": "기상 특보", "level": v["level"],
         "reason": ", ".join(ALERT_INFO[k]["label"] for k in sorted(v["kinds"])) + " → " + ", ".join(sorted(v["issues"])),
         "factor": WIDEN.get(ag, WIDEN_DEFAULT), "start": asof, "end": asof + D(days=6), "extra_per_day": 0.0}
        for ag, v in hit.items() if ag in AGENCIES])
    return alerts, affected
