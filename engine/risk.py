"""지연 위험 민원 — 로지스틱 회귀 (검증 ⑥, analysis/verify_risk.py와 같은 정의).

- 장기처리 = 부서별 처리기간 P90 초과. P90은 매달 6~12개월 전 접수분으로 재계산(그때 처리 중이면 '매우 오래 걸림')
- 학습: 매달 1일, 최근 12개월 접수분. 처리 중이면서 이미 기준을 넘긴 민원 = 1, 아직 기준 이내 = 제외(중도절단)
- 적용: 기준일에 처리 중인 민원(최근 6개월 접수분)의 지연 확률
- 소비자보호국은 모델이 거의 구별하지 못해(AUC 0.62) 확률 대신 '경과일 ÷ 기준처리기간'으로 정렬
- 화면에 보여 주는 기준처리기간은 최근 6개월 P90의 중앙값 (달마다 출렁임을 줄임)
"""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from engine.config import AGENCIES, RISK_TOP_K

CAT = ["agency", "complaint_type", "descriptor", "location_type", "open_data_channel_type", "community_board",
       "dow_s", "hourb", "month_s"]
NUM = ["backlog_agency", "backlog_type", "dup_3d", "type_vol_7d", "agency_vol_7d", "recent_med", "recent_n"]
NEVER = 1e6
ELAPSED_ONLY = {"DCWP"}

CAT_LABEL = {"agency": "부서", "complaint_type": "유형", "descriptor": "세부 유형", "location_type": "장소",
             "open_data_channel_type": "접수 경로", "community_board": "지역", "dow_s": "접수 요일",
             "hourb": "접수 시간대", "month_s": "접수 월"}
NUM_LABEL = {"backlog_agency": ("접수 당시 부서 적체 많음", "접수 당시 부서 적체 적음"),
             "backlog_type": ("같은 유형 적체 많음", "같은 유형 적체 적음"),
             "dup_3d": ("최근 3일 중복 신고 많음", "중복 신고 없음"),
             "type_vol_7d": ("같은 유형 최근 접수 많음", "같은 유형 최근 접수 적음"),
             "agency_vol_7d": ("부서 최근 접수 많음", "부서 최근 접수 적음"),
             "recent_med": ("최근 같은 유형 처리 기간 김", "최근 같은 유형 처리 기간 짧음"),
             "recent_n": ("최근 처리 건수 많음", "최근 처리 건수 적음")}
DOW = ["월", "화", "수", "목", "금", "토", "일"]
CHANNEL = {"PHONE": "전화", "ONLINE": "온라인", "MOBILE": "모바일 앱", "UNKNOWN": "미상", "OTHER": "기타"}


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["dow_s"] = df.dow.astype(str)
    df["hourb"] = (df.hour // 3).astype(str)
    df["month_s"] = df.month.astype(str)
    for c in ["backlog_agency", "backlog_type", "dup_3d", "type_vol_7d", "agency_vol_7d", "recent_n"]:
        df[c] = np.log1p(df[c])
    df["recent_med"] = np.log1p(df["recent_med"].clip(lower=-0.99))
    for c in CAT:
        df[c] = df[c].astype(str)
    return df


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


def train(df: pd.DataFrame, m: pd.Timestamp):
    thr = thresholds(df, m)
    tr = df[(df.created >= m - pd.DateOffset(months=12)) & (df.created < m)]
    y = label(tr, thr, m)
    ct = ColumnTransformer([("c", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=20), CAT),
                            ("n", StandardScaler(), NUM)])
    model = make_pipeline(ct, LogisticRegression(max_iter=400, C=0.5)).fit(tr[y.notna()], y[y.notna()])
    return model, thr


def _factor_label(name: str, value: float) -> str:
    if name.startswith("n__"):
        col = name[3:]
        hi, lo = NUM_LABEL[col]
        return hi if value > 0 else lo
    rest = name[3:]
    for col in sorted(CAT, key=len, reverse=True):
        if rest.startswith(col + "_"):
            v = rest[len(col) + 1:]
            if v.endswith("infrequent_sklearn"):
                return f"{CAT_LABEL[col]}: 드문 유형"
            if col == "dow_s":
                v = DOW[int(v)] + "요일"
            elif col == "hourb":
                v = f"{int(v) * 3}~{int(v) * 3 + 3}시"
            elif col == "month_s":
                v = f"{v}월"
            elif col == "open_data_channel_type":
                v = CHANNEL.get(v, v)
            return f"{CAT_LABEL[col]}: {v}"
    return rest


def top_factors(model, rows: pd.DataFrame, k: int = 2) -> list[list[str]]:
    ct = model.named_steps["columntransformer"]
    lr = model.named_steps["logisticregression"]
    X = ct.transform(rows).tocsr()
    names = ct.get_feature_names_out()
    contrib = X.multiply(lr.coef_[0]).tocsr()
    out = []
    for i in range(contrib.shape[0]):
        row = contrib.getrow(i)
        order = np.argsort(-row.data)
        labels = []
        for j in order:
            if row.data[j] <= 0 or len(labels) >= k:
                break
            col = row.indices[j]
            labels.append(_factor_label(names[col], X[i, col]))
        out.append(labels)
    return out


def score(df: pd.DataFrame, model, thr_display: pd.Series, asof: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    """기준일 처리 중 민원(최근 6개월 접수분)의 지연 확률·순위, 부서별 개수."""
    w = df[(df.created >= asof - pd.DateOffset(months=6)) & (df.created < asof)]
    o = w[w.closed.isna() | (w.closed >= asof) | (w.status != "Closed")].copy()
    o["elapsed_days"] = (asof - o.created).dt.total_seconds() / 86400
    o["threshold_days"] = o.agency.map(thr_display)
    o["ratio"] = o.elapsed_days / o.threshold_days
    o["prob"] = model.predict_proba(o)[:, 1]
    o.loc[o.agency.isin(ELAPSED_ONLY), "prob"] = np.nan
    o["method"] = np.where(o.agency.isin(ELAPSED_ONLY), "elapsed", "model")
    o["score"] = o.prob.fillna(o.ratio.clip(upper=3) / 3)
    counts = o.groupby("agency").agg(open=("unique_key", "size"), over_threshold=("ratio", lambda r: int((r > 1).sum())),
                                     high_risk=("prob", lambda p: int((p >= 0.5).sum())))
    counts = counts.reindex(AGENCIES).fillna(0).astype(int).reset_index()
    top = o.sort_values("score", ascending=False).groupby("agency", group_keys=False).head(RISK_TOP_K).copy()
    top["factors"] = [" · ".join(f) for f in top_factors(model, top)]
    top.loc[top.method == "elapsed", "factors"] = "경과일 기준 (이 부서는 위험 확률 대신 경과일로 표시)"
    top["rank"] = top.groupby("agency").score.rank(ascending=False, method="first").astype(int)
    cols = ["unique_key", "agency", "complaint_type", "descriptor", "created", "elapsed_days", "threshold_days", "ratio",
            "prob", "method", "score", "rank", "factors"]
    return top[cols].reset_index(drop=True), counts
