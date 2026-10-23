"""단기 예측: 시기 입력 방식 비교 (docs/woy_sin_cos_conversion.md).

sin+cos(지금), sin만, cos만, 반년 주기 sin+cos, 일차(day of year), 시기 없음. LightGBM seed 0, verify_short_term.py와 같은 백테스트.

실행: uv run python analysis/compare_season_encoding.py
"""
import sys
sys.path.insert(0, "analysis")
import lightgbm as lgb, numpy as np, pandas as pd
from verify_short_term import build_rows, ROOT
a = pd.read_csv(ROOT/"data/processed/daily_agency_weather.csv", parse_dates=["date"])
w = pd.read_csv(ROOT/"data/processed/weather_features_daily.csv", parse_dates=["date"]).set_index("date")
cnt = a.pivot(index="date", columns="agency", values="count")
# seasonal pattern: monthly mean daily count / annual mean, 2017-2025
c = cnt.loc["2017":"2025"]
m = c.groupby(c.index.month).mean() / c.mean()
print(m.round(2).to_string())
df = build_rows(cnt, w)
doy = (pd.to_datetime(df.origin) + pd.to_timedelta((df.block-1)*7, unit="D")).dt.dayofyear
df["doy"] = doy
df["half_sin"] = np.sin(4*np.pi*doy/365.25); df["half_cos"] = np.cos(4*np.pi*doy/365.25)
core = ["agency","block","r7_r28","season_ratio","holidays"]
V = {"both (now)": ["woy_sin","woy_cos"], "sin only": ["woy_sin"], "cos only": ["woy_cos"],
     "half-year sin+cos": ["half_sin","half_cos"], "day number": ["doy"], "none": []}
for name, extra in V.items():
    f = core+extra; out=[]
    for yr in range(2022,2027):
        tr=df[df.origin<f"{yr}-01-01"]; te=df[(df.origin>=f"{yr}-01-01")&(df.origin<f"{yr+1}-01-01")].copy()
        mdl=lgb.LGBMRegressor(n_estimators=400,learning_rate=0.03,num_leaves=15,min_child_samples=30,subsample=0.8,subsample_freq=1,colsample_bytree=0.8,verbose=-1,random_state=0).fit(tr[f],tr.target)
        te["p"]=np.exp(mdl.predict(te[f]))*(te.base+1)-1; out.append(te)
    R=pd.concat(out); r=[]
    for blk in (1,2):
        g=R[R.block==blk]; e=(g.p-g.actual).abs()/g.actual.clip(lower=1)
        r.append(e.groupby(g.agency.astype(str),observed=True).mean().mean())
    g=R[(R.block==1)&(R.actual>0)]; e=(g.p-g.actual).abs()/g.actual
    print(f"{name:18s} d1-7 {r[0]:.2%}  d8-14 {r[1]:.2%}  d1-7 excl0 {e.groupby(g.agency.astype(str),observed=True).mean().mean():.2%}")
