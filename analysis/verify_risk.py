"""10년치 검증 ①: 장기처리 위험 모델 + 매트릭스 세로축(미래 기간 장기처리율) + 사분면 기준값.

장기처리 정의 (기획 최종안):
- 기준 = 부서별 처리기간 P90. 매달, 6~12개월 전에 접수된 민원으로 다시 계산
  (그 시점에 아직 처리 중인 민원은 '매우 오래 걸림'으로 계산, P90을 못 구하면 처리 완료분으로 대체)
- 중도절단: 학습 시점에 처리 중이면서 기준을 이미 넘긴 민원 = 장기(1), 아직 기준 이내면 결과 미정이라 제외

평가: 2022-01 ~ 2026-03 매달 (그 달 1일 기준으로 최근 12개월 데이터로 학습 → 그 달 접수 민원을 예측).
정답은 데이터 마지막 날(2026-10-12) 기준으로 확정된 것만 씁니다.

실행: uv run python analysis/verify_risk.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis/results"
CAT = ["agency", "complaint_type", "descriptor", "location_type", "open_data_channel_type", "community_board",
       "dow_s", "hourb", "month_s"]
NUM = ["backlog_agency", "backlog_type", "dup_3d", "type_vol_7d", "agency_vol_7d", "recent_med", "recent_n"]
WX = ["temperature_2m_max", "precipitation_sum", "snowfall_3d", "wind_gusts_10m_max", "is_hot", "is_heavy_rain",
      "is_snow", "is_strong_gust", "is_holiday"]
AG = ["DCWP", "DEP", "DHS", "DOB", "DOHMH", "DOT", "DPR", "DSNY"]
NEVER = 1e6  # 처리 중 민원의 처리기간 대용값


def thresholds(df: pd.DataFrame, m: pd.Timestamp) -> pd.Series:
    w = df[(df.created >= m - pd.DateOffset(months=12)) & (df.created < m - pd.DateOffset(months=6))]
    known = w.proc_days.where(w.closed < m, NEVER)
    thr = known.groupby(w.agency).quantile(0.9)
    fallback = w[w.closed < m].groupby("agency").proc_days.quantile(0.9)
    return thr.where(thr < NEVER, fallback)


def label(d: pd.DataFrame, thr: pd.Series, asof: pd.Timestamp) -> pd.Series:
    t = d.agency.map(thr)
    done = d.closed.notna() & (d.closed <= asof)
    elapsed = (asof - d.created).dt.total_seconds() / 86400
    y = pd.Series(np.nan, index=d.index)
    y[done] = (d.proc_days[done] > t[done]).astype(float)
    y[~done & (elapsed > t)] = 1.0
    return y


def model(num: list[str]):
    ct = ColumnTransformer([("c", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=20), CAT),
                            ("n", StandardScaler(), num)])
    return make_pipeline(ct, LogisticRegression(max_iter=400, C=0.5))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(ROOT / "data/processed/complaint_features.parquet")
    df["dow_s"] = df.dow.astype(str)
    df["hourb"] = (df.hour // 3).astype(str)
    df["month_s"] = df.month.astype(str)
    for c in ["backlog_agency", "backlog_type", "dup_3d", "type_vol_7d", "agency_vol_7d", "recent_n"]:
        df[c] = np.log1p(df[c])
    df["recent_med"] = np.log1p(df["recent_med"].clip(lower=-0.99))
    for c in CAT:
        df[c] = df[c].astype(str)
    end = df.created.max()

    rows, mrows, thr_log = [], [], []
    months = pd.date_range("2022-01-01", "2026-03-01", freq="MS")
    for m in months:
        thr = thresholds(df, m)
        thr_log.append(thr.rename(m.strftime("%Y-%m")))
        tr = df[(df.created >= m - pd.DateOffset(months=12)) & (df.created < m)]
        te = df[(df.created >= m) & (df.created < m + pd.offsets.MonthBegin(1))]
        ytr, yte = label(tr, thr, m), label(te, thr, end)
        a, ya = tr[ytr.notna()], ytr[ytr.notna()].to_numpy()
        b, yb = te[yte.notna()], yte[yte.notna()].to_numpy()
        for name, num in (("기본", NUM), ("기본+접수일 기상", NUM + WX)):
            p = model(num).fit(a, ya).predict_proba(b)[:, 1]
            r = {"month": m.strftime("%Y-%m"), "variant": name, "pooled": roc_auc_score(yb, p), "pos_rate": yb.mean()}
            for ag in AG:
                mk = (b.agency == ag).to_numpy()
                r[ag] = roc_auc_score(yb[mk], p[mk]) if len(set(yb[mk])) > 1 else np.nan
            rows.append(r)

        # 세로축(미래 기간 장기처리율): 예상 유형 구성 × 유형별 과거 장기처리율
        hist = df[(df.created >= m - pd.DateOffset(months=18)) & (df.created < m - pd.DateOffset(months=6))]
        yh = label(hist, thr, m)
        hist = hist.assign(y=yh)[yh.notna()]
        rate_t = hist.groupby(["agency", "complaint_type"]).y.agg(["mean", "size"])
        rate_a = hist.groupby("agency").y.mean()
        same = df[(df.created.dt.month == m.month) & (df.created < m) & (df.created >= m - pd.DateOffset(years=3))]
        share = same.groupby(["agency", "complaint_type"]).size()
        share = share / share.groupby(level=0).transform("sum")
        r_t = rate_t["mean"].where(rate_t["size"] >= 30).reindex(share.index)
        r_t = r_t.fillna(pd.Series(rate_a.reindex(share.index.get_level_values(0)).to_numpy(), index=share.index))
        pred = (share * r_t).groupby(level=0).sum()
        act = te.assign(y=yte)[yte.notna()].groupby("agency").y.mean()
        cnt = te.groupby("agency").size()
        recent28 = df[(df.created >= m - pd.Timedelta(days=28)) & (df.created < m)].groupby("agency").size() / 28
        for ag in AG:
            mrows.append({"month": m.strftime("%Y-%m"), "agency": ag, "pred_rate": pred.get(ag), "naive_rate": rate_a.get(ag),
                          "actual_rate": act.get(ag), "count": cnt.get(ag, 0),
                          "growth": cnt.get(ag, 0) / (recent28.get(ag, np.nan) * m.days_in_month) - 1})
        print(m.strftime("%Y-%m"), "완료", flush=True)

    R = pd.DataFrame(rows)
    M = pd.DataFrame(mrows)
    R.to_csv(OUT / "risk_model_auc.csv", index=False)
    M.to_csv(OUT / "matrix_monthly.csv", index=False)
    pd.concat(thr_log, axis=1).to_csv(OUT / "risk_thresholds.csv")

    print("\n=== 장기처리 위험 모델 (월별 재학습, 2022-01 ~ 2026-03, 51개월 평균)")
    s = R.groupby("variant")[["pooled", "pos_rate"] + AG].mean()
    s["부서별 평균"] = s[AG].mean(axis=1)
    print(s.round(3).to_string())
    print("기간별 전체 AUC:", R[R.variant == "기본"].groupby(R.month.str[:4]).pooled.mean().round(3).to_dict())

    print("\n=== 매트릭스 세로축 (그 달 장기처리율 예측)")
    M2 = M.dropna(subset=["actual_rate"])
    for col, name in (("pred_rate", "예상 유형 구성 × 유형별 장기처리율"), ("naive_rate", "부서 과거 장기처리율 그대로")):
        mae = (M2[col] - M2.actual_rate).abs().mean() * 100
        rho = M2.groupby("month").apply(lambda g: spearmanr(g[col], g.actual_rate).correlation, include_groups=False).mean()
        print(f"  {name:28s} 평균 오차 {mae:.1f}%p, 부서 순위 상관 {rho:.2f}")

    print("\n=== 사분면 기준값 검토 (부서×월 408개, 실제값 기준)")
    print("  실제 장기처리율 분포(%):", (M2.actual_rate.describe(percentiles=[.25, .5, .75, .9]) * 100).round(1).to_dict())
    print("  접수 증가율(최근 4주 대비) 분포(%):", (M2.growth.describe(percentiles=[.25, .5, .75, .9]) * 100).round(1).to_dict())
    for gx in (0.10, 0.20):
        for gy in (0.15, 0.20, 0.25):
            q = pd.crosstab(M2.growth >= gx, M2.actual_rate >= gy, normalize=True)
            ur = q.loc[True, True] if (True in q.index and True in q.columns) else 0
            up = q[True].sum() if True in q.columns else 0
            right = q.loc[True].sum() if True in q.index else 0
            print(f"  가로 {gx:+.0%}, 세로 {gy:.0%}: 집중관리 {ur:.0%}, 위쪽 전체 {up:.0%}, 오른쪽 전체 {right:.0%}")
    print("  부서별 장기처리율 중앙값(%):", (M2.groupby("agency").actual_rate.median() * 100).round(1).to_dict())


if __name__ == "__main__":
    main()
