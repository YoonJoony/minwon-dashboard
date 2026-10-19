"""10년치 검증 ④: 인력 연결의 '처리능력' 정의.

기획안 정의: 처리능력 = 최근 4주 주당 처리완료 건수. 확인할 것
1) 즉시 종결(접수 1분 안 종결, 사람 손이 거의 안 감) 비율 — 처리능력에서 빼야 하는지
2) 처리완료가 접수를 따라 늘어나는지(탄력적) 아니면 거의 고정인지
3) 접수가 평소보다 20% 이상 많은 주에 늘어난 접수 중 얼마가 그 주 안에 처리되고 얼마가 적체로 남는지
4) 최근 4주 처리완료로 다음 4주 처리완료를 얼마나 맞히는지

실행: uv run python analysis/verify_capacity.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    df = pd.read_parquet(ROOT / "data/processed/complaint_features.parquet", columns=["created", "closed", "agency", "instant"])
    df = df[df.created >= "2017-01-01"]
    print("=== 1) 즉시 종결 비율 (2017~)")
    print("  " + ", ".join(f"{k} {v:.0%}" for k, v in df.groupby("agency").instant.mean().items()))
    real = df[~df.instant]
    wk = lambda s: s.dt.to_period("W-SUN").dt.start_time
    intake = real.groupby([wk(real.created), "agency"]).size().unstack(fill_value=0)
    done = real[real.closed.notna()].groupby([wk(real.closed[real.closed.notna()]), "agency"]).size().unstack(fill_value=0)
    idx = pd.date_range("2017-01-02", "2026-09-28", freq="W-MON")
    intake, done = intake.reindex(idx, fill_value=0), done.reindex(idx, fill_value=0)

    print("\n=== 2) 주간 접수와 주간 처리완료의 상관 (1이면 처리가 접수를 그대로 따라감)")
    print("  " + ", ".join(f"{a} {np.corrcoef(intake[a], done[a])[0, 1]:.2f}" for a in intake.columns))

    print("\n=== 3) 접수 급증 주(최근 4주 평균의 1.2배 이상): 늘어난 접수 중 그 주 처리 비율 / 적체로 남은 비율")
    base_in = intake.rolling(4).mean().shift(1)
    base_done = done.rolling(4).mean().shift(1)
    rows = []
    for a in intake.columns:
        m = intake[a] >= 1.2 * base_in[a]
        extra_in = (intake[a] - base_in[a])[m].sum()
        extra_done = (done[a] - base_done[a])[m].sum()
        rows.append(f"{a} {m.sum()}주: 처리 {extra_done / extra_in:.0%} / 적체 {1 - extra_done / extra_in:.0%}")
    print("  " + "\n  ".join(rows))

    print("\n=== 4) 최근 4주 처리완료로 다음 4주 처리완료 예측 (2022~, 평균 오차)")
    nxt = done.rolling(4).sum().shift(-4)
    cur = done.rolling(4).sum()
    sel = (idx >= "2022-01-01") & nxt.notna().all(axis=1).to_numpy()
    err = ((cur - nxt).abs() / nxt)[sel].mean()
    print("  " + ", ".join(f"{k} {v:.0%}" for k, v in err.items()) + f" | 평균 {err.mean():.0%}")


if __name__ == "__main__":
    main()
