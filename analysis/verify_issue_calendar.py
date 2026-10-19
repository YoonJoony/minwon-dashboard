"""10년치 검증 ⑥: 월별 이슈 급증 빈도(이슈 달력), 빈도의 예측력, 겨울 적설 → 봄 도로 파손.

실행: uv run python analysis/verify_issue_calendar.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

pd.set_option("display.width", 250)
i = pd.read_csv(ROOT / "data/processed/daily_issue_weather.csv", parse_dates=["date"])
w = pd.read_csv(ROOT / "data/processed/weather_features_daily.csv", parse_dates=["date"])
i = i[(i.date < "2026-10-01") & (i.issue != "기타")]
m = i.groupby([i.date.dt.to_period("M"), "issue"])["count"].sum().unstack().fillna(0)
base = m.rolling(12).mean().shift(1)                 # 직전 12개월 월평균 (예측 시점에 알 수 있는 값)
ratio = m / base
SURGE, MINC = 1.5, 30
surge = ((ratio >= SURGE) & (m >= MINC)).astype(float).where(base.notna())

print(f"=== 이슈 급증 정의: 그 달 건수 ≥ 직전 12개월 월평균 × {SURGE}, 그리고 {MINC}건 이상")
print("=== 달력: 2017~2025년(9년) 중 그 달에 급증한 해의 수")
S9 = surge[(surge.index >= pd.Period("2017-01", "M")) & (surge.index <= pd.Period("2025-12", "M"))]
cal = S9.groupby(S9.index.month).sum().astype(int)
cal.index = [f"{x}월" for x in cal.index]
print(cal.T.to_string())

# 예측력: 그 해 이전 해들의 같은 달 급증 빈도로 이번 해 급증을 예측 (빈도 ≥ 0.5면 '급증 예상')
print("\n=== 예측력 검증 (평가 2021-01 ~ 2026-09)")
rows = []
for p in surge.index[surge.index >= pd.Period("2021-01", "M")]:
    prev = surge[(surge.index.month == p.month) & (surge.index < p)].dropna(how="all")
    if len(prev) < 3: continue
    for iss in surge.columns:
        if np.isnan(surge.loc[p, iss]): continue
        rows.append(dict(period=p, issue=iss, actual=surge.loc[p, iss],
                         freq=prev[iss].mean(), last_year=prev[iss].iloc[-1], n_prev=len(prev)))
R = pd.DataFrame(rows)
def pr(pred, act):
    tp = ((pred == 1) & (act == 1)).sum(); fp = ((pred == 1) & (act == 0)).sum(); fn = ((pred == 0) & (act == 1)).sum()
    return tp / max(tp + fp, 1), tp / max(tp + fn, 1), int(tp + fn), int(tp + fp)
for name, pred in [("작년 같은 달 급증 (2년치 방식)", R.last_year), ("과거 빈도 ≥ 50% (10년치 방식)", (R.freq >= .5).astype(float)),
                   ("과거 빈도 ≥ 70%", (R.freq >= .7).astype(float))]:
    p_, r_, n_act, n_pred = pr(pred, R.actual)
    print(f"  {name:28s} 정밀도 {p_:.0%}  재현율 {r_:.0%}  (실제 급증 {n_act}건, 예상 {n_pred}건)")
print("  과거 빈도 구간별 실제 급증 비율 (빈도가 확률처럼 맞는지):")
R["bin"] = pd.cut(R.freq, [-.01, .1, .3, .5, .7, 1.0], labels=["0~10%", "10~30%", "30~50%", "50~70%", "70~100%"])
print(R.groupby("bin", observed=True).agg(건수=("actual", "size"), 실제급증비율=("actual", "mean")).round(2).to_string())

print("\n=== 이슈별: 과거 빈도 ≥ 50%로 예상했을 때 맞힌 비율 / 놓친 급증")
for iss, g in R.groupby("issue"):
    p_, r_, n_act, n_pred = pr((g.freq >= .5).astype(float), g.actual)
    print(f"  {iss:6s} 예상 {n_pred:2d}회 중 적중 {p_:.0%} | 실제 급증 {n_act:2d}회 중 사전 예상 {r_:.0%}")

# 연쇄 패턴: 겨울(12~2월) 적설 합계 → 봄(3~4월) 도로 파손 배수
print("\n=== 겨울 적설 → 이듬해 3~4월 도로 파손")
W = w.set_index("date")
out = []
for yr in range(2017, 2027):
    snow = W.loc[f"{yr-1}-12-01":f"{yr}-02-28", "snowfall_sum"].sum()
    spring = m.loc[[pd.Period(f"{yr}-03", "M"), pd.Period(f"{yr}-04", "M")], "도로 파손"].mean()
    bl = base.loc[pd.Period(f"{yr}-03", "M"), "도로 파손"]
    out.append((f"{yr-1}/{str(yr)[2:]}", round(snow, 1), round(spring / bl, 2)))
O = pd.DataFrame(out, columns=["겨울", "적설합계cm", "3~4월 도로파손 배수"])
print(O.to_string(index=False)); print("  순위상관:", round(spearmanr(O.iloc[:, 1], O.iloc[:, 2]).correlation, 2))
# 결빙 발생 해 비율 (월별, 적설 기준)
print("\n=== 월별 적설일(≥2cm)이 있었던 해 (2016~2026 겨울)")
W["ym"] = W.index.to_period("M")
sd = W.groupby("ym").is_snow.sum()
for mo in [11, 12, 1, 2, 3, 4]:
    v = sd[sd.index.month == mo]
    print(f"  {mo:2d}월: {int((v>0).sum())}/{len(v)}년 (평균 {v.mean():.1f}일)")
