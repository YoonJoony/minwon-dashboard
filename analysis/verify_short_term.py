"""10년치 검증 ②: 단기(1~7일, 8~14일) 접수 건수 예측 + 기상 경보 적중률.

- 예측 시점: 매주 월요일. 그 전날까지의 데이터만 사용.
- 대상: 이번 주(1~7일)와 다음 주(8~14일)의 부서별 접수 건수 합계.
- 방법
  1) 최근 4주 평균: 직전 28일 일평균 × 7 (가장 단순한 기준)
  2) 모델(기상 없음): LightGBM. 최근 수준, 직전 1주 흐름, 과거 같은 시기 비율, 공휴일, 시기
  3) 모델 + 기상: 2)에 그 기간의 실제 관측 기상을 더함 → 실제 예보로 쓰면 이보다 낮아지므로 '상한'
- 학습: 평가 연도 직전까지 모든 데이터(2017년부터)로 해마다 다시 학습. 평가 2022-01 ~ 2026-09.

기상 경보 적중률: 기상 조건이 생긴 날 → 정해진 기간 안에 관련 민원 급증(직전 28일 중앙값의 2배 이상, 20건 이상).

실행: uv run python analysis/verify_short_term.py
"""
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis/results"
AG = ["DCWP", "DEP", "DHS", "DOB", "DOHMH", "DOT", "DPR", "DSNY"]


def build_rows(cnt: pd.DataFrame, w: pd.DataFrame, origins: pd.DatetimeIndex | None = None) -> pd.DataFrame:
    days = cnt.index
    hol = w["is_holiday"].reindex(days).fillna(0)
    rows = []
    if origins is None:
        origins = pd.date_range("2017-01-02", "2026-09-21", freq="W-MON")
    for t in origins:
        if t - pd.Timedelta(days=28 * 13) < days[0]:
            continue
        for blk, (a, b) in ((1, (0, 6)), (2, (7, 13))):
            s, e = t + pd.Timedelta(days=a), t + pd.Timedelta(days=b)
            if e > days[-1]:
                continue
            ww = w.loc[s - pd.Timedelta(days=2): e]
            for ag in AG:
                y = cnt[ag]
                r28 = y.loc[t - pd.Timedelta(days=28): t - pd.Timedelta(days=1)].mean()
                r7 = y.loc[t - pd.Timedelta(days=7): t - pd.Timedelta(days=1)].mean()
                # 과거 같은 시기 비율: 지난 3년 같은 기간 합계 ÷ 그때의 직전 28일 일평균×7
                ratios = []
                for k in (1, 2, 3):
                    ps, pe, pt = s - pd.DateOffset(years=k), e - pd.DateOffset(years=k), t - pd.DateOffset(years=k)
                    if pt - pd.Timedelta(days=28) < days[0]:
                        continue
                    base = y.loc[pt - pd.Timedelta(days=28): pt - pd.Timedelta(days=1)].mean() * 7
                    if base > 0:
                        ratios.append(y.loc[ps:pe].sum() / base)
                rows.append({
                    "origin": t, "block": blk, "agency": ag, "actual": y.loc[s:e].sum(), "base": r28 * 7,
                    "r7_r28": r7 / r28 if r28 > 0 else 1.0, "season_ratio": np.median(ratios) if ratios else 1.0,
                    "holidays": hol.loc[s:e].sum(), "woy_sin": np.sin(2 * np.pi * s.dayofyear / 365.25),
                    "woy_cos": np.cos(2 * np.pi * s.dayofyear / 365.25),
                    "tmax": ww["temperature_2m_max"].max(), "hot_days": ww["is_hot"].sum(),
                    "precip": ww["precipitation_sum"].sum(), "rain_days": ww["is_heavy_rain"].sum(),
                    "snow": ww["snowfall_sum"].sum(), "gust_days": ww["is_strong_gust"].sum(),
                })
    df = pd.DataFrame(rows)
    df["agency"] = df["agency"].astype("category")
    df["target"] = np.log((df["actual"] + 1) / (df["base"] + 1))
    return df


BASE_F = ["agency", "block", "r7_r28", "season_ratio", "holidays", "woy_sin", "woy_cos"]
WX_F = ["tmax", "hot_days", "precip", "rain_days", "snow", "gust_days"]


def backtest(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    for yr in range(2022, 2027):
        tr = df[df.origin < f"{yr}-01-01"]
        te = df[(df.origin >= f"{yr}-01-01") & (df.origin < f"{yr + 1}-01-01")].copy()
        te["pred_naive"] = te["base"]
        for name, feats in (("pred_model", BASE_F), ("pred_model_wx", BASE_F + WX_F)):
            m = lgb.LGBMRegressor(n_estimators=400, learning_rate=0.03, num_leaves=15, min_child_samples=30,
                                  subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1, random_state=0)
            m.fit(tr[feats], tr["target"])
            te[name] = np.exp(m.predict(te[feats])) * (te["base"] + 1) - 1
        out.append(te)
    return pd.concat(out)


def alerts(iss: pd.DataFrame, w: pd.DataFrame) -> pd.DataFrame:
    rules = [  # (이름, 이슈, 기상 조건, 급증을 볼 기간: 조건 날짜 기준 며칠 뒤까지)
        ("폭염(최고 ≥ 32°C) → 소화전 민원", "폭염·소화전", w["is_hot"] == 1, (0, 1)),
        ("폭염 → 수돗물 민원", "수돗물", w["is_hot"] == 1, (0, 1)),
        ("적설 ≥ 2cm → 제설 민원 (1~2일 뒤)", "결빙·제설", w["is_snow"] == 1, (1, 2)),
        ("강수 ≥ 25mm → 침수 민원", "폭우·침수", w["is_heavy_rain"] == 1, (0, 1)),
        ("강수 ≥ 25mm 또는 돌풍 ≥ 60km/h → 수목 민원", "강풍·수목", (w["is_heavy_rain"] == 1) | (w["is_strong_gust"] == 1), (0, 1)),
    ]
    out = []
    for name, issue, cond, (lo, hi) in rules:
        s = iss[issue]
        med = s.rolling(28).median().shift(1)
        surge = (s >= 2 * med.clip(lower=1)) & (s >= 20)
        ev = cond.reindex(s.index).fillna(False)
        hit = pd.concat([surge.shift(-k) for k in range(lo, hi + 1)], axis=1).any(axis=1)
        caught = pd.concat([ev.shift(k) for k in range(lo, hi + 1)], axis=1).any(axis=1)
        out.append({"경보 규칙": name, "기상 조건 일수": int(ev.sum()), "급증 일수": int(surge.sum()),
                    "적중률(경보 후 실제 급증)": hit[ev].mean(), "포착률(급증 중 미리 경보)": caught[surge].mean()})
    return pd.DataFrame(out)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    a = pd.read_csv(ROOT / "data/processed/daily_agency_weather.csv", parse_dates=["date"])
    i = pd.read_csv(ROOT / "data/processed/daily_issue_weather.csv", parse_dates=["date"])
    w = pd.read_csv(ROOT / "data/processed/weather_features_daily.csv", parse_dates=["date"]).set_index("date")
    cnt = a.pivot(index="date", columns="agency", values="count")
    iss = i.pivot(index="date", columns="issue", values="count")

    df = build_rows(cnt, w)
    R = backtest(df)
    R.to_csv(OUT / "short_term_backtest.csv", index=False)
    print(f"=== 단기 예측 (평가 2022-01 ~ 2026-09, 월요일 {R.origin.nunique()}회 × 8개 부서)")
    for blk, label in ((1, "1~7일"), (2, "8~14일")):
        g = R[R.block == blk]
        t = pd.DataFrame({c: (g[c] - g.actual).abs() / g.actual.clip(lower=1) for c in ["pred_naive", "pred_model", "pred_model_wx"]})
        t["agency"] = g["agency"].astype(str).to_numpy()
        tab = t.groupby("agency")[["pred_naive", "pred_model", "pred_model_wx"]].mean()
        tab.loc["평균"] = tab.mean()
        tab.columns = ["최근 4주 평균", "모델(기상 없음)", "모델+관측 기상(상한)"]
        print(f"\n[{label}] 평균 오차(MAPE)")
        print(tab.map(lambda x: f"{x:.1%}").to_string())
        ev = (g.hot_days + g.rain_days + (g.snow >= 2) + g.gust_days) > 0
        te = t[ev.to_numpy()][["pred_naive", "pred_model", "pred_model_wx"]].mean()
        tn = t[~ev.to_numpy()][["pred_naive", "pred_model", "pred_model_wx"]].mean()
        print(f"  기상 이벤트 있는 기간({ev.mean():.0%}): " + ", ".join(f"{k} {v:.1%}" for k, v in te.items()))
        print("  기상 이벤트 없는 기간: " + ", ".join(f"{k} {v:.1%}" for k, v in tn.items()))

    A = alerts(iss, w)
    A.to_csv(OUT / "weather_alerts.csv", index=False)
    print("\n=== 기상 경보 적중률 (2016-02 ~ 2026-10, 관측 기상 기준)")
    print(A.to_string(index=False, formatters={"적중률(경보 후 실제 급증)": "{:.0%}".format, "포착률(급증 중 미리 경보)": "{:.0%}".format}))


if __name__ == "__main__":
    main()
