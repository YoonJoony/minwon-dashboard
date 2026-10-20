"""7일 기상 예보 띠 검증 — 기준일에 볼 수 있던 예보가 실제 날씨·실제 발표된 NWS 특보와 얼마나 맞았나.

띠의 날짜별 예보: 오늘(기준일)은 전날 발표(1일 전) 예보, +k일은 기준일에 발표된 k일 전 예보 (k = 1~7).
→ 날짜 차이 k별 정확도 = 'k일 전 예보'의 정확도. 평가: 습도·강수·적설 예보가 모두 있는 2024-02 ~ 2026-10.

1. 기온·강수·적설: 최고·최저 기온 오차, 비·눈 온 날 맞힘
2. 날씨 아이콘: 하루 대표 날씨(맑음·구름많음·흐림·비·눈·뇌우)가 실제와 같은 비율 — 두 가지 방식 비교
3. 특보 수준: 예보로 판정한 특보 수준 vs 관측으로 판정한 특보 수준
4. 실제 발표된 NWS 특보(IEM 보관, 브롱크스 NYZ073·NYC005)와 비교: 관측 판정 / 예보 판정
5. 예시 띠: 기준일 2025-06-20, 2026-02-20, 2026-10-12

입력: data/raw/weather/openmeteo_bronx_hourly_{obs,forecast}.parquet (pipelines/fetch_openmeteo_hourly.py),
      data/raw/nws/nws_alerts_bronx.csv (pipelines/fetch_nws_alerts.py)
실행: uv run python analysis/verify_forecast_strip.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import verify_nws_alerts as vn

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "data/raw/weather"
OUT = ROOT / "analysis/results"
VARS = ["temperature_2m", "relative_humidity_2m", "precipitation", "snowfall", "wind_speed_10m", "wind_gusts_10m",
        "weather_code", "cloud_cover"]
SHORT = ["t", "rh", "prcp", "snow", "wind", "gust", "code", "cloud"]
EVAL = ("2024-02-01", "2026-10-11")
NAME = {"heat": "폭염", "wind": "강풍", "snow": "대설", "rain": "호우"}
# 실제 발표 특보 → 우리 판정 종류·단계 (Y 주의보 = 1, W 경보 = 2)
NWS = {("HT", "Y"): ("heat", 1), ("EH", "W"): ("heat", 2), ("XH", "W"): ("heat", 2),
       ("WI", "Y"): ("wind", 1), ("HW", "W"): ("wind", 2),
       ("WW", "Y"): ("snow", 1), ("WS", "W"): ("snow", 2), ("BZ", "W"): ("snow", 2),
       ("FA", "Y"): ("rain", 1), ("FF", "W"): ("rain", 2)}


def hourly(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    h = df[["time"] + cols].copy()
    h.columns = ["time"] + SHORT
    return h


def daily(h: pd.DataFrame) -> pd.DataFrame:
    """시간별 → 날짜별 요약 (미국 단위 → °C, mm, cm)."""
    g = h.set_index("time").sort_index()
    day = g.index.normalize()
    daytime = g[(g.index.hour >= 7) & (g.index.hour <= 19)]
    return pd.DataFrame({
        "tmax": (g.t.groupby(day).max() - 32) * 5 / 9,
        "tmin": (g.t.groupby(day).min() - 32) * 5 / 9,
        "prcp": g.prcp.groupby(day).sum(min_count=20) * 25.4,
        "snow": g.snow.groupby(day).sum(min_count=20) * 2.54,
        "gust": g.gust.groupby(day).max() * 1.609,
        "code_max": g.code.groupby(day).max(),
        "cloud_day": daytime.cloud.groupby(daytime.index.normalize()).mean(),
        "thunder": g.code.ge(95).groupby(day).any(),
    })


def icon_a(d: pd.DataFrame) -> pd.Series:
    """방식 A: 하루 중 가장 심한 날씨 코드 (Open-Meteo 일별 날씨 코드와 같은 방식)."""
    c = d.code_max
    return pd.Series(np.select([c >= 95, c.between(71, 77) | c.between(85, 86), c.between(51, 67) | c.between(80, 82),
                                c.isin([45, 48]), c == 3, c == 2], ["뇌우", "눈", "비", "안개", "흐림", "구름많음"], "맑음"),
                     index=d.index).where(c.notna())


def icon_b(d: pd.DataFrame) -> pd.Series:
    """방식 B (국내 예보 방식에 가깝게): 비·눈은 하루 양으로, 아니면 낮 시간 평균 전운량으로."""
    out = np.select([d.thunder & (d.prcp >= 1), d.snow >= 1, d.prcp >= 1, d.cloud_day >= 80, d.cloud_day >= 40],
                    ["뇌우", "눈", "비", "흐림", "구름많음"], "맑음")
    return pd.Series(out, index=d.index).where(d.cloud_day.notna() & d.prcp.notna())


def official(alerts: pd.DataFrame, days: pd.DatetimeIndex) -> pd.DataFrame:
    """날짜별 실제 발표된 NWS 특보 단계 (그날 뉴욕 시각으로 하루라도 걸치면 그날 발표된 것으로 봄)."""
    lv = pd.DataFrame(0, index=days, columns=list(NAME))
    for r in alerts.itertuples():
        key = NWS.get((r.phenomena, r.significance))
        if key is None:
            continue
        a = pd.Timestamp(r.iso_issued).tz_convert("America/New_York").tz_localize(None).normalize()
        b = pd.Timestamp(r.iso_expired).tz_convert("America/New_York").tz_localize(None)
        if b <= a:
            continue
        b = (b - pd.Timedelta(minutes=1)).normalize()
        for d in pd.date_range(a, b):
            if d in lv.index:
                lv.at[d, key[0]] = max(lv.at[d, key[0]], key[1])
    return lv


def main() -> None:
    obs = pd.read_parquet(W / "openmeteo_bronx_hourly_obs.parquet")
    fc = pd.read_parquet(W / "openmeteo_bronx_hourly_forecast.parquet")
    days = pd.date_range(*EVAL)
    O = daily(hourly(obs, VARS)).reindex(days)
    O_lv = vn.daily_levels(hourly(obs, VARS).iloc[:, :7].rename(columns={"code": "_"})).reindex(days)
    alerts = pd.read_csv(ROOT / "data/raw/nws/nws_alerts_bronx.csv")
    N_all = official(alerts, pd.date_range("2016-02-01", "2026-10-11"))
    N = N_all.reindex(days)

    print("=== 1·2. 날짜 차이별 예보 정확도 (2024-02 ~ 2026-10)")
    rows, F_lv = [], {}
    for k in range(1, 8):
        F_h = hourly(fc, [f"{v}_previous_day{k}" for v in VARS])
        F = daily(F_h).reindex(days)
        F_lv[k] = vn.daily_levels(F_h.iloc[:, :7].rename(columns={"code": "_"})).reindex(days)
        ok = F.tmax.notna() & O.tmax.notna()
        rain_o, rain_f = O.prcp >= 1, F.prcp >= 1
        snow_o, snow_f = O.snow >= 1, F.snow >= 1
        ia_o, ia_f, ib_o, ib_f = icon_a(O), icon_a(F), icon_b(O), icon_b(F)
        okb = ib_o.notna() & ib_f.notna()
        oka = ia_o.notna() & ia_f.notna()
        rows.append({"예보": f"{k}일 전", "띠 날짜": "오늘·+1일" if k == 1 else f"+{k}일",
                     "최고기온 오차(°C)": (F.tmax - O.tmax)[ok].abs().mean(), "최저기온 오차(°C)": (F.tmin - O.tmin)[ok].abs().mean(),
                     "비 온 날 맞힘": (rain_f & rain_o).sum() / rain_o.sum(), "비 예보가 맞은 비율": (rain_f & rain_o).sum() / rain_f.sum(),
                     "눈 온 날 맞힘": (snow_f & snow_o).sum() / max(snow_o.sum(), 1),
                     "아이콘 일치 A(가장 심한 코드)": (ia_o == ia_f)[oka].mean(), "아이콘 일치 B(양·전운량)": (ib_o == ib_f)[okb].mean(),
                     "비교 일수": int(okb.sum())})
    R = pd.DataFrame(rows)
    print(R.to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    print("  실제 날씨 분포 A:", icon_a(O).value_counts(normalize=True).round(2).to_dict())
    print("  실제 날씨 분포 B:", icon_b(O).value_counts(normalize=True).round(2).to_dict())

    print("\n=== 3. 특보 수준: 예보 판정 vs 관측 판정 (주의보 이상, 2024-02 ~ 2026-10)")
    srows = []
    for kind, kname in NAME.items():
        o = (O_lv[kind] >= 1)
        line = {"종류": kname, "관측 특보 수준 일수": int(o.sum())}
        for k in range(1, 8):
            v = F_lv[k][f"valid_{kind}"].fillna(False).astype(bool)
            f = (F_lv[k][kind] >= 1) & v
            line[f"{k}일 전 포착"] = (f & o).sum() / max((o & v).sum(), 1)
            line[f"{k}일 전 맞음"] = (f & o).sum() / max(f.sum(), 1)
        srows.append(line)
    S = pd.DataFrame(srows)
    print(S[["종류", "관측 특보 수준 일수"] + [f"{k}일 전 포착" for k in range(1, 8)]].to_string(index=False, float_format=lambda x: f"{x:.0%}"))
    print("  (맞음 = 예보가 특보 수준이라고 한 날 중 실제로 특보 수준이었던 비율)")
    print(S[["종류"] + [f"{k}일 전 맞음" for k in range(1, 8)]].to_string(index=False, float_format=lambda x: f"{x:.0%}"))

    print("\n=== 4. 실제 발표된 NWS 특보와 비교 (주의보 이상)")
    O_all = vn.daily_levels(hourly(obs, VARS).iloc[:, :7].rename(columns={"code": "_"})).reindex(N_all.index)
    for kind, kname in NAME.items():
        n, o = N_all[kind] >= 1, O_all[kind] >= 1
        print(f"  {kname} (2016-02~2026-10): 실제 발표 {int(n.sum())}일, 우리 관측 판정 {int(o.sum())}일 | "
              f"발표된 날 중 우리도 특보 수준 {(n & o).sum() / max(n.sum(), 1):.0%}, 우리 판정 날 중 실제 발표 {(n & o).sum() / max(o.sum(), 1):.0%}")
    print("  예보 판정(띠) vs 실제 발표 (2024-02 ~ 2026-10):")
    for kind, kname in NAME.items():
        n = N[kind] >= 1
        parts = []
        for k in (1, 2, 3, 5, 7):
            f = (F_lv[k][kind] >= 1) & F_lv[k][f"valid_{kind}"].fillna(False).astype(bool)
            parts.append(f"{k}일 전 포착 {(f & n).sum() / max(n.sum(), 1):.0%}·맞음 {(f & n).sum() / max(f.sum(), 1):.0%}")
        print(f"    {kname} (발표 {int(n.sum())}일): " + ", ".join(parts))

    print("\n=== 5. 예시 띠 (예보 / 실제 / 실제 발표 특보)")
    ex_rows = []
    for asof in ["2025-06-20", "2026-02-20", "2026-10-12"]:
        a = pd.Timestamp(asof)
        print(f"  기준일 {asof}")
        for k in range(8):
            d = a + pd.Timedelta(days=k)
            lead = max(k, 1)
            F_h = hourly(fc, [f"{v}_previous_day{lead}" for v in VARS])
            Fd = daily(F_h[(F_h.time >= d) & (F_h.time < d + pd.Timedelta(days=1))]).reindex([d])
            Fl = vn.daily_levels(F_h[(F_h.time >= d - pd.Timedelta(days=2)) & (F_h.time < d + pd.Timedelta(days=2))]
                                 .iloc[:, :7].rename(columns={"code": "_"})).reindex([d])
            Od = daily(hourly(obs, VARS)[lambda x, d=d: (x.time >= d) & (x.time < d + pd.Timedelta(days=1))]).reindex([d])
            alerts_f = [f"{NAME[t]}{'경보' if Fl.at[d, t] == 2 else '주의보'}" for t in NAME if Fl.at[d, t] >= 1]
            alerts_n = [f"{NAME[t]}{'경보' if N_all.at[d, t] == 2 else '주의보'}" for t in NAME if d in N_all.index and N_all.at[d, t] >= 1]
            row = {"기준일": asof, "날짜": d.date(), "예보 시점": f"{lead}일 전", "예보 아이콘": icon_b(Fd).iloc[0],
                   "예보 최고/최저": f"{Fd.tmax.iloc[0]:.0f}/{Fd.tmin.iloc[0]:.0f}°C", "예보 강수": f"{Fd.prcp.iloc[0]:.0f}mm",
                   "예보 특보 수준": ", ".join(alerts_f) or "-", "실제 아이콘": icon_b(Od).iloc[0] if len(Od.dropna(how='all')) else "-",
                   "실제 최고": f"{Od.tmax.iloc[0]:.0f}°C" if Od.tmax.notna().iloc[0] else "-", "실제 발표 특보": ", ".join(alerts_n) or "-"}
            ex_rows.append(row)
            print("    " + " | ".join(str(v) for v in list(row.values())[1:]))
    OUT.mkdir(parents=True, exist_ok=True)
    R.to_csv(OUT / "forecast_strip_accuracy.csv", index=False)
    S.to_csv(OUT / "forecast_strip_alerts.csv", index=False)
    pd.DataFrame(ex_rows).to_csv(OUT / "forecast_strip_examples.csv", index=False)


if __name__ == "__main__":
    main()
