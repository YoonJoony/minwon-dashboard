"""10년치 검증 ⑦: 미국 기상청(NWS 뉴욕 지청 OKX) 특보 기준으로 본 기상 경보와 민원 급증.

NWS OKX 기준 (https://www.weather.gov/okx/wwa_definitions, 2026-10-19 확인)
- 폭염: 주의보(Heat Advisory) 열지수 95°F 이상 2일 연속 또는 100~104°F / 경보(Extreme Heat Warning) 105°F 이상 2시간 연속
- 강풍: 주의보(Wind Advisory) 지속 풍속 30~39mph 1시간 이상 또는 돌풍 46~57mph / 경보(High Wind Warning) 40mph 이상 또는 돌풍 58mph 이상
- 대설: 주의보(Winter Weather Advisory) 12시간 3인치 / 경보(Winter Storm Warning) 12시간 6인치 또는 24시간 8인치
- 호우: NWS는 고정 강수 기준이 없음(레이더·홍수 상황 기반) → 1시간 강수 강도로 대신 확인

관측(2016-01 ~ 2026-10)과 실제 예보(1·3·7일 전 발표분, 값이 있는 기간만)로 각각 계산합니다.
민원 급증 = 그날 관련 이슈 민원이 직전 28일 중앙값의 2배 이상이고 20건 이상.

실행: uv run python analysis/verify_nws_alerts.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "data/raw/weather"


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
    """시간별 값(t, rh, prcp, snow, wind, gust) → 날짜별 NWS 특보 단계 (0 없음, 1 주의보, 2 경보)."""
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
    rain = pd.Series(0, index=p1.index)          # 대체 지표: 1시간 강수 0.5인치(12.7mm) / 1인치(25.4mm)
    rain[p1 >= 0.5] = 1
    rain[p1 >= 1.0] = 2
    valid = h[["t", "rh", "prcp", "snow", "wind", "gust"]].notna().groupby(day).mean()
    return pd.DataFrame({"heat": heat, "wind": wind, "snow": snow, "rain": rain, "hi_max": hi_max,
                         "valid_heat": valid[["t", "rh"]].min(axis=1) > 0.9, "valid_wind": valid[["wind", "gust"]].min(axis=1) > 0.9,
                         "valid_snow": valid.snow > 0.9, "valid_rain": valid.prcp > 0.9})


RULES = [("heat", "폭염·소화전", (0, 1), "폭염 (열지수)"), ("heat", "수돗물", (0, 1), "폭염 → 수돗물"),
         ("wind", "강풍·수목", (0, 1), "강풍"), ("snow", "결빙·제설", (1, 2), "대설 (1~2일 뒤)"),
         ("rain", "폭우·침수", (0, 1), "호우 (1시간 강수, 대체 지표)")]


def main() -> None:
    obs = pd.read_parquet(W / "openmeteo_bronx_hourly_obs.parquet").rename(columns={
        "temperature_2m": "t", "relative_humidity_2m": "rh", "precipitation": "prcp", "snowfall": "snow",
        "wind_speed_10m": "wind", "wind_gusts_10m": "gust"})
    fc = pd.read_parquet(W / "openmeteo_bronx_hourly_forecast.parquet")
    iss = pd.read_csv(ROOT / "data/processed/daily_issue_weather.csv", parse_dates=["date"]).pivot(
        index="date", columns="issue", values="count")
    O = daily_levels(obs)
    days = pd.date_range("2016-02-01", "2026-10-09")
    O = O.reindex(days)

    def surge_after(issue, lo, hi):
        s = iss[issue]
        surge = (s >= 2 * s.rolling(28).median().shift(1).clip(lower=1)) & (s >= 20)
        return pd.concat([surge.shift(-k) for k in range(lo, hi + 1)], axis=1).any(axis=1).reindex(days)

    print("=== 관측 기준 (2016-02 ~ 2026-10): NWS 특보 기준일 수와 이후 관련 민원 급증 비율")
    rows = []
    for key, issue, (lo, hi), name in RULES:
        hit = surge_after(issue, lo, hi)
        for lv, lvn in ((1, "주의보 이상"), (2, "경보")):
            ev = O[key] >= lv
            rows.append({"기준": name, "단계": lvn, "일수": int(ev.sum()), "민원 급증 적중": hit[ev].mean()})
    R = pd.DataFrame(rows)
    print(R.to_string(index=False, formatters={"민원 급증 적중": "{:.0%}".format}))
    print("  참고 - 이전 임시 기준: 최고기온 ≥ 32°C 68%(174일), ≥ 34°C 81%(59일)")

    print("\n=== 실제 예보 기준: 예보가 NWS 특보를 미리 잡은 비율 / 예보 특보 후 민원 급증 비율")
    frows = []
    for lead in (1, 3, 7):
        f = fc[["time"] + [c for c in fc.columns if c.endswith(f"_previous_day{lead}")]].copy()
        f.columns = ["time", "t", "rh", "prcp", "snow", "wind", "gust"]
        F = daily_levels(f).reindex(days)
        for key, issue, (lo, hi), name in RULES:
            if issue == "수돗물":
                continue
            hit = surge_after(issue, lo, hi)
            ok = F[f"valid_{key}"].fillna(False).astype(bool)
            for lv, lvn in ((1, "주의보 이상"), (2, "경보")):
                ob = (O[key] >= lv) & ok
                fl = (F[key] >= lv) & ok
                frows.append({"기준": name, "단계": lvn, "예보": f"{lead}일 전", "평가 기간": f"{ok[ok].index.min():%Y-%m}~",
                              "실제 발생일": int(ob.sum()), "예보 포착": (fl & ob).sum() / max(ob.sum(), 1),
                              "예보 특보일": int(fl.sum()), "민원 급증 적중": hit[fl].mean()})
    FR = pd.DataFrame(frows)
    FR.to_csv(ROOT / "analysis/results/nws_forecast_alerts.csv", index=False)
    R.to_csv(ROOT / "analysis/results/nws_observed_alerts.csv", index=False)
    piv = FR.pivot_table(index=["기준", "단계", "평가 기간", "실제 발생일"], columns="예보",
                         values=["예보 포착", "민원 급증 적중"], aggfunc="first")
    print(piv.map(lambda x: "-" if pd.isna(x) else f"{x:.0%}").to_string())


if __name__ == "__main__":
    main()
