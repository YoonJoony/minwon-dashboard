"""10년치 검증 ⑤: 한 달·분기 앞 예상 건수 (방법 비교, 80% 예측 범위 포함률).

예측 시점까지 알려진 월(분기) 건수만 사용. 평가 2022-01 ~ 2026-09.
실행: uv run python analysis/verify_long_term.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import numpy as np
import pandas as pd

pd.set_option("display.width", 220)
a = pd.read_csv(ROOT / "data/processed/daily_agency_weather.csv", parse_dates=["date"])
a = a[a.date < "2026-10-01"]

def backtest(freq, test_from, hist_start_eval):
    s = a.groupby([a.date.dt.to_period(freq), "agency"])["count"].sum().unstack()
    P = 12 if freq == "M" else 4
    idx = list(s.index)
    rows = []
    for t in range(len(idx)):
        if idx[t] < pd.Period(hist_start_eval, freq): continue
        hist = s.iloc[:t]                       # 예측 시점까지 알려진 데이터
        for ag in s.columns:
            y = hist[ag]; act = s.iloc[t][ag]; pos = idx[t].month if freq == "M" else idx[t].quarter
            # 계절 지수: 과거 각 해의 (그 기간 / 그 해 12개월 평균)
            def seas(excl_covid):
                ratios = []
                for k in range(1, 8):
                    j = t - k * P
                    if j - P // 2 < 0 or j + P // 2 > len(hist): continue
                    if excl_covid and idx[j].year in (2020, 2021): continue
                    win = y.iloc[max(0, j - P // 2): j + P // 2 + (P % 2)]
                    if len(win) < P: continue
                    ratios.append(y.iloc[j] / win.mean())
                return np.median(ratios) if ratios else np.nan, len(ratios)
            si, n_si = seas(False); si_x, _ = seas(True)
            # 직전 3기간(분기는 2기간) 탈계절 수준
            k_recent = 3 if freq == "M" else 2
            def deseas_level(excl):
                vals = []
                for r in range(1, k_recent + 1):
                    tt = t - r; save = []
                    for k in range(1, 8):
                        j = tt - k * P
                        if j - P // 2 < 0: continue
                        if excl and idx[j].year in (2020, 2021): continue
                        win = y.iloc[max(0, j - P // 2): j + P // 2 + (P % 2)]
                        if len(win) == P: save.append(y.iloc[j] / win.mean())
                    if save: vals.append(y.iloc[tt] / np.median(save))
                return np.mean(vals) if vals else np.nan
            f = {
                "작년같은기간": y.iloc[t - P],
                "최근평균": y.iloc[t - k_recent:t].mean(),
                "계절지수x최근12": y.iloc[t - P:t].mean() * si,
                "계절지수x최근수준": deseas_level(False) * si,
                "계절지수x최근수준(코로나제외)": deseas_level(True) * si_x,
            }
            for name, v in f.items():
                rows.append(dict(period=str(idx[t]), year=idx[t].year, agency=ag, method=name, pred=v, act=act, n_years=n_si))
    R = pd.DataFrame(rows); R["ape"] = (R.pred - R.act).abs() / R.act; R["logerr"] = np.log(R.act / R.pred)
    return R, test_from

for freq, test_from, start in [("M", "2022-01", "2018-01"), ("Q", "2022Q1", "2018Q1")]:
    R, tf = backtest(freq, test_from, start)
    T = R[R.period >= tf]
    print(f"\n===== {'한 달' if freq=='M' else '분기'} 앞 예측, 평가 {tf} ~ 2026-09 ({T.period.nunique()}개 기간), 기관별 MAPE")
    tab = T.pivot_table(index="agency", columns="method", values="ape", aggfunc="mean")
    tab.loc["평균"] = tab.mean()
    print(tab.map(lambda x: f"{x:.0%}").to_string())
    # 80% 범위: 같은 기관의 과거 오차(log)의 10~90% 분위, 테스트 전 기간까지만 사용
    best = "계절지수x최근수준(코로나제외)"
    B = R[R.method == best].sort_values("period").copy()
    cov = []
    for ag, g in B.groupby("agency"):
        g = g.reset_index(drop=True)
        for i_, r in g.iterrows():
            if r.period < tf: continue
            past = g.loc[:i_ - 1, "logerr"].dropna()
            if len(past) < 8: continue
            lo, hi = np.quantile(past, [.1, .9])
            cov.append(dict(agency=ag, inside=(lo <= r.logerr <= hi), width=np.exp(hi) - np.exp(lo)))
    C = pd.DataFrame(cov).groupby("agency").agg(포함률=("inside", "mean"), 범위폭=("width", "mean"))
    print(f"--- '{best}' 80% 예측 범위: 실제값 포함률과 평균 폭(예측값 대비)")
    print(C.map(lambda x: f"{x:.0%}").to_string())
    # 연도별 MAPE (구조 변화 확인)
    print("--- 연도별 MAPE (최선 방법)")
    print(T[T.method == best].pivot_table(index="agency", columns="year", values="ape", aggfunc="mean").map(lambda x: f"{x:.0%}").to_string())
