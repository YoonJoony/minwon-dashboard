"""부서 상태 — 적체 배수, 최근 4주 일평균, 즉시 종결 비율 (리허설 검증 3장, analysis/verify_matrix_y_stability.py C안).

- 처리 중 민원 수: 매주 월요일, 최근 6개월 접수분 중 아직 처리 중인 민원 수
  (종결일이 없거나 그 뒤이거나, 종결일이 적혀 있어도 상태가 아직 '처리 중'인 민원. 건축국은 처리 중 민원에도 종결일이 적힌 경우가 많음)
- 적체 배수: 처리 중 민원 수 ÷ 직전 52주(월요일) 중앙값
- 기준일 값은 기준일 또는 그 직전 월요일의 측정값
"""
import pandas as pd

from engine.config import AGENCIES

D = pd.Timedelta


def weekly_backlog(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """월요일마다 부서별 처리 중 민원 수."""
    out = {}
    for m in pd.date_range(start, end, freq="W-MON"):
        w = df[(df.created >= m - pd.DateOffset(months=6)) & (df.created < m)]
        out[m] = (w.closed.isna() | (w.closed >= m) | (w.status != "Closed")).groupby(w.agency).sum()
    return pd.DataFrame(out).T.reindex(columns=AGENCIES).astype(float)


def backlog_multiple(weekly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    normal = weekly.rolling(52, min_periods=40).median().shift(1).clip(lower=1)
    return weekly / normal, normal


def dept_state(asof: pd.Timestamp, cnt: pd.DataFrame, weekly: pd.DataFrame, mult: pd.DataFrame, normal: pd.DataFrame,
               df: pd.DataFrame) -> pd.DataFrame:
    monday = weekly.index[weekly.index <= asof][-1]
    recent = cnt.loc[asof - D(days=28): asof - D(days=1)].mean()
    last12 = df[(df.created >= asof - pd.DateOffset(months=12)) & (df.created < asof)]
    inst = last12.groupby("agency").instant.mean()
    return pd.DataFrame({
        "agency": AGENCIES, "recent_day": recent.reindex(AGENCIES).to_numpy(),
        "backlog_open": weekly.loc[monday, AGENCIES].to_numpy(), "backlog_normal": normal.loc[monday, AGENCIES].to_numpy(),
        "backlog_multiple": mult.loc[monday, AGENCIES].to_numpy(), "instant_share": inst.reindex(AGENCIES).fillna(0).to_numpy(),
        "backlog_monday": monday,
    })


def dow_weights(cnt: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
    """직전 8주 요일별 상대 비율 (일 단위로 나눌 때 씀). 행: 요일 0~6, 열: 부서."""
    h = cnt.loc[asof - D(days=56): asof - D(days=1)]
    w = h.groupby(h.index.dayofweek).mean()
    return (w / w.mean()).reindex(range(7)).fillna(1.0)
