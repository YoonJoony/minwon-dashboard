"""10년치 검증 ⑧: 부서 간 상보성 — 과부하 부서와 지원 가능 부서가 같은 날(같은 주) 동시에 있었나.

기획안 정의를 그대로 씁니다.
- 접수 증가율 x: 그날 접수(즉시 종결 제외) ÷ 직전 4주 같은 요일 평균 − 1   (주 단위: 그 주 ÷ 직전 4주 평균 − 1)
- 지연 배수 y: 현재 지연 중 비율 ÷ 부서 평소(직전 52주 중앙값)
  현재 지연 중 비율 = 최근 6개월 접수분 중 기준처리기간(부서별 P90, 매달 재계산)을 넘기고도 처리 중인 비율 (매주 월요일 측정)
- 과부하(집중관리): x ≥ +10% 이고 y ≥ 1.5
- 지원 가능(여유): x ≤ −10% 이고 y < 1.5 (평소보다 접수가 적고 밀린 일도 많지 않음)

흡수 가능성: 과부하 부서의 초과 업무(초과 접수 × 적체 전환율)를 지원 가능 부서의 여유(평소 − 실제 접수)로 메울 수 있는지.
평가 기간: 2018-01 ~ 2026-10 (앞의 2년은 기준값 계산에 사용).

실행: uv run python analysis/verify_complementarity.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
AG = ["DCWP", "DEP", "DHS", "DOB", "DOHMH", "DOT", "DPR", "DSNY"]
NAME = {"DCWP": "소비자보호", "DEP": "환경보호", "DHS": "노숙자", "DOB": "건축", "DOHMH": "보건",
        "DOT": "교통", "DPR": "공원", "DSNY": "위생"}
# 적체 전환율: verify_capacity.py 결과 (보건국은 처리 기록이 고르지 않아 보수적으로 1.0)
CONV = {"DHS": 0.11, "DEP": 0.17, "DOT": 0.27, "DCWP": 0.28, "DSNY": 0.51, "DPR": 0.66, "DOB": 0.75, "DOHMH": 1.0}
NEVER = 1e6


def delay_ratio(df: pd.DataFrame) -> pd.DataFrame:
    """매주 월요일: 부서별 현재 지연 중 비율."""
    out = {}
    thr_cache = {}
    for m in pd.date_range("2017-01-02", "2026-10-05", freq="W-MON"):
        key = (m.year, m.month)
        if key not in thr_cache:
            ms = pd.Timestamp(m.year, m.month, 1)
            w = df[(df.created >= ms - pd.DateOffset(months=12)) & (df.created < ms - pd.DateOffset(months=6))]
            thr = w.proc_days.where(w.closed < ms, NEVER).groupby(w.agency).quantile(0.9)
            fb = w[w.closed < ms].groupby("agency").proc_days.quantile(0.9)
            thr_cache[key] = thr.where(thr < NEVER, fb)
        thr = thr_cache[key]
        w = df[(df.created >= m - pd.DateOffset(months=6)) & (df.created < m)]
        open_ = w.closed.isna() | (w.closed >= m)
        over = open_ & ((m - w.created).dt.total_seconds() / 86400 > w.agency.map(thr))
        out[m] = over.groupby(w.agency).mean()
    return pd.DataFrame(out).T.reindex(columns=AG)


def classify(x: pd.DataFrame, y: pd.DataFrame) -> pd.DataFrame:
    s = pd.DataFrame("안정", index=x.index, columns=x.columns)
    s[(x >= 0.10) & (y < 1.5)] = "접수증가 주의"
    s[(x < 0.10) & (y >= 1.5)] = "처리지연 주의"
    s[(x >= 0.10) & (y >= 1.5)] = "집중관리"
    s[(x <= -0.10) & (y < 1.5)] = "지원 가능"
    return s.where(x.notna() & y.notna())


def report(label: str, s: pd.DataFrame, intake: pd.DataFrame, base: pd.DataFrame) -> None:
    over = s.eq("집중관리")
    sup = s.eq("지원 가능")
    has_over = over.any(axis=1)
    n = int(has_over.sum())
    both = has_over & sup.any(axis=1)
    need = ((intake - base).clip(lower=0) * pd.Series(CONV)).where(over).sum(axis=1)
    raw_need = (intake - base).clip(lower=0).where(over).sum(axis=1)
    slack = (base - intake).clip(lower=0).where(sup).sum(axis=1)
    cov = (slack / need.replace(0, np.nan)).clip(upper=1)[has_over]
    cov_raw = (slack / raw_need.replace(0, np.nan)).clip(upper=1)[has_over]
    print(f"\n=== [{label}] 평가 {s.index.min():%Y-%m} ~ {s.index.max():%Y-%m}, {len(s):,}개 중 과부하 부서가 있었던 {n:,}개")
    print(f"  과부하 부서가 있던 {label} 중 지원 가능 부서가 동시에 있었던 비율: {both.sum() / n:.0%}")
    print(f"  그때 지원 가능 부서 수 평균: {sup[has_over].sum(axis=1).mean():.1f}개")
    print(f"  과부하 초과 업무(적체 전환율 반영)를 지원 가능 부서 여유로 메울 수 있었던 비율: 평균 {cov.mean():.0%}, 전부 메운 경우 {(cov >= 1).mean():.0%}")
    print(f"  (적체 전환율 미반영, 초과 접수 전체 기준: 평균 {cov_raw.mean():.0%}, 전부 메운 경우 {(cov_raw >= 1).mean():.0%})")
    print("  과부하가 잦은 부서(횟수 기준):", ", ".join(f"{NAME[k]} {v:.0%}" for k, v in (over.sum() / over.sum().sum()).sort_values(ascending=False).head(4).items()))
    excess = ((intake - base).clip(lower=0) * pd.Series(CONV)).where(over).sum()
    print("  과부하 초과 업무가 큰 부서(건수 기준):", ", ".join(f"{NAME[k]} {v:.0%}" for k, v in (excess / excess.sum()).sort_values(ascending=False).head(4).items()))
    print(f"  부서×{label} 중 집중관리 비율: {over.sum().sum() / over.notna().sum().sum():.1%}")
    pairs = {}
    for t in over.index[has_over]:
        for a in over.columns[over.loc[t]]:
            for b in sup.columns[sup.loc[t]]:
                pairs[(a, b)] = pairs.get((a, b), 0) + 1
    top = sorted(pairs.items(), key=lambda kv: -kv[1])[:5]
    print("  자주 나온 짝(과부하 → 지원 가능):", ", ".join(f"{NAME[a]}→{NAME[b]} {c}회" for (a, b), c in top))
    print("  계절별 동시 존재 비율:", ", ".join(
        f"{q} {both[has_over & (s.index.month.isin(ms))].sum() / max((has_over & s.index.month.isin(ms)).sum(), 1):.0%}"
        for q, ms in (("겨울", [12, 1, 2]), ("봄", [3, 4, 5]), ("여름", [6, 7, 8]), ("가을", [9, 10, 11]))))


def main() -> None:
    df = pd.read_parquet(ROOT / "data/processed/complaint_features.parquet",
                         columns=["created", "closed", "proc_days", "agency", "instant"])
    dr = delay_ratio(df)
    normal = dr.rolling(52, min_periods=40).median().shift(1)
    y_week = dr / normal.clip(lower=0.005)

    real = df[~df.instant]
    daily = real.groupby([real.created.dt.normalize(), "agency"]).size().unstack(fill_value=0)
    daily = daily.reindex(pd.date_range("2016-01-01", "2026-10-11"), fill_value=0)[AG]
    base_d = sum(daily.shift(7 * k) for k in (1, 2, 3, 4)) / 4          # 직전 4주 같은 요일 평균
    x_d = daily / base_d.replace(0, np.nan) - 1
    y_d = y_week.reindex(daily.index).ffill(limit=6)
    sel = daily.index >= "2018-01-01"
    s_d = classify(x_d[sel], y_d[sel])
    report("일", s_d, daily[sel], base_d[sel])

    weekly = daily.resample("W-MON", label="left", closed="left").sum()
    weekly = weekly[weekly.index <= "2026-09-28"]
    base_w = weekly.rolling(4).mean().shift(1)
    x_w = weekly / base_w - 1
    y_w = y_week.reindex(weekly.index)
    selw = weekly.index >= "2018-01-01"
    s_w = classify(x_w[selw], y_w[selw])
    report("주", s_w, weekly[selw], base_w[selw])
    s_w.to_csv(ROOT / "analysis/results/complementarity_weekly_status.csv")

    print("\n=== 사례: 과부하 부서가 가장 많았던 주")
    cnt = s_w.eq("집중관리").sum(axis=1).sort_values(ascending=False).head(5)
    for t in cnt.index:
        o = [NAME[a] for a in AG if s_w.loc[t, a] == "집중관리"]
        sp = [NAME[a] for a in AG if s_w.loc[t, a] == "지원 가능"]
        print(f"  {t:%Y-%m-%d} 주: 집중관리 {', '.join(o)} | 지원 가능 {', '.join(sp) or '없음'}")


if __name__ == "__main__":
    main()
