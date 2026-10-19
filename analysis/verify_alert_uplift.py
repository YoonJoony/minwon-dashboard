"""시연 리허설 보충: 이슈 경보를 부서 건수 예측에 반영하는 보정 (예보 기반).

리허설에서 폭염·블리자드 주에 부서 건수 예측이 크게 빗나갔습니다(기상을 쓰지 않는 모델이라).
보정 방식
- 2016~2023년 관측으로 'NWS 특보 수준 날씨일 때 관련 이슈 민원이 평소(직전 28일 평균)의 몇 배였나'(배수)를 구합니다.
- 예측 시점에 발표돼 있던 예보로 향후 7일의 특보 단계를 계산하고, 영향받는 날의 이슈 민원을 평소 × 배수로 늘려
  늘어난 만큼을 해당 부서 예측에 더합니다.
  폭염 → 소화전·수돗물(환경보호국, 당일·다음 날), 대설 → 제설(위생국, 1~2일 뒤), 강풍 → 수목(공원국, 당일·다음 날),
  호우 → 침수(환경보호국, 당일·다음 날)
평가: 2024-02 ~ 2026-09 매주 월요일 이번 주(1~7일) 부서 건수. 보정 전(단기 모델) vs 보정 후.

실행: uv run python analysis/verify_alert_uplift.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
from verify_nws_alerts import daily_levels

# (특보 종류, 이슈, 부서, 영향받는 날: 특보일 기준 며칠 뒤)
LINKS = [("heat", "폭염·소화전", "DEP", (0, 1)), ("heat", "수돗물", "DEP", (0, 1)),
         ("snow", "결빙·제설", "DSNY", (1, 2)), ("wind", "강풍·수목", "DPR", (0, 1)),
         ("rain", "폭우·침수", "DEP", (0, 1))]
LEAD = {0: 1, 1: 1, 2: 2, 3: 3, 4: 5, 5: 5, 6: 7}
COLS = ["t", "rh", "prcp", "snow", "wind", "gust"]


def load():
    iss = pd.read_csv(ROOT / "data/processed/daily_issue_weather.csv", parse_dates=["date"]).pivot(
        index="date", columns="issue", values="count")
    obs = pd.read_parquet(ROOT / "data/raw/weather/openmeteo_bronx_hourly_obs.parquet")
    obs.columns = ["time"] + COLS
    fc = pd.read_parquet(ROOT / "data/raw/weather/openmeteo_bronx_hourly_forecast.parquet")
    F = {}
    for L in sorted(set(LEAD.values())):
        f = fc[["time"] + [c for c in fc.columns if c.endswith(f"_previous_day{L}")]].copy()
        f.columns = ["time"] + COLS
        F[L] = daily_levels(f)
    return iss, daily_levels(obs), F


def multipliers(iss: pd.DataFrame, obs_lv: pd.DataFrame, until: str = "2024-01-01") -> dict:
    """관측 특보 수준 날의 영향일 이슈 건수 ÷ 직전 28일 평균 (평균값). 단계별(1 주의보, 2 경보)."""
    base = iss.rolling(28).mean().shift(1)
    out = {}
    for key, issue, _, (lo, hi) in LINKS:
        for lv in (1, 2):
            ev = obs_lv.index[(obs_lv[key] >= lv) & (obs_lv.index < until)]
            r = [iss[issue].get(d + pd.Timedelta(days=k), np.nan) / max(base[issue].get(d, np.nan), 1)
                 for d in ev for k in range(lo, hi + 1)]
            out[(key, issue, lv)] = float(np.nanmean(r)) if r else 1.0
    return out


def uplift(origin: pd.Timestamp, iss: pd.DataFrame, F: dict, mult: dict, obs_lv: pd.DataFrame) -> dict:
    """origin(포함)부터 7일 동안 부서별 추가 예상 건수와 이슈별 내역."""
    base = iss.loc[origin - pd.Timedelta(days=28): origin - pd.Timedelta(days=1)].mean()
    window = pd.date_range(origin, origin + pd.Timedelta(days=6))
    extra, detail = {}, []
    for key, issue, dept, (lo, hi) in LINKS:
        m_day = pd.Series(1.0, index=window)
        for k in range(-2, 7):                       # 기간 직전 이틀의 특보도 기간 안에 영향
            d = origin + pd.Timedelta(days=k)
            if k < 0:
                lv = obs_lv[key].get(d, 0)          # 이미 지난 날은 관측으로
            else:
                lv = F[LEAD[k]][key].get(d, 0)
            lv = 0 if pd.isna(lv) else int(lv)
            if lv == 0:
                continue
            for j in range(lo, hi + 1):
                e = d + pd.Timedelta(days=j)
                if e in m_day.index:
                    m_day[e] = max(m_day[e], mult[(key, issue, lv)])
        add = float(((m_day - 1) * base[issue]).sum())
        if add > 0:
            extra[dept] = extra.get(dept, 0) + add
            detail.append((issue, dept, add))
    return {"extra": extra, "detail": detail}


def main() -> None:
    iss, obs_lv, F = load()
    mult = multipliers(iss, obs_lv)
    print("=== 특보 수준 날씨일 때 관련 이슈 민원 배수 (2016~2023 관측, 평균)")
    for (key, issue, lv), v in mult.items():
        print(f"  {key:5s} {'경보' if lv == 2 else '주의보 이상'} → {issue}: {v:.1f}배")
    bt = pd.read_csv(ROOT / "analysis/results/short_term_backtest.csv", parse_dates=["origin"])
    bt = bt[(bt.block == 1) & (bt.origin >= "2024-02-05")].copy()
    ups = {t: uplift(t, iss, F, mult, obs_lv)["extra"] for t in bt.origin.unique()}
    bt["extra"] = [ups[t].get(a, 0.0) for t, a in zip(bt.origin, bt.agency)]
    bt["pred_adj"] = bt.pred_model + bt.extra
    bt["e0"] = (bt.pred_model - bt.actual).abs() / bt.actual
    bt["e1"] = (bt.pred_adj - bt.actual).abs() / bt.actual
    print(f"\n=== 이번 주 부서 건수 예측 오차 (2024-02 ~ 2026-09, {bt.origin.nunique()}주)")
    for a in ["DEP", "DSNY", "DPR"]:
        g = bt[bt.agency == a]
        ev = g.extra > 0
        print(f"  {a:5s} 전체 {g.e0.mean():.1%} → {g.e1.mean():.1%} | 보정이 들어간 주({ev.sum()}주) "
              f"{g.e0[ev].mean():.1%} → {g.e1[ev].mean():.1%} | 큰 급증 주(실제 ≥ 평소의 1.5배) "
              f"{g.e0[g.actual >= 1.5 * g.base].mean():.1%} → {g.e1[g.actual >= 1.5 * g.base].mean():.1%}")
    allv = bt
    print(f"  8개 부서 전체 평균 {allv.e0.mean():.1%} → {allv.e1.mean():.1%}")
    bt.to_csv(ROOT / "analysis/results/alert_uplift_backtest.csv", index=False)
    pd.Series({f"{k[0]}|{k[1]}|{k[2]}": v for k, v in mult.items()}).to_csv(ROOT / "analysis/results/alert_multipliers.csv")


if __name__ == "__main__" and len(sys.argv) == 1:
    main()


# ====================================================================== 방식 2: 이슈 모델 차이
# 배수 방식은 평소 건수가 0에 가까운 이슈(겨울 초 제설 등)에서 과하게 부풀어 오차가 커졌습니다.
# 대신 이슈별 주간 건수를 '기상 포함/미포함' 두 모델로 예측하고, 그 차이(늘어나는 만큼)만 부서 예측에 더합니다.
# 학습은 2017~2023년 관측 기상, 적용은 예측 시점에 발표돼 있던 예보 기상입니다.
ISSUE_DEPT = {"폭염·소화전": "DEP", "수돗물": "DEP", "폭우·침수": "DEP", "결빙·제설": "DSNY", "강풍·수목": "DPR"}
WX = ["tmax", "hot_days", "precip", "precip_max", "snow", "gust"]


def fc_daily_metric(F_hourly: pd.DataFrame) -> dict:
    """예보 시간별(미국 단위) → 예보 시점별 일 단위(미터 단위) 표."""
    out = {}
    for L in sorted(set(LEAD.values())):
        f = F_hourly[["time"] + [c for c in F_hourly.columns if c.endswith(f"_previous_day{L}")]].copy()
        f.columns = ["time"] + COLS
        day = f.time.dt.normalize()
        out[L] = pd.DataFrame({"tmax": (f.t.groupby(day).max() - 32) / 1.8,
                               "precip": f.prcp.groupby(day).sum() * 25.4,
                               "snow": f.snow.groupby(day).sum() * 2.54,
                               "gust": f.gust.groupby(day).max() * 1.609})
    return out


def issue_rows(iss, wobs, origins, fcd=None):
    import lightgbm  # noqa: F401  (이 함수 바깥에서 모델에 씀)
    rows = []
    for t in origins:
        s, e = t, t + pd.Timedelta(days=6)
        days = pd.date_range(s - pd.Timedelta(days=2), e)
        recs = []
        for d in days:
            k = (d - t).days
            if fcd is None or k < 0:
                o = wobs.loc[d]
                recs.append((o.temperature_2m_max, o.precipitation_sum, o.snowfall_sum, o.wind_gusts_10m_max))
            else:
                f = fcd[LEAD[k]].loc[d] if d in fcd[LEAD[k]].index else None
                recs.append((f.tmax, f.precip, f.snow, f.gust) if f is not None else (np.nan,) * 4)
        W = pd.DataFrame(recs, columns=["tmax", "precip", "snow", "gust"], index=days)
        for k_, y in iss.items():
            if k_ not in ISSUE_DEPT:
                continue
            r28 = y.loc[t - pd.Timedelta(days=28): t - pd.Timedelta(days=1)].mean()
            ly = [y.loc[s - pd.DateOffset(years=j): e - pd.DateOffset(years=j)].sum() for j in (1, 2, 3)
                  if s - pd.DateOffset(years=j) >= y.index[0]]
            rows.append({"origin": t, "issue": k_, "actual": y.loc[s:e].sum(), "r28x7": r28 * 7,
                         "r7": y.loc[t - pd.Timedelta(days=7): t - pd.Timedelta(days=1)].sum(),
                         "ly_med": np.median(ly) if ly else np.nan,
                         "doy_sin": np.sin(2 * np.pi * s.dayofyear / 365.25), "doy_cos": np.cos(2 * np.pi * s.dayofyear / 365.25),
                         "tmax": W.tmax.max(), "hot_days": (W.tmax >= 32).sum(), "precip": W.precip.sum(),
                         "precip_max": W.precip.max(), "snow": W.snow.sum(), "gust": W.gust.max()})
    df = pd.DataFrame(rows)
    df["issue"] = pd.Categorical(df["issue"], categories=list(ISSUE_DEPT))
    return df


def issue_models(iss, wobs, until="2024-01-01"):
    import lightgbm as lgb
    tr = issue_rows(iss, wobs, pd.date_range("2017-01-02", pd.Timestamp(until) - pd.Timedelta(days=14), freq="W-MON"))
    base_f = ["issue", "r28x7", "r7", "ly_med", "doy_sin", "doy_cos"]
    ms = {}
    for name, f in (("no_wx", base_f), ("wx", base_f + WX)):
        ms[name] = (lgb.LGBMRegressor(n_estimators=500, learning_rate=0.03, num_leaves=15, min_child_samples=20,
                                      objective="poisson", verbose=-1, random_state=0).fit(tr[f], tr["actual"]), f)
    return ms


def issue_extra(ms, rows) -> pd.DataFrame:
    p0 = ms["no_wx"][0].predict(rows[ms["no_wx"][1]])
    p1 = ms["wx"][0].predict(rows[ms["wx"][1]])
    return rows.assign(extra=np.clip(p1 - p0, 0, None))


def main2() -> None:
    iss = pd.read_csv(ROOT / "data/processed/daily_issue_weather.csv", parse_dates=["date"]).pivot(
        index="date", columns="issue", values="count")
    wobs = pd.read_csv(ROOT / "data/processed/weather_features_daily.csv", parse_dates=["date"]).set_index("date")
    fcd = fc_daily_metric(pd.read_parquet(ROOT / "data/raw/weather/openmeteo_bronx_hourly_forecast.parquet"))
    ms = issue_models(iss, wobs)
    test = issue_extra(ms, issue_rows(iss, wobs, pd.date_range("2024-02-05", "2026-09-28", freq="W-MON"), fcd))
    test["dept"] = test.issue.map(ISSUE_DEPT)
    ex = test.groupby(["origin", "dept"]).extra.sum()
    bt = pd.read_csv(ROOT / "analysis/results/short_term_backtest.csv", parse_dates=["origin"])
    bt = bt[(bt.block == 1) & (bt.origin >= "2024-02-05")].copy()
    bt["extra"] = [ex.get((t, a), 0.0) for t, a in zip(bt.origin, bt.agency)]
    bt["pred_adj"] = bt.pred_model + bt.extra
    bt["e0"] = (bt.pred_model - bt.actual).abs() / bt.actual.clip(lower=1)
    bt["e1"] = (bt.pred_adj - bt.actual).abs() / bt.actual.clip(lower=1)
    print(f"\n=== 방식 2 (이슈 모델 차이, 예보 기상): 이번 주 부서 건수 예측 오차 (2024-02 ~ 2026-09, {bt.origin.nunique()}주)")
    for a in ["DEP", "DSNY", "DPR"]:
        g = bt[bt.agency == a]
        big = g.actual >= 1.5 * g.base
        sig = g.extra >= 0.05 * g.pred_model
        print(f"  {a:5s} 전체 {g.e0.mean():.1%} → {g.e1.mean():.1%} | 보정 5% 이상 들어간 주({sig.sum()}주) "
              f"{g.e0[sig].mean():.1%} → {g.e1[sig].mean():.1%} | 큰 급증 주({big.sum()}주) {g.e0[big].mean():.1%} → {g.e1[big].mean():.1%}")
    print(f"  8개 부서 전체 평균 {bt.e0.mean():.1%} → {bt.e1.mean():.1%}")
    bt.to_csv(ROOT / "analysis/results/alert_uplift_backtest.csv", index=False)
    for t in [pd.Timestamp("2025-06-23"), pd.Timestamp("2026-02-23")]:
        g = bt[bt.origin == t].set_index("agency")
        print(f"  사례 {t:%Y-%m-%d} 주: " + ", ".join(
            f"{a} 보정 전 {g.loc[a, 'pred_model']:,.0f} → 후 {g.loc[a, 'pred_adj']:,.0f} (실제 {g.loc[a, 'actual']:,.0f})" for a in ["DEP", "DSNY", "DPR"]))


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "2":
    main2()


# ====================================================================== 방식 3: 경보 영향 표시 (건수 보정 대신)
def alert_flags(origins, F, obs_lv) -> pd.DataFrame:
    """주(월요일 시작 7일)마다, 예보상 NWS 특보가 관련 이슈에 영향을 주는 부서 표시."""
    rows = []
    for t in origins:
        hit = {}
        for key, issue, dept, (lo, hi) in LINKS:
            for k in range(-2, 7):
                d = t + pd.Timedelta(days=k)
                lv = obs_lv[key].get(d, 0) if k < 0 else F[LEAD[k]][key].get(d, 0)
                if not pd.isna(lv) and lv >= 1 and any(0 <= k + j <= 6 for j in range(lo, hi + 1)):
                    hit[dept] = max(hit.get(dept, 0), int(lv))
        rows.append({"origin": t, **hit})
    return pd.DataFrame(rows).set_index("origin").fillna(0)


def main3() -> None:
    _, obs_lv, F = load()
    bt = pd.read_csv(ROOT / "analysis/results/short_term_backtest.csv", parse_dates=["origin"])
    bt = bt[bt.block == 1].copy()
    fl = alert_flags(bt.origin.unique(), F, obs_lv)
    bt["alert"] = [fl.loc[t].get(a, 0) if t in fl.index else 0 for t, a in zip(bt.origin, bt.agency)]
    bt = bt[bt.origin >= "2024-02-05"]
    bt["ratio"] = bt.actual / bt.pred_model
    bt["x_pred"] = bt.pred_model / bt.base - 1
    bt["x_act"] = bt.actual / bt.base - 1
    print("\n=== 방식 3: 예보 특보 영향 부서-주의 실제 ÷ 예측 (2024-02 ~ 2026-09)")
    for name, g in (("특보 영향 있음", bt[bt.alert > 0]), ("특보 영향 없음", bt[(bt.alert == 0) & bt.agency.isin(["DEP", "DSNY", "DPR"])])):
        print(f"  {name}: {len(g)}개, 실제÷예측 중앙값 {g.ratio.median():.2f}, 90% 지점 {g.ratio.quantile(.9):.2f}, 최대 {g.ratio.max():.1f}"
              f" | 예측 '지원 가능'(접수 −10% 이하)인데 실제 +10% 이상: {((g.x_pred <= -0.1) & (g.x_act >= 0.1)).sum()}건 / 예측 지원 가능 {(g.x_pred <= -0.1).sum()}건")
    q = bt[bt.alert > 0].groupby("agency").ratio.quantile(0.9)
    print("  부서별 특보 주 실제÷예측 90% 지점:", ", ".join(f"{a} {v:.1f}배" for a, v in q.items()))
    fl.to_csv(ROOT / "analysis/results/alert_flags_weekly.csv")


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "3":
    main3()
