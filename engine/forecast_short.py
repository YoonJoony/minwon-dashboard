"""단기(1~14일) 부서별 접수 건수 예측 — LightGBM (검증 ②, analysis/verify_short_term.py와 같은 정의).

- 예측 단위: 기준일부터 7일(1~7일 블록)과 그다음 7일(8~14일 블록)의 합계
- 입력: 직전 28일 평균(기준), 직전 7일 ÷ 직전 28일, 과거 3년 같은 시기 비율(중앙값), 공휴일 수, 시기
- 목표: log((실제 + 1) ÷ (직전 28일 평균 × 7 + 1))
- 학습: 기준일 2주 전까지 끝난 모든 월요일 기준점
- 80% 범위: 같은 방식의 과거 예측 오차(연 단위 재학습 백테스트)의 10~90% 지점
"""
import lightgbm as lgb
import numpy as np
import pandas as pd

from engine.config import AGENCIES

FEATURES = ["agency", "block", "r7_r28", "season_ratio", "holidays", "woy_sin", "woy_cos"]
CATS = sorted(AGENCIES)
BLOCKS = {1: (0, 6), 2: (7, 13)}
PARAMS = {"n_estimators": 400, "learning_rate": 0.03, "num_leaves": 15, "min_child_samples": 30, "subsample": 0.8,
          "subsample_freq": 1, "colsample_bytree": 0.8, "verbose": -1, "random_state": 0}
D = pd.Timedelta


def feature_rows(cnt: pd.DataFrame, hol: pd.Series, origins, require_actual: bool = True) -> pd.DataFrame:
    """기준점(origin)마다 부서·블록별 입력 변수. require_actual이면 실제값이 다 있는 블록만."""
    days = cnt.index
    rows = []
    for t in origins:
        t = pd.Timestamp(t)
        if t - D(days=28 * 13) < days[0]:
            continue
        for blk, (a, b) in BLOCKS.items():
            s, e = t + D(days=a), t + D(days=b)
            if require_actual and e > days[-1]:
                continue
            for ag in AGENCIES:
                y = cnt[ag]
                r28 = y.loc[t - D(days=28): t - D(days=1)].mean()
                r7 = y.loc[t - D(days=7): t - D(days=1)].mean()
                ratios = []
                for k in (1, 2, 3):
                    ps, pe, pt = s - pd.DateOffset(years=k), e - pd.DateOffset(years=k), t - pd.DateOffset(years=k)
                    if pt - D(days=28) < days[0]:
                        continue
                    base = y.loc[pt - D(days=28): pt - D(days=1)].mean() * 7
                    if base > 0:
                        ratios.append(y.loc[ps:pe].sum() / base)
                actual = y.loc[s:e].sum() if e <= days[-1] else np.nan
                rows.append({
                    "origin": t, "block": blk, "agency": ag, "start": s, "end": e, "actual": actual, "base": r28 * 7,
                    "r7_r28": r7 / r28 if r28 > 0 else 1.0, "season_ratio": np.median(ratios) if ratios else 1.0,
                    "holidays": hol.reindex(pd.date_range(s, e)).fillna(0).sum(),
                    "woy_sin": np.sin(2 * np.pi * s.dayofyear / 365.25), "woy_cos": np.cos(2 * np.pi * s.dayofyear / 365.25),
                })
    # 행 순서를 검증 스크립트와 같게(기준점 → 블록 → 부서 알파벳순): LightGBM 표본 추출이 행 순서에 따라 달라짐
    df = pd.DataFrame(rows).sort_values(["origin", "block", "agency"], kind="stable").reset_index(drop=True)
    df["agency"] = pd.Categorical(df["agency"], categories=CATS)
    df["target"] = np.log((df["actual"] + 1) / (df["base"] + 1))
    return df


def fit(train: pd.DataFrame) -> lgb.LGBMRegressor:
    return lgb.LGBMRegressor(**PARAMS).fit(train[FEATURES], train["target"])


def predict(model: lgb.LGBMRegressor, rows: pd.DataFrame) -> np.ndarray:
    return np.exp(model.predict(rows[FEATURES])) * (rows["base"] + 1) - 1


def backtest(rows: pd.DataFrame, years=range(2022, 2027)) -> pd.DataFrame:
    """연 단위 재학습 백테스트 (80% 범위 계산용 과거 오차). 그해 이전 기준점으로 학습해 그해를 예측."""
    out = []
    for yr in years:
        tr = rows[rows.origin < f"{yr}-01-01"]
        te = rows[(rows.origin >= f"{yr}-01-01") & (rows.origin < f"{yr + 1}-01-01")].copy()
        if te.empty:
            continue
        te["pred"] = predict(fit(tr), te)
        out.append(te)
    return pd.concat(out)


def forecast(asof: pd.Timestamp, rows: pd.DataFrame, cnt: pd.DataFrame, hol: pd.Series) -> pd.DataFrame:
    """기준일의 1~7일·8~14일 부서별 예측. 학습은 기준일 2주 전까지 끝난 기준점만."""
    model = fit(rows[rows.origin + D(days=13) < asof])
    sc = feature_rows(cnt, hol, [asof], require_actual=False)
    sc["pred"] = predict(model, sc)
    return sc[["agency", "block", "start", "end", "pred", "base"]].assign(agency=lambda d: d.agency.astype(str))


def interval_ratios(bt: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
    """블록별·부서별 (실제+1)÷(예측+1)의 10%·90% 지점. 기준일 전에 결과가 확정된 예측만."""
    out = []
    for blk, (_, b) in BLOCKS.items():
        past = bt[(bt.block == blk) & (bt.origin + D(days=b) < asof)]
        err = np.log((past.actual + 1) / (past.pred + 1)).groupby(past.agency.astype(str), observed=True).quantile([0.1, 0.9]).unstack()
        out.append(pd.DataFrame({"agency": err.index, "block": blk, "lo_ratio": np.exp(err[0.1]).to_numpy(),
                                 "hi_ratio": np.exp(err[0.9]).to_numpy()}))
    return pd.concat(out, ignore_index=True)
