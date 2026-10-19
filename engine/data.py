"""데이터 읽기. 원본·병합 결과(data/raw, data/processed)를 표 형태로 돌려줍니다."""
from datetime import date, timedelta
from functools import lru_cache

import pandas as pd

from engine.config import AGENCIES, PROCESSED, RAW_WEATHER

HOURLY_COLS = ["t", "rh", "prcp", "snow", "wind", "gust"]
_HOURLY_VARS = ["temperature_2m", "relative_humidity_2m", "precipitation", "snowfall", "wind_speed_10m", "wind_gusts_10m"]


@lru_cache(maxsize=1)
def daily_counts() -> pd.DataFrame:
    """날짜 × 부서 접수 건수 (즉시 종결 포함, 접수가 없는 날은 0)."""
    a = pd.read_csv(PROCESSED / "daily_agency_weather.csv", usecols=["date", "agency", "count"], parse_dates=["date"])
    return a.pivot(index="date", columns="agency", values="count")[AGENCIES].astype(float)


@lru_cache(maxsize=1)
def daily_issues() -> pd.DataFrame:
    """날짜 × 이슈 접수 건수 ('기타' 제외)."""
    i = pd.read_csv(PROCESSED / "daily_issue_weather.csv", usecols=["date", "issue", "count"], parse_dates=["date"])
    return i.pivot(index="date", columns="issue", values="count").drop(columns="기타").astype(float)


@lru_cache(maxsize=1)
def weather_daily() -> pd.DataFrame:
    return pd.read_csv(PROCESSED / "weather_features_daily.csv", parse_dates=["date"]).set_index("date")


@lru_cache(maxsize=1)
def complaints() -> pd.DataFrame:
    """민원 1건별 분석 변수 (analysis/build_complaint_features.py 결과)."""
    return pd.read_parquet(PROCESSED / "complaint_features.parquet")


@lru_cache(maxsize=1)
def hourly_obs() -> pd.DataFrame:
    o = pd.read_parquet(RAW_WEATHER / "openmeteo_bronx_hourly_obs.parquet")
    return o.rename(columns=dict(zip(_HOURLY_VARS, HOURLY_COLS)))


@lru_cache(maxsize=1)
def hourly_forecast() -> pd.DataFrame:
    return pd.read_parquet(RAW_WEATHER / "openmeteo_bronx_hourly_forecast.parquet")


def forecast_lead(lead: int) -> pd.DataFrame:
    """lead일 전에 발표된 예보의 시간별 값 (열 이름은 관측과 같게)."""
    f = hourly_forecast()
    cols = [f"{v}_previous_day{lead}" for v in _HOURLY_VARS]
    out = f[["time"] + cols].copy()
    out.columns = ["time"] + HOURLY_COLS
    return out


# ------------------------------------------------------------------ 미국 연방 공휴일 (pipelines/merge_weather.py와 같은 규칙)
def _nth_weekday(y: int, m: int, weekday: int, n: int) -> date:
    if n > 0:
        d = date(y, m, 1)
        d += timedelta(days=(weekday - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)
    d = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d: date) -> date:
    return d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d


@lru_cache(maxsize=1)
def holidays() -> pd.Series:
    """날짜 → 공휴일 여부(0/1). 2015~2027."""
    days = []
    for y in range(2015, 2028):
        fixed = [date(y, 1, 1), date(y, 7, 4), date(y, 11, 11), date(y, 12, 25)] + ([date(y, 6, 19)] if y >= 2021 else [])
        days += [_observed(d) for d in fixed]
        days += [_nth_weekday(y, 1, 0, 3), _nth_weekday(y, 2, 0, 3), _nth_weekday(y, 5, 0, -1),
                 _nth_weekday(y, 9, 0, 1), _nth_weekday(y, 10, 0, 2), _nth_weekday(y, 11, 3, 4)]
    idx = pd.date_range("2015-01-01", "2027-12-31")
    return pd.Series(idx.isin(pd.to_datetime(days)).astype(int), index=idx)
