"""화면 계산 — 선택 기간 예측 합산, 2×2 매트릭스, 인력 지원. API와 빌드 검증이 함께 씁니다.

입력은 사전 계산 결과(기준일 하나의 표들)이고, 요청 때마다 빠르게 계산합니다.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from engine.config import AGENCIES, CONV, SHORT_DAYS, SUPPORT_X, X_TH, Y_TH

D = pd.Timedelta
QUADRANTS = ["집중관리", "처리지연 주의", "접수증가 주의", "안정", "지원 가능"]


@dataclass
class AsofData:
    """기준일 하나에 대한 사전 계산 결과."""
    asof: pd.Timestamp
    forecast_daily: pd.DataFrame     # agency, date, source(short/long), pred
    intervals: pd.DataFrame          # agency, source, block, lo_ratio, hi_ratio
    affected: pd.DataFrame           # agency, flag, level, reason, factor, start, end, extra_per_day
    state: pd.DataFrame              # agency, recent_day, backlog_open, backlog_normal, backlog_multiple, instant_share


def quadrant(x: float, y: float) -> str:
    if x <= SUPPORT_X and y < Y_TH:
        return "지원 가능"
    if x >= X_TH:
        return "집중관리" if y >= Y_TH else "접수증가 주의"
    return "처리지연 주의" if y >= Y_TH else "안정"


def period_forecast(a: AsofData, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """부서별 기간 예측 합계와 80% 범위, 특보 표시. 14일 안이면 단기, 넘으면 월별 방식."""
    use_short = end <= a.asof + D(days=SHORT_DAYS - 1)
    src = "short" if use_short else "long"
    block = (1 if end <= a.asof + D(days=6) else 2) if use_short else 0
    fd = a.forecast_daily[(a.forecast_daily.source == src) & (a.forecast_daily.date >= start) & (a.forecast_daily.date <= end)]
    pred = fd.groupby("agency").pred.sum().reindex(AGENCIES)
    iv = a.intervals[(a.intervals.source == src) & (a.intervals.block == block)].set_index("agency").reindex(AGENCIES)
    out = pd.DataFrame({"agency": AGENCIES, "pred": pred.to_numpy(), "lo": (pred * iv.lo_ratio).to_numpy(),
                        "hi": (pred * iv.hi_ratio).to_numpy(), "source": src, "flag": "", "flag_reason": "", "flag_level": 0})
    out = out.set_index("agency")
    for r in a.affected.itertuples():
        s, e = max(start, r.start), min(end, r.end)
        if s > e:
            continue
        days_in = fd[(fd.agency == r.agency) & (fd.date >= s) & (fd.date <= e)]
        if r.flag == "기상 특보":
            widened = out.at[r.agency, "pred"] + (r.factor - 1) * days_in.pred.sum()
            out.at[r.agency, "hi"] = max(out.at[r.agency, "hi"], widened)
        else:
            out.at[r.agency, "hi"] = out.at[r.agency, "hi"] + r.extra_per_day * ((e - s).days + 1)
        out.at[r.agency, "flag"] = r.flag if not out.at[r.agency, "flag"] else out.at[r.agency, "flag"] + " · " + r.flag
        out.at[r.agency, "flag_reason"] = r.reason
        out.at[r.agency, "flag_level"] = max(int(out.at[r.agency, "flag_level"]), int(r.level))
    return out.reset_index()


def matrix(a: AsofData, start: pd.Timestamp, end: pd.Timestamp, actual: pd.Series | None = None) -> pd.DataFrame:
    """부서별 매트릭스 값. actual(부서별 기간 실제 합계)이 있으면 실제 위치도."""
    days = (end - start).days + 1
    pf = period_forecast(a, start, end).set_index("agency")
    st = a.state.set_index("agency").reindex(AGENCIES)
    base = st.recent_day * days
    m = pd.DataFrame({
        "pred": pf.pred, "lo": pf.lo, "hi": pf.hi, "source": pf.source, "flag": pf.flag, "flag_reason": pf.flag_reason,
        "flag_level": pf.flag_level, "base": base, "x": pf.pred / base - 1, "x_lo": pf.lo / base - 1, "x_hi": pf.hi / base - 1,
        "y": st.backlog_multiple, "backlog_open": st.backlog_open, "backlog_normal": st.backlog_normal,
        "instant_share": st.instant_share, "recent_day": st.recent_day,
    })
    m["quadrant"] = [quadrant(r.x, r.y) for r in m.itertuples()]
    m.loc[(m.flag != "") & (m.quadrant == "지원 가능"), "quadrant"] = "안정"    # 특보 영향 부서는 지원 후보에서 제외
    if actual is not None:
        m["actual"] = actual.reindex(AGENCIES)
        m["x_actual"] = m.actual / base - 1
        m["quadrant_actual"] = [quadrant(r.x_actual, r.y) for r in m.itertuples()]
        m["in_range"] = (m.actual >= m.lo) & (m.actual <= m.hi)
    return m.reset_index()


def staffing(m: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, per_person_day: float) -> dict:
    """적체 증가 예상(지원 필요)과 지원 가능 부서의 여유, 짝짓기."""
    workdays = len(pd.bdate_range(start, end))
    t = m.set_index("agency")
    need = ((t.pred - t.base).clip(lower=0) * (1 - t.instant_share) * pd.Series(CONV)).where(t.x >= X_TH, 0)
    slack = (t.base - t.pred).clip(lower=0).where(t.quadrant == "지원 가능", 0)
    needs = [{"agency": ag, "excess": float(t.at[ag, "pred"] - t.at[ag, "base"]), "conv": CONV[ag],
              "instant_share": float(t.at[ag, "instant_share"]), "need": float(v),
              "people": float(v / (per_person_day * workdays)) if workdays else 0.0, "quadrant": t.at[ag, "quadrant"],
              "flag": t.at[ag, "flag"]} for ag, v in need.sort_values(ascending=False).items() if v >= 1]
    supports = [{"agency": ag, "slack": float(v), "people": float(v / (per_person_day * workdays)) if workdays else 0.0}
                for ag, v in slack.sort_values(ascending=False).items() if v >= 1]
    pairs, left = [], {s["agency"]: s["slack"] for s in supports}
    for n in needs:
        remain = n["need"]
        for s in supports:
            if remain <= 0:
                break
            give = min(remain, left[s["agency"]])
            if give >= 1:
                pairs.append({"from": s["agency"], "to": n["agency"], "amount": float(give),
                              "people": float(give / (per_person_day * workdays)) if workdays else 0.0})
                left[s["agency"]] -= give
                remain -= give
        n["covered"] = float(n["need"] - max(remain, 0))
    total_need = float(sum(n["need"] for n in needs))
    covered = float(sum(n["covered"] for n in needs))
    return {"workdays": workdays, "per_person_day": per_person_day, "needs": needs, "supports": supports, "pairs": pairs,
            "total_need": total_need, "total_people": float(total_need / (per_person_day * workdays)) if workdays else 0.0,
            "covered": covered, "coverage": covered / total_need if total_need > 0 else np.nan}
