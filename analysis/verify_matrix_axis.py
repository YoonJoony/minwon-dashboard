"""10년치 검증 ①-보충: 매트릭스 세로축 대안과 사분면 기준.

미래 기간의 장기처리율을 '예상 유형 구성'으로 추정하는 방법은 약했으므로(verify_risk.py),
**지금 이미 지연되고 있는 비율**(그 달 1일 기준, 최근 6개월 접수분 중 기준처리기간을 넘기고도 처리 중인 비율)이
다음 기간의 장기처리율을 더 잘 가리키는지 비교합니다. 사분면 기준은 부서별 평소 수준 대비 배수로도 봅니다.

입력: analysis/results/matrix_monthly.csv, risk_thresholds.csv (verify_risk.py 결과)
실행: uv run python analysis/verify_matrix_axis.py
"""
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "analysis/results"


def main() -> None:
    df = pd.read_parquet(ROOT / "data/processed/complaint_features.parquet", columns=["created", "closed", "agency"])
    M = pd.read_csv(RES / "matrix_monthly.csv")
    thr = pd.read_csv(RES / "risk_thresholds.csv", index_col=0)
    cur = []
    for m in thr.columns:
        t0 = pd.Timestamp(m + "-01")
        w = df[(df.created >= t0 - pd.DateOffset(months=6)) & (df.created < t0)]
        open_ = w.closed.isna() | (w.closed >= t0)
        elapsed = (t0 - w.created).dt.total_seconds() / 86400
        over = open_ & (elapsed > w.agency.map(thr[m]))
        r = over.groupby(w.agency).mean()
        for ag, v in r.items():
            cur.append({"month": m, "agency": ag, "current_delay": v})
    M = M.merge(pd.DataFrame(cur), on=["month", "agency"], how="left").dropna(subset=["actual_rate"])
    M.to_csv(RES / "matrix_monthly.csv", index=False)

    print("=== 세로축 후보별: 그 달 실제 장기처리율과의 부서 순위 상관 (월별 평균, 2022-01 ~ 2026-03)")
    for col, name in (("pred_rate", "예상 유형 구성 × 유형별 장기처리율"), ("naive_rate", "부서 과거 장기처리율"),
                      ("current_delay", "현재 지연 중 비율 (그 달 1일 기준)")):
        rho = M.groupby("month").apply(lambda g: spearmanr(g[col], g.actual_rate).correlation, include_groups=False)
        print(f"  {name:30s} 순위 상관 {rho.mean():.2f} (양수인 달 {(rho > 0).mean():.0%})")
    # 같은 부서 안에서 시간에 따라 함께 움직이는지 (부서별 상관의 평균)
    print("=== 같은 부서 안에서 시간 흐름에 따른 상관 (부서별 평균)")
    for col, name in (("pred_rate", "예상 유형 구성"), ("naive_rate", "부서 과거 장기처리율"), ("current_delay", "현재 지연 중 비율")):
        rho = M.groupby("agency").apply(lambda g: spearmanr(g[col], g.actual_rate).correlation, include_groups=False)
        print(f"  {name:20s} {rho.mean():.2f}  " + ", ".join(f"{k} {v:.2f}" for k, v in rho.items()))

    print("\n=== 사분면: 세로축을 '부서 평소 대비 배수'로 바꿨을 때 (평소 = 직전 6~18개월 장기처리율)")
    M["rel"] = M.actual_rate / M.naive_rate.clip(lower=0.01)
    for gx in (0.10, 0.20):
        for gy in (1.25, 1.5):
            ur = ((M.growth >= gx) & (M.rel >= gy)).mean()
            print(f"  가로 {gx:+.0%}, 세로 평소의 {gy}배: 집중관리 {ur:.0%}, 위쪽 {(M.rel >= gy).mean():.0%}, 오른쪽 {(M.growth >= gx).mean():.0%}"
                  f" | 위쪽에 자주 오는 부서: " + ", ".join(f"{k} {v:.0%}" for k, v in (M[M.rel >= gy].agency.value_counts(normalize=True).head(3)).items()))
    print("  (참고) 고정 25% 기준일 때 위쪽에 오는 부서:", ", ".join(f"{k} {v:.0%}" for k, v in M[M.actual_rate >= .25].agency.value_counts(normalize=True).head(3).items()))


if __name__ == "__main__":
    main()
