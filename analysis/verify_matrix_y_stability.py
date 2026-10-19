"""시연 리허설 보충: 매트릭스 세로축의 안정성.

리허설에서 세로축(현재 지연 중 비율 ÷ 평소)이 보건·소비자보호·노숙자·공원국에서 크게 출렁였습니다.
원인은 기준처리기간(P90)을 6~12개월 전 접수분으로 매달 다시 계산하는데, 몰아서 종결하는 부서는 이 값이 크게 뛰기 때문입니다.
세 후보를 비교합니다 (모두 매주 월요일 측정, ÷ 직전 52주 중앙값).
  A. 현재 정의: 지연 중 비율, 기준 = 6~12개월 전 접수분 P90 (매달)
  B. 장기 기준: 지연 중 비율, 기준 = 7~30개월 전 접수분 중 처리 완료된 민원의 P90 (분기마다, 최근 4개 분기 중앙값)
  C. 적체 배수: 처리 중 민원 수(최근 6개월 접수분) — 기준처리기간이 필요 없음
평가: 주간 흔들림, 0배·4배 넘는 비율, 다음 달 장기처리율과의 관계(부서 순위 상관), 상보성 결과.

실행: uv run python analysis/verify_matrix_y_stability.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
from verify_complementarity import AG, delay_ratio


def candidates(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    A = delay_ratio(df)
    mondays = A.index
    q_thr = {}
    for q in pd.period_range("2016Q4", "2026Q4", freq="Q"):
        s = q.start_time
        w = df[(df.created >= s - pd.DateOffset(months=30)) & (df.created < s - pd.DateOffset(months=7)) & (df.closed < s)]
        q_thr[q] = w.groupby("agency").proc_days.quantile(0.9)
    QT = pd.DataFrame(q_thr).T
    QT = QT.rolling(4, min_periods=1).median()
    B, C = {}, {}
    for m in mondays:
        thr = QT.loc[pd.Period(m, "Q")]
        w = df[(df.created >= m - pd.DateOffset(months=6)) & (df.created < m)]
        open_ = w.closed.isna() | (w.closed >= m)
        over = open_ & ((m - w.created).dt.total_seconds() / 86400 > w.agency.map(thr))
        B[m] = over.groupby(w.agency).mean()
        C[m] = open_.groupby(w.agency).sum()
    return {"A 현재 정의": A, "B 장기 기준 P90": pd.DataFrame(B).T[AG], "C 적체 배수": pd.DataFrame(C).T[AG].astype(float)}, QT


def main() -> None:
    df = pd.read_parquet(ROOT / "data/processed/complaint_features.parquet", columns=["created", "closed", "proc_days", "agency"])
    M = pd.read_csv(ROOT / "analysis/results/matrix_monthly.csv")
    cands, QT = candidates(df)
    print("=== B의 분기 기준처리기간(일), 2024~ :")
    print(QT.loc[pd.Period("2024Q1", "Q"):].round(0).iloc[::2].to_string())
    for name, raw in cands.items():
        y = raw / raw.rolling(52, min_periods=40).median().shift(1).clip(lower=1e-3 if "C" not in name else 1)
        y = y.loc["2018-01-01":]
        chg = np.log(y.clip(lower=0.05)).diff().abs().median().mean()
        zero = (y < 0.05).mean().mean()
        big = (y > 4).mean().mean()
        per_dept_jump = np.log(y.clip(lower=0.05)).diff().abs().median()
        # 다음 달 장기처리율과의 관계: 매달 1일 직전 월요일 값
        rows = []
        for mon in M.month.unique():
            t0 = pd.Timestamp(mon + "-01")
            k = y.index[y.index <= t0]
            if len(k):
                rows.append(pd.DataFrame({"month": mon, "agency": AG, "y": y.loc[k[-1], AG].to_numpy()}))
        J = M.merge(pd.concat(rows), on=["month", "agency"])
        rho = J.groupby("month").apply(lambda g: spearmanr(g.y, g.actual_rate).correlation, include_groups=False).mean()
        print(f"\n[{name}] 주간 흔들림(로그 변화 중앙값) {chg:.2f} | 0배 근처 {zero:.0%} | 4배 초과 {big:.0%} | "
              f"다음 달 장기처리율과 부서 순위 상관 {rho:.2f}")
        print("  부서별 주간 흔들림: " + ", ".join(f"{a} {v:.2f}" for a, v in per_dept_jump.items()))


if __name__ == "__main__":
    main()
