"""10년치 검증 ②-보충: 이슈 단위 단기 예측에서 기상의 효과, 기상 강도별 경보 적중률.

부서 전체 건수에서는 기상 효과가 묻히므로, 기상과 직접 연결된 이슈(소화전·제설·침수·수목·수돗물)의
이번 주(1~7일) 건수를 같은 방식으로 예측해 기상 유무를 비교합니다. 기상은 실제 관측값(상한)입니다.

실행: uv run python analysis/verify_short_term_issue.py
"""
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis/results"
ISSUES = ["폭염·소화전", "결빙·제설", "폭우·침수", "강풍·수목", "수돗물"]


def main() -> None:
    i = pd.read_csv(ROOT / "data/processed/daily_issue_weather.csv", parse_dates=["date"])
    w = pd.read_csv(ROOT / "data/processed/weather_features_daily.csv", parse_dates=["date"]).set_index("date")
    iss = i.pivot(index="date", columns="issue", values="count")
    rows = []
    for t in pd.date_range("2017-01-02", "2026-09-28", freq="W-MON"):
        s, e = t, t + pd.Timedelta(days=6)
        ww = w.loc[s - pd.Timedelta(days=2): e]
        for k in ISSUES:
            y = iss[k]
            r28 = y.loc[t - pd.Timedelta(days=28): t - pd.Timedelta(days=1)].mean()
            ly = [y.loc[s - pd.DateOffset(years=j): e - pd.DateOffset(years=j)].sum() for j in (1, 2, 3)
                  if s - pd.DateOffset(years=j) >= y.index[0]]
            rows.append({"origin": t, "issue": k, "actual": y.loc[s:e].sum(), "r28x7": r28 * 7,
                         "r7": y.loc[t - pd.Timedelta(days=7): t - pd.Timedelta(days=1)].sum(),
                         "ly_med": np.median(ly) if ly else np.nan,
                         "doy_sin": np.sin(2 * np.pi * s.dayofyear / 365.25), "doy_cos": np.cos(2 * np.pi * s.dayofyear / 365.25),
                         "tmax": ww.temperature_2m_max.max(), "hot_days": ww.is_hot.sum(), "precip": ww.precipitation_sum.sum(),
                         "precip_max": ww.precipitation_sum.max(), "snow": ww.snowfall_sum.sum(), "gust": ww.wind_gusts_10m_max.max()})
    df = pd.DataFrame(rows)
    df["issue"] = df["issue"].astype("category")
    base_f = ["issue", "r28x7", "r7", "ly_med", "doy_sin", "doy_cos"]
    wx_f = ["tmax", "hot_days", "precip", "precip_max", "snow", "gust"]
    res = []
    for yr in range(2022, 2027):
        tr, te = df[df.origin < f"{yr}-01-01"], df[(df.origin >= f"{yr}-01-01") & (df.origin < f"{yr + 1}-01-01")].copy()
        for name, f in (("기상 없음", base_f), ("기상 포함(관측)", base_f + wx_f)):
            m = lgb.LGBMRegressor(n_estimators=500, learning_rate=0.03, num_leaves=15, min_child_samples=20,
                                  objective="poisson", verbose=-1, random_state=0).fit(tr[f], tr["actual"])
            te[name] = m.predict(te[f])
        res.append(te)
    R = pd.concat(res)
    print("=== 이슈별 이번 주(1~7일) 건수 예측, 평가 2022-01 ~ 2026-09: 평균 절대 오차(건) / 급증 주(상위 10%) 오차")
    for k, g in R.groupby("issue", observed=True):
        top = g.actual >= g.actual.quantile(0.9)
        e0, e1 = (g["기상 없음"] - g.actual).abs(), (g["기상 포함(관측)"] - g.actual).abs()
        print(f"  {k:6s} 전체 {e0.mean():6.1f} → {e1.mean():6.1f}건 ({1 - e1.mean() / e0.mean():+.0%})"
              f" | 급증 주 {e0[top].mean():6.1f} → {e1[top].mean():6.1f}건 ({1 - e1[top].mean() / e0[top].mean():+.0%})")

    print("\n=== 기상 강도별 경보 적중률 (경보 후 기간 안에 관련 민원 급증: 직전 28일 중앙값의 2배·20건 이상)")
    def rate(issue, cond, lo, hi):
        s = iss[issue]
        surge = (s >= 2 * s.rolling(28).median().shift(1).clip(lower=1)) & (s >= 20)
        ev = cond.reindex(s.index).fillna(False)
        hit = pd.concat([surge.shift(-k) for k in range(lo, hi + 1)], axis=1).any(axis=1)
        return int(ev.sum()), hit[ev].mean()
    for name, issue, col, levels, (lo, hi) in [
        ("최고기온", "폭염·소화전", "temperature_2m_max", [30, 32, 34, 36], (0, 1)),
        ("적설", "결빙·제설", "snowfall_sum", [1, 2, 5, 10], (1, 2)),
        ("강수", "폭우·침수", "precipitation_sum", [15, 25, 40, 60], (0, 1)),
        ("돌풍", "강풍·수목", "wind_gusts_10m_max", [50, 60, 70, 80], (0, 1)),
    ]:
        out = []
        for lv in levels:
            n, r = rate(issue, w[col] >= lv, lo, hi)
            out.append(f"≥{lv}: {r:.0%} ({n}일)")
        print(f"  {name} → {issue}: " + " | ".join(out))


if __name__ == "__main__":
    main()
