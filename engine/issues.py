"""한 달·분기 예상 이슈 — 이슈 달력 빈도와 겨울 적설 → 봄 도로 파손 (검증 ⑤, analysis/rehearsal_scenarios.py와 같은 정의)."""
import numpy as np
import pandas as pd

from engine.config import POTHOLE_FLAG_MULT, SURGE_MIN, SURGE_RATIO


def monthly_issues(iss: pd.DataFrame) -> pd.DataFrame:
    return iss.groupby(iss.index.to_period("M")).sum()


def calendar(mi: pd.DataFrame, asof: pd.Timestamp, months: list[pd.Period]) -> pd.DataFrame:
    """대상 월(달력 월)마다, 기준일 전 해들의 그 달 급증 여부 (해 단위 행). 확률은 API에서 기간에 맞게 묶어 계산."""
    m = mi[mi.index < asof.to_period("M")]
    base = m.rolling(12).mean().shift(1)
    surge = ((m / base >= SURGE_RATIO) & (m >= SURGE_MIN)).where(base.notna())
    rows = []
    for mon in sorted({p.month for p in months}):
        sel = surge[surge.index.month == mon]
        for issue in m.columns:
            s = sel[issue].dropna()
            for per, v in s.items():
                rows.append({"cal_month": mon, "issue": issue, "year": per.year, "surged": int(v)})
    return pd.DataFrame(rows)


def pothole_outlook(w: pd.DataFrame, mi: pd.DataFrame, asof: pd.Timestamp) -> dict | None:
    """3~4월 기준일에만: 지난 겨울(12~2월) 적설 → 3~4월 도로 파손 배수 (기준일 전 겨울들로 맞춘 로그 직선)."""
    if asof.month not in (3, 4):
        return None
    m = mi["도로 파손"]
    base = m.rolling(12).mean().shift(1)
    xs, ys = [], []
    for yr in range(2017, asof.year):
        xs.append(w.loc[f"{yr - 1}-12-01":f"{yr}-02-28", "snowfall_sum"].sum())
        ys.append(m.loc[[pd.Period(f"{yr}-03", "M"), pd.Period(f"{yr}-04", "M")]].mean() / base.loc[pd.Period(f"{yr}-03", "M")])
    b = np.polyfit(xs, np.log(ys), 1)
    snow = float(w.loc[f"{asof.year - 1}-12-01":f"{asof.year}-02-28", "snowfall_sum"].sum())
    mult = float(np.exp(np.polyval(b, snow)))
    pot_base = float(m[m.index < asof.to_period("M")].iloc[-12:].mean())   # 직전 12개월 월평균
    return {"snow_cm": snow, "mult": mult, "n_winters": len(xs), "pot_base": pot_base,
            "flag": mult >= POTHOLE_FLAG_MULT, "corr_note": "10개 겨울 순위상관 0.94"}
