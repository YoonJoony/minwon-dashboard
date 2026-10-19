"""한 달·분기(15~92일) 부서별 접수 건수 예측 — 계절 지수 × 최근 수준 (검증 ①, analysis/rehearsal_scenarios.py와 같은 정의).

- 계절 지수: 과거 최대 7년의 "그 달 ÷ 그 달을 가운데 둔 12개월 평균"의 중앙값
- 최근 수준: 직전 3개월(완료된 달)의 "실적 ÷ 계절 지수" 평균
- 80% 범위: 같은 방식으로 한 달 앞을 예측했을 때의 과거 오차(2019년~) 10~90% 지점
"""
import numpy as np
import pandas as pd

from engine.config import AGENCIES


def monthly(cnt: pd.DataFrame) -> pd.DataFrame:
    return cnt.groupby(cnt.index.to_period("M")).sum()


def _season_index(y: pd.Series, per: pd.Period, asof_m: pd.Period) -> float:
    r = []
    for k in range(1, 8):
        p = per - 12 * k
        if p - 6 in y.index and p + 5 in y.index and p + 5 < asof_m:
            win = y.loc[p - 6: p + 5]
            if len(win) == 12:
                r.append(y.loc[p] / win.mean())
    return float(np.median(r)) if r else np.nan


def seasonal_pred(mo: pd.DataFrame, target_months: list, asof: pd.Timestamp) -> pd.DataFrame:
    """부서 × 대상 월 예측. 기준일이 속한 달 이전의 완료된 달만 씀."""
    asof_m = asof.to_period("M")
    known = mo[mo.index < asof_m]
    out = {}
    for ag in AGENCIES:
        y = known[ag]
        last = y.index[-1]
        level = np.mean([y.loc[last - r] / _season_index(y, last - r, asof_m) for r in range(3)])
        out[ag] = {p: level * _season_index(y, p, asof_m) for p in target_months}
    return pd.DataFrame(out).T


def walk_forward(mo: pd.DataFrame, start: str = "2019-01") -> pd.DataFrame:
    """2019년부터 매달 '그달 1일 기준 그달 예측'과 실적. 80% 범위 계산용."""
    last_full = mo.index[-2]                     # 마지막 달은 일부만 있을 수 있어 제외
    rows = []
    for t in pd.period_range(start, last_full, freq="M"):
        p = seasonal_pred(mo, [t], t.to_timestamp())[t]
        for ag in AGENCIES:
            rows.append({"month": t, "agency": ag, "pred": p[ag], "actual": mo.loc[t, ag]})
    return pd.DataFrame(rows)


def interval_ratios(wf: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
    """기준일 직전 달까지의 한 달 앞 예측 오차 → 부서별 실제÷예측 10%·90% 지점."""
    past = wf[wf.month <= (asof - pd.DateOffset(months=1)).to_period("M")]
    err = np.log(past.actual / past.pred).groupby(past.agency).quantile([0.1, 0.9]).unstack()
    return pd.DataFrame({"agency": err.index, "block": 0, "lo_ratio": np.exp(err[0.1]).to_numpy(),
                         "hi_ratio": np.exp(err[0.9]).to_numpy()})
