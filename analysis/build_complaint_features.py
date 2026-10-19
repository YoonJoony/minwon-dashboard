"""민원 1건별 분석용 변수 테이블을 만듭니다 (10년치 검증 공통 입력).

입력: data/processed/nyc311_weather_merged.csv.gz
출력: data/processed/complaint_features.parquet

변수는 모두 **접수 시점에 알 수 있는 값**입니다.
- 부서·유형 적체: 접수 순간 같은 부서(같은 부서·유형)의 미처리 건수
- 최근 접수량: 같은 부서·유형의 직전 7일 접수 건수, 같은 부서의 직전 7일 접수 건수
- 중복 신고: 같은 부서·세부 유형·우편번호의 직전 3일 신고 수
- 최근 처리속도: 같은 부서·유형이 직전 28일 동안 처리 완료한 민원의 처리기간 중앙값 (주 단위 갱신)
- 접수일 기상: 최고기온, 강수, 3일 누적 적설, 폭염·폭우·적설·강풍 여부, 공휴일

실행 (프로젝트 루트에서): uv run python analysis/build_complaint_features.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data/processed/nyc311_weather_merged.csv.gz"
OUT = ROOT / "data/processed/complaint_features.parquet"

CAT = ["agency", "complaint_type", "descriptor", "location_type", "open_data_channel_type",
       "community_board", "incident_zip", "issue", "status"]
WEATHER = ["temperature_2m_max", "precipitation_sum", "snowfall_3d", "wind_gusts_10m_max",
           "is_hot", "is_heavy_rain", "is_snow", "is_strong_gust", "hot_streak", "is_holiday"]


def prior_count(df: pd.DataFrame, t: np.ndarray, keys: list[str], days: int) -> np.ndarray:
    """같은 키 그룹에서 직전 `days`일 안에 접수된 건수 (자기 자신 제외)."""
    code = df.groupby(keys, sort=False, observed=True).ngroup().to_numpy(np.int64)
    comp = code * 10**10 + (t - t.min())
    order = np.argsort(comp, kind="stable")
    cs = comp[order]
    return np.searchsorted(cs, comp, "left") - np.searchsorted(cs, comp - days * 86400, "left")


def backlog(df: pd.DataFrame, t: np.ndarray, k: np.ndarray, closed: np.ndarray, keys: list[str]) -> np.ndarray:
    """접수 순간 같은 키 그룹의 미처리 건수 = (그 전에 접수된 건) − (그 전에 처리 완료된 건)."""
    res = np.zeros(len(df))
    for _, idx in df.groupby(keys, sort=False, observed=True).indices.items():
        c = np.sort(t[idx])
        kk = np.sort(k[idx][closed[idx]])
        res[idx] = np.searchsorted(c, t[idx], "left") - np.searchsorted(kk, t[idx], "right")
    return np.clip(res, 0, None)


def main() -> None:
    df = pd.read_csv(SRC, usecols=["unique_key", "created_date", "closed_date", "agency_raw", "date"] + CAT + WEATHER,
                     dtype={c: "string" for c in CAT + ["unique_key", "agency_raw"]})
    df["created"] = pd.to_datetime(df["created_date"])
    df["closed"] = pd.to_datetime(df["closed_date"], errors="coerce")
    df["proc_days"] = (df["closed"] - df["created"]).dt.total_seconds() / 86400
    before = len(df)
    # 처리완료일이 접수일보다 빠른 건, 상태는 완료인데 완료일이 없는 건은 결과를 알 수 없어 제외
    df = df[~(df["proc_days"] < 0) & ~((df["status"] == "Closed") & df["closed"].isna())].copy()
    print(f"민원 {before:,}건 → 결과 불명 제외 후 {len(df):,}건")

    df = df.sort_values("created").reset_index(drop=True)
    for c in ["location_type", "descriptor", "community_board", "incident_zip"]:
        df[c] = df[c].fillna("NA")
    df["location_type"] = df["location_type"].replace({"3+ Family Apartment Building": "3+ Family Apt. Building"})
    df["dow"] = df["created"].dt.dayofweek.astype("int8")
    df["hour"] = df["created"].dt.hour.astype("int8")
    df["month"] = df["created"].dt.month.astype("int8")
    df["instant"] = df["proc_days"] < 1 / 1440

    t = df["created"].to_numpy("datetime64[s]").astype(np.int64)
    k = df["closed"].to_numpy("datetime64[s]").astype(np.int64)
    closed = df["closed"].notna().to_numpy()
    df["backlog_agency"] = backlog(df, t, k, closed, ["agency"])
    df["backlog_type"] = backlog(df, t, k, closed, ["agency", "complaint_type"])
    df["dup_3d"] = prior_count(df, t, ["agency", "descriptor", "incident_zip"], 3)
    df["type_vol_7d"] = prior_count(df, t, ["agency", "complaint_type"], 7)
    df["agency_vol_7d"] = prior_count(df, t, ["agency"], 7)
    print("적체·접수량·중복 변수 완료")

    # 최근 처리속도: 주 단위로 직전 28일 처리 완료분의 처리기간 중앙값
    df["wk"] = df["created"].dt.to_period("W-SUN").dt.start_time
    cl = df.loc[closed, ["agency", "complaint_type", "closed", "proc_days"]]
    cl = cl.assign(cwk=cl["closed"].dt.to_period("W-SUN").dt.start_time)
    weekly = cl.groupby(["agency", "complaint_type", "cwk"], observed=True)["proc_days"].agg(["median", "size"])
    rows = []
    for w in sorted(df["wk"].unique()):
        win = weekly[(weekly.index.get_level_values("cwk") < w)
                     & (weekly.index.get_level_values("cwk") >= w - pd.Timedelta(days=28))]
        g = win.groupby(level=[0, 1], observed=True).agg(recent_med=("median", "median"), recent_n=("size", "sum"))
        rows.append(g.assign(wk=w).reset_index())
    rec = pd.concat(rows)
    df = df.merge(rec, on=["agency", "complaint_type", "wk"], how="left")
    df["recent_med"] = df["recent_med"].fillna(-1)
    df["recent_n"] = df["recent_n"].fillna(0)
    print("최근 처리속도 변수 완료")

    keep = ["unique_key", "created", "closed", "proc_days", "status", "instant", "agency", "agency_raw", "complaint_type",
            "descriptor", "location_type", "open_data_channel_type", "community_board", "incident_zip", "issue", "dow",
            "hour", "month", "backlog_agency", "backlog_type", "dup_3d", "type_vol_7d", "agency_vol_7d", "recent_med",
            "recent_n"] + WEATHER
    df[keep].to_parquet(OUT, index=False)
    print(f"저장: {OUT.relative_to(ROOT)} ({len(df):,}행, {len(keep)}열)")


if __name__ == "__main__":
    main()
