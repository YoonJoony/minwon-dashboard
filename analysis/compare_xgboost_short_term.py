"""단기(1~7일, 8~14일) 예측: LightGBM vs XGBoost 비교 (docs/xgboost_vs_lightgbm.md).

- 입력·목표·백테스트는 verify_short_term.py와 같음 (기상 없는 모델, 해마다 재학습, 평가 2022-01 ~ 2026-09)
- 모델마다 random seed 5개로 돌려 seed 차이도 같이 봄
- XGBoost는 현재 LightGBM 설정에 맞춘 것 + 깊이만 바꾼 것 몇 가지 (평가 기간으로 고르면 낙관적이므로 모두 표시)

실행: pip install xgboost 후 uv run python analysis/compare_xgboost_short_term.py
"""
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import xgboost as xgb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_short_term import BASE_F, ROOT, build_rows  # noqa: E402

OUT = ROOT / "analysis/results"
SEEDS = range(5)
COMMON = {"n_estimators": 400, "learning_rate": 0.03, "subsample": 0.8, "colsample_bytree": 0.8}
MODELS = {
    "lgbm": lambda s: lgb.LGBMRegressor(**COMMON, num_leaves=15, min_child_samples=30, subsample_freq=1,
                                        verbose=-1, random_state=s),
    # 같은 모양: 잎 단위로 15개까지 (LightGBM 방식)
    "xgb_leaves15": lambda s: xgb.XGBRegressor(**COMMON, tree_method="hist", enable_categorical=True,
                                               grow_policy="lossguide", max_leaves=15, max_depth=0,
                                               min_child_weight=30, random_state=s),
    # XGBoost 기본 방식: 깊이 단위
    **{f"xgb_depth{d}": (lambda d: lambda s: xgb.XGBRegressor(**COMMON, tree_method="hist", enable_categorical=True,
                                                               max_depth=d, min_child_weight=30, random_state=s))(d)
       for d in (3, 4, 5)},
}


def backtest(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    for yr in range(2022, 2027):
        tr = df[df.origin < f"{yr}-01-01"]
        te = df[(df.origin >= f"{yr}-01-01") & (df.origin < f"{yr + 1}-01-01")].copy()
        for name, make in MODELS.items():
            for s in SEEDS:
                m = make(s).fit(tr[BASE_F], tr["target"])
                te[f"{name}_s{s}"] = np.exp(m.predict(te[BASE_F])) * (te["base"] + 1) - 1
        out.append(te)
    return pd.concat(out)


def mape(g: pd.DataFrame, col: str) -> float:
    """에이전시별 평균 후 8개 부서 단순 평균 (verify_short_term.py와 같은 정의)."""
    e = (g[col] - g.actual).abs() / g.actual.clip(lower=1)
    return e.groupby(g.agency.astype(str), observed=True).mean().mean()


def main() -> None:
    a = pd.read_csv(ROOT / "data/processed/daily_agency_weather.csv", parse_dates=["date"])
    w = pd.read_csv(ROOT / "data/processed/weather_features_daily.csv", parse_dates=["date"]).set_index("date")
    R = backtest(build_rows(a.pivot(index="date", columns="agency", values="count"), w))
    for name in MODELS:  # seed 5개 평균 예측
        R[f"{name}_avg"] = R[[f"{name}_s{s}" for s in SEEDS]].mean(axis=1)
    R["ens_lgbm_xgb4"] = (R["lgbm_avg"] + R["xgb_depth4_avg"]) / 2
    keep = ["origin", "block", "agency", "actual", "base"] + [c for c in R.columns if c.endswith(("_avg",)) or c.startswith(("lgbm_s", "xgb_depth4_s"))] + ["ens_lgbm_xgb4"]
    R[keep].to_csv(OUT / "xgb_vs_lgbm_backtest.csv", index=False)

    for blk, label in ((1, "1~7일"), (2, "8~14일")):
        g = R[R.block == blk]
        gz = g[g.actual > 0]
        print(f"\n=== [{label}] MAPE: 전체 / 실제 0인 주 제외")
        for name in MODELS:
            per_seed = [mape(g, f"{name}_s{s}") for s in SEEDS]
            print(f"{name:14s} seed별 {min(per_seed):.2%}~{max(per_seed):.2%} (평균 {np.mean(per_seed):.2%})"
                  f" | seed 평균 예측 {mape(g, f'{name}_avg'):.2%} / {mape(gz, f'{name}_avg'):.2%}")
        print(f"{'ens_lgbm_xgb4':14s} {mape(g, 'ens_lgbm_xgb4'):.2%} / {mape(gz, 'ens_lgbm_xgb4'):.2%}")

        # 연도·부서별, 예측별 승패 (lgbm vs xgb_depth4, seed 평균 예측)
        yr = g.origin.dt.year
        print("연도별 (lgbm / xgb_depth4 / xgb_leaves15):")
        for y in sorted(yr.unique()):
            gy = g[yr == y]
            print(f"  {y}: {mape(gy, 'lgbm_avg'):.2%} / {mape(gy, 'xgb_depth4_avg'):.2%} / {mape(gy, 'xgb_leaves15_avg'):.2%}")
        print("부서별 (실제 0인 주 제외, lgbm / xgb_depth4):")
        for ag, x in gz.groupby(gz.agency.astype(str), observed=True):
            el = ((x.lgbm_avg - x.actual).abs() / x.actual).mean()
            ex = ((x.xgb_depth4_avg - x.actual).abs() / x.actual).mean()
            print(f"  {ag:6s} {el:.1%} / {ex:.1%}")
        el = (g.lgbm_avg - g.actual).abs()
        ex = (g.xgb_depth4_avg - g.actual).abs()
        print(f"예측 {len(g)}건 중 xgb_depth4가 더 가까움 {(ex < el).mean():.1%}, lgbm {(el < ex).mean():.1%}")


if __name__ == "__main__":
    main()
