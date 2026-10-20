"""기상 이슈 사건별 영향 기간과 민원 처리 현황 — '7일 기상 예보 띠 + 과거 7년 모달' 기능 설계용 검증.

1. 사건: 관측 기준 NWS 특보 수준 날씨(analysis/verify_nws_alerts.py와 같은 판정)가 이어진 날들.
   하루 쉬고 다시 오면 같은 사건으로 묶음.
2. 영향 기간: 사건 전후로 관련 민원이 평소보다 늘어난 날을 실제 데이터로 재서 기상 종류별 규칙을 정함.
   늘어난 날 = 평소(사건 전 28일 하루 중앙값)의 1.5배 이상이고 5건 이상 많은 날.
   규칙 = [사건 첫날 + a일, 사건 마지막 날 + b일]. a·b는 급증 사건들의 '늘기 시작한 날'·'마지막으로 늘어난 날'의 중앙값.
   영향 기간이 겹치는 사건은 하나로 합침.
3. 모달 값: 평소(직전 28일 중 다른 영향 기간을 뺀 날의 중앙값), 접수, 늘어난 건수, 영향 기간 내 처리 건수, 미처리(영향 끝, +7일).
4. 7일 예보 띠: 예보 시점별(1·2·3·5·7일 전) 최고기온 오차.

실행: uv run python analysis/verify_weather_events.py
결과: analysis/results/weather_events.csv (사건 × 대상 민원), weather_event_rules.csv (기상별 영향 기간 규칙)
"""
from pathlib import Path

import numpy as np
import pandas as pd
import verify_nws_alerts as vn
from verify_forecast_strip import official

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis/results"
D = pd.Timedelta
# 기상 → 대상 민원 (앞이 주 대상, engine.config.LINKS와 같은 연결)
# rain_nws: 호우는 우리 대체 지표(1시간 강수) 대신 실제 발표된 NWS 홍수 주의보·돌발 홍수 경보로도 사건을 만들어 비교
LINK = {"heat": ["폭염·소화전", "수돗물"], "snow": ["결빙·제설"], "wind": ["강풍·수목"], "rain": ["폭우·침수"], "rain_nws": ["폭우·침수"]}
NAME = {"heat": "폭염", "snow": "대설", "wind": "강풍", "rain": "호우", "rain_nws": "호우(NWS 특보)"}
SPAN_AFTER = 10       # 사건 끝 뒤 며칠까지 영향을 보나
HOURLY = {"temperature_2m": "t", "relative_humidity_2m": "rh", "precipitation": "prcp", "snowfall": "snow",
          "wind_speed_10m": "wind", "wind_gusts_10m": "gust"}


def runs(levels: pd.DataFrame, kind: str) -> list[tuple[pd.Timestamp, pd.Timestamp, int]]:
    out: list[list] = []
    for d in levels.index[levels[kind] >= 1]:
        if out and (d - out[-1][1]).days <= 2:
            out[-1][1] = d
        else:
            out.append([d, d])
    return [(a, b, int(levels.loc[a:b, kind].max())) for a, b in out]


def profile(daily: pd.Series, a: pd.Timestamp, b: pd.Timestamp) -> dict:
    base = float(daily.loc[a - D(days=28): a - D(days=1)].median())
    span = daily.loc[a - D(days=3): b + D(days=SPAN_AFTER)]
    elevated = (span >= 1.5 * max(base, 1)) & (span - base >= 5)
    peak = span.loc[a: b + D(days=3)]
    surge = bool(((peak >= 2 * max(base, 1)) & (peak >= 20)).any())
    first = tail = None
    for d, v in elevated.loc[a - D(days=2):].items():
        if v and first is None:
            first = d
        if first is not None and not v and d > b:
            break
        if v:
            tail = d
    return {"base": base, "span": span, "surge": surge, "peak_ratio": float(peak.max() / max(base, 1)),
            "first_lag": None if first is None else (first - a).days, "tail_lag": None if tail is None else (tail - b).days}


def main() -> None:
    obs = pd.read_parquet(ROOT / "data/raw/weather/openmeteo_bronx_hourly_obs.parquet").rename(columns=HOURLY)
    lv = vn.daily_levels(obs)
    lv = lv[(lv.index >= "2016-02-01") & (lv.index <= "2026-09-30")]
    lv["rain_nws"] = official(pd.read_csv(ROOT / "data/raw/nws/nws_alerts_bronx.csv"), lv.index)["rain"]
    cf = pd.read_parquet(ROOT / "data/processed/complaint_features.parquet",
                         columns=["created", "closed", "status", "issue"])
    cf = cf[cf.issue.isin([i for v in LINK.values() for i in v])]
    daily = cf.groupby([cf.created.dt.normalize(), "issue"]).size().unstack(fill_value=0)
    daily = daily.reindex(pd.date_range("2016-01-01", "2026-10-11"), fill_value=0)

    # ------------------------------------------------------------------ 1. 사건과 민원 흐름
    print("=== 1. 관측 특보 수준 사건 (2016-02 ~ 2026-09)")
    raw = {k: runs(lv, k) for k in LINK}
    for k, rs in raw.items():
        yrs = pd.Series([a.year for a, _, _ in rs]).value_counts().reindex(range(2016, 2027), fill_value=0)
        print(f"  {NAME[k]}: {len(rs)}건, 해마다 {yrs.to_dict()}")

    print("\n=== 2. 사건 끝 기준 민원 흐름 (급증 사건, 평소 대비 배수 중앙값)")
    rules = []
    for k, rs in raw.items():
        issue = LINK[k][0]
        P = [profile(daily[issue], a, b) | {"a": a, "b": b} for a, b, _ in rs]
        S = [p for p in P if p["surge"]]
        prof = pd.concat([pd.Series(p["span"].to_numpy() / max(p["base"], 1), index=[(d - p["b"]).days for d in p["span"].index])
                          for p in S], axis=1).median(axis=1)
        print(f"  {NAME[k]} → {issue} ({len(S)}/{len(P)} 사건 급증): "
              + " ".join(f"{o:+d}일 {v:.1f}" for o, v in prof.loc[-2:7].items()))
        a_off = int(np.clip(np.median([p["first_lag"] for p in S if p["first_lag"] is not None]), -1, 1))
        b_off = int(np.median([p["tail_lag"] for p in S if p["tail_lag"] is not None]))
        # 규칙 검증: 늘어난 민원(평소 초과분)을 영향 기간 안에 담은 비율, 영향 기간 중 실제로 늘어난 날 비율
        cap, hot = [], []
        for p in S:
            exc = (p["span"] - p["base"]).clip(lower=0)
            win = exc.loc[p["a"] + D(days=a_off): p["b"] + D(days=b_off)]
            cap.append(win.sum() / max(exc.sum(), 1))
            hot.append((p["span"].loc[win.index] >= 1.5 * max(p["base"], 1)).mean())
        rules.append({"기상": NAME[k], "kind": k, "대상 민원": issue, "급증 사건": len(S), "전체 사건": len(P),
                      "시작 보정(일)": a_off, "끝 뒤(일)": b_off, "늘어난 민원 담은 비율": np.mean(cap), "기간 중 늘어난 날": np.mean(hot)})
    R = pd.DataFrame(rules)
    print("\n=== 3. 영향 기간 규칙 (급증 사건의 중앙값)")
    for r in R.to_dict("records"):
        print(f"  {r['기상']}: [사건 첫날 {r['시작 보정(일)']:+d}일 ~ 마지막 날 +{r['끝 뒤(일)']}일] — 늘어난 민원의 "
              f"{r['늘어난 민원 담은 비율']:.0%}를 담고, 기간 중 {r['기간 중 늘어난 날']:.0%}가 실제로 늘어난 날 ({r['급증 사건']}개 급증 사건)")

    # ------------------------------------------------------------------ 4. 영향 기간이 겹치는 사건은 합치고, 사건별 모달 값
    rule = {r["kind"]: (r["시작 보정(일)"], r["끝 뒤(일)"]) for r in R.to_dict("records")}
    rows = []
    for k, rs in raw.items():
        a_off, b_off = rule[k]
        merged: list[list] = []
        for a, b, lvl in rs:
            ws, we = a + D(days=a_off), b + D(days=b_off)
            if merged and ws <= merged[-1][3] + D(days=1):
                merged[-1][1], merged[-1][3], merged[-1][4] = b, we, max(merged[-1][4], lvl)
            else:
                merged.append([a, b, ws, we, lvl])
        windows = [(ws, we) for _, _, ws, we, _ in merged]
        for a, b, ws, we, lvl in merged:
            for issue in LINK[k]:
                s = daily[issue]
                prev = s.loc[ws - D(days=28): ws - D(days=1)]
                mask = pd.Series(True, index=prev.index)
                for x, y in windows:                       # 다른 특보 영향 기간은 '평소'에서 뺌
                    mask &= ~((prev.index >= x) & (prev.index <= y))
                base = float(prev[mask].median()) if mask.sum() >= 7 else float(prev.median())
                base_old = float(prev.median())
                n = (we - ws).days + 1
                sub = cf[(cf.issue == issue) & (cf.created >= ws) & (cf.created < we + D(days=1))]
                closed_by = lambda t: int((sub.closed.notna() & (sub.closed < t) & (sub.status == "Closed")).sum())
                c_end, c_7 = closed_by(we + D(days=1)), closed_by(we + D(days=8))
                peak = s.loc[ws:we]
                rows.append({"기상": NAME[k], "대상 민원": issue, "사건 시작": a.date(), "사건 끝": b.date(),
                             "단계": "경보" if lvl == 2 else "주의보", "영향 시작": ws.date(), "영향 끝": we.date(), "영향 일수": n,
                             "평소(하루)": base, "평소(하루, 영향 기간 포함)": base_old, "접수": len(sub),
                             "늘어난 건수": len(sub) - base * n,
                             "영향 기간 내 처리": c_end, "미처리 영향 끝": len(sub) - c_end, "처리 +7일": c_7, "미처리 +7일": len(sub) - c_7,
                             "최대 하루": int(peak.max()), "급증": bool(((peak >= 2 * max(base, 1)) & (peak >= 20)).any())})
    E = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    E.to_csv(OUT / "weather_events.csv", index=False)
    R.drop(columns="kind").to_csv(OUT / "weather_event_rules.csv", index=False)

    print("\n=== 4. 사건별 모달 값 (영향 기간 겹치는 사건 합친 뒤, 주 대상 민원, 급증 사건 중앙값)")
    G = E[E["대상 민원"].isin([v[0] for v in LINK.values()])].copy()
    G["미처리율 영향 끝"] = G["미처리 영향 끝"] / G["접수"]
    G["미처리율 +7일"] = G["미처리 +7일"] / G["접수"]
    print(G[G["급증"]].groupby("기상")[["영향 일수", "평소(하루)", "접수", "늘어난 건수", "미처리율 영향 끝",
                                     "미처리율 +7일"]].median().round(2).to_string())
    neg = G[(G["늘어난 건수"] < 0)]
    print(f"  늘어난 건수가 음수인 사건: {len(neg)}개 (평소에서 다른 영향 기간을 빼기 전에는 "
          f"{int(((G['접수'] - G['평소(하루, 영향 기간 포함)'] * G['영향 일수']) < 0).sum())}개)")
    print("  사건 수(합친 뒤):", G.groupby("기상").size().to_dict(), "· 급증 없던 사건:", G[~G["급증"]].groupby("기상").size().to_dict())

    print("\n=== 5. 모달 예시: 2025-06-22 폭염 경보 예보일을 고르면 → 과거 7년(2018~2024) 같은 시기 폭염")
    H = E[(E["기상"] == "폭염")].copy()
    H["doy_gap"] = pd.to_datetime(H["사건 시작"]).apply(lambda t: abs((t - pd.Timestamp(t.year, 6, 22)).days))
    for y in range(2024, 2017, -1):
        hy = H[pd.to_datetime(H["사건 시작"]).dt.year == y]
        if hy.empty:
            print(f"  {y}: 폭염 특보 수준 날씨 없음")
            continue
        best = hy.sort_values("doy_gap").iloc[0]
        same = hy[(hy["사건 시작"] == best["사건 시작"])]
        n_ev = hy["사건 시작"].nunique()
        for r in same.to_dict("records"):
            print(f"  {y} (그 해 {n_ev}회) {r['사건 시작']}~{r['사건 끝']} {r['단계']} | {r['대상 민원']} 영향 {r['영향 시작']}~{r['영향 끝']}"
                  f"({r['영향 일수']}일) 평소 {r['평소(하루)']:.0f}/일 접수 {r['접수']:,} 늘어남 {r['늘어난 건수']:+,.0f} "
                  f"영향 기간 내 처리 {r['영향 기간 내 처리']:,} 미처리 끝 {r['미처리 영향 끝']:,}·+7일 {r['미처리 +7일']:,}")

    # ------------------------------------------------------------------ 6. 7일 예보 띠: 예보 시점별 정확도
    print("\n=== 6. 예보 시점별 하루 최고기온 오차 (2022-01 ~ 2026-10, °C)")
    fc = pd.read_parquet(ROOT / "data/raw/weather/openmeteo_bronx_hourly_forecast.parquet")
    o_max = obs.set_index("time").t.resample("D").max()
    for lead in (1, 2, 3, 5, 7):
        f_max = fc.set_index("time")[f"temperature_2m_previous_day{lead}"].resample("D").max()
        err = ((f_max - o_max) * 5 / 9).dropna()
        print(f"  {lead}일 전 예보: 평균 오차 ±{err.abs().mean():.1f}°C, 3°C 넘게 틀린 날 {(err.abs() > 3).mean():.0%} ({len(err):,}일)")


if __name__ == "__main__":
    main()
