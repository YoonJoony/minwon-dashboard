"""뉴욕시 311 민원 + Open-Meteo 기상 데이터 병합 스크립트.

병합 기준: 311 접수일시(created_date)의 **뉴욕 현지 날짜** = 기상 데이터의 날짜.
(311 시각과 Open-Meteo(timezone=America/New_York) 날짜가 모두 현지 기준이라 변환 없이 맞습니다.)

만드는 파일 (data/processed/):
    weather_features_daily.csv   날짜별 기상 변수 + 지연(1~3일 전)·누적·이벤트 플래그 + 휴일
    daily_agency_weather.csv     날짜 × 기관 접수 건수 + 기상 변수   (접수량 예측용)
    daily_issue_weather.csv      날짜 × 이슈 접수 건수 + 기상 변수   (예상 이슈 키워드용)
    nyc311_weather_merged.csv.gz 민원 1건마다 접수일 기상 변수를 붙인 파일 (장기처리 위험 모델용)

사용 예 (프로젝트 루트에서):
    python pipelines/merge_weather.py                    # 월별 파일 폴더(data/raw/nyc311)를 그대로 읽음
    python pipelines/merge_weather.py --nyc some_file.csv  # 합쳐진 CSV 하나를 읽을 수도 있음
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

# 2020년 이전 소비자보호국 약어(DCA)를 현재 약어로 통일합니다.
AGENCY_RENAME = {"DCA": "DCWP"}
AGENCY_NAME = {"DCWP": "Department of Consumer and Worker Protection"}

# 기상 이벤트 기준 (수정안 실현 가능성 검토에서 민원 급증이 확인된 값)
HOT_TMAX = 32.0       # 최고기온 °C
HEAVY_RAIN = 25.0     # 일 강수량 mm
SNOW_DAY = 2.0        # 일 신적설 cm
STRONG_GUST = 60.0    # 최대 돌풍 km/h

LAG_COLS = ["temperature_2m_max", "precipitation_sum", "snowfall_sum", "wind_gusts_10m_max", "hot_hours"]

# 예상 이슈 키워드: 민원 유형·세부 유형 → 이슈 묶음 (위에서부터 먼저 맞는 것 하나)
ISSUES = [
    ("폭염·소화전", "descriptor", r"Hydrant"),
    ("결빙·제설", "complaint_type", r"^Snow"),
    ("폭우·침수", "descriptor", r"Sewer Backup|Catch Basin|Flooding"),
    ("강풍·수목", "complaint_type", r"^Damaged Tree$"),
    ("도로 파손", "descriptor", r"^(?:Pothole|Cave-in)$"),
    ("수돗물", "descriptor", r"No Water|Dirty Water|Low Water Pressure|Water Main Break"),
    ("쥐", "complaint_type", r"^Rodent$"),
    ("보일러", "complaint_type", r"^Boilers$"),
    ("가로등", "descriptor", r"^Street Light Out$"),
]


# --------------------------------------------------------------------------- 휴일
def nth_weekday(y: int, m: int, weekday: int, n: int) -> date:
    """n번째 요일 (n=-1이면 마지막). weekday: 월=0 ... 일=6"""
    if n > 0:
        d = date(y, m, 1)
        d += timedelta(days=(weekday - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)
    d = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def observed(d: date) -> date:
    """토요일 휴일은 금요일, 일요일 휴일은 월요일에 쉽니다."""
    return d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d


def us_federal_holidays(years: range) -> pd.DataFrame:
    rows = []
    for y in years:
        fixed = [("New Year's Day", date(y, 1, 1)), ("Independence Day", date(y, 7, 4)),
                 ("Veterans Day", date(y, 11, 11)), ("Christmas Day", date(y, 12, 25))]
        if y >= 2021:
            fixed.append(("Juneteenth", date(y, 6, 19)))
        rows += [(n, observed(d)) for n, d in fixed]
        rows += [("Martin Luther King Jr. Day", nth_weekday(y, 1, 0, 3)),
                 ("Presidents' Day", nth_weekday(y, 2, 0, 3)),
                 ("Memorial Day", nth_weekday(y, 5, 0, -1)),
                 ("Labor Day", nth_weekday(y, 9, 0, 1)),
                 ("Columbus Day", nth_weekday(y, 10, 0, 2)),
                 ("Thanksgiving Day", nth_weekday(y, 11, 3, 4))]
    out = pd.DataFrame(rows, columns=["holiday_name", "date"])
    out["date"] = pd.to_datetime(out["date"])
    return out.drop_duplicates("date")


# --------------------------------------------------------------------------- 기상 변수
def weather_features(path: Path) -> pd.DataFrame:
    w = pd.read_csv(path, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    for c in LAG_COLS:
        for k in (1, 2, 3):
            w[f"{c}_lag{k}"] = w[c].shift(k)
    w["snowfall_3d"] = w["snowfall_sum"].rolling(3, min_periods=1).sum()        # 당일 포함 3일 누적 적설
    w["precipitation_3d"] = w["precipitation_sum"].rolling(3, min_periods=1).sum()
    w["temperature_2m_max_3d"] = w["temperature_2m_max"].rolling(3, min_periods=1).max()
    w["hot_streak"] = (w["temperature_2m_max"] >= HOT_TMAX).astype(int)
    w["hot_streak"] = w["hot_streak"].groupby((w["hot_streak"] == 0).cumsum()).cumsum()  # 폭염 연속 일수
    w["is_hot"] = (w["temperature_2m_max"] >= HOT_TMAX).astype(int)
    w["is_heavy_rain"] = (w["precipitation_sum"] >= HEAVY_RAIN).astype(int)
    w["is_snow"] = (w["snowfall_sum"] >= SNOW_DAY).astype(int)
    w["is_strong_gust"] = (w["wind_gusts_10m_max"] >= STRONG_GUST).astype(int)
    w["snow_within_3d"] = w["is_snow"].rolling(3, min_periods=1).max().astype(int)  # 최근 3일 안 적설일 여부

    hol = us_federal_holidays(range(w["date"].dt.year.min(), w["date"].dt.year.max() + 1))
    w = w.merge(hol, on="date", how="left")
    w["is_holiday"] = w["holiday_name"].notna().astype(int)
    w["dow"] = w["date"].dt.dayofweek          # 월=0 ... 일=6
    w["is_weekend"] = (w["dow"] >= 5).astype(int)
    return w


# --------------------------------------------------------------------------- 민원
def load_311(path: Path) -> pd.DataFrame:
    """폴더면 월별 파일(nyc311_YYYY-MM.csv)을 모두 읽고, 파일이면 그 파일 하나를 읽습니다."""
    if path.is_dir():
        files = sorted(path.glob("nyc311_[0-9][0-9][0-9][0-9]-[0-9][0-9].csv"))
        if not files:
            raise SystemExit(f"{path}에 월별 파일(nyc311_YYYY-MM.csv)이 없습니다.")
        df = pd.concat((pd.read_csv(f, dtype=str) for f in files), ignore_index=True)
        print(f"월별 파일 {len(files)}개 읽음 ({files[0].name} ~ {files[-1].name})")
    else:
        df = pd.read_csv(path, dtype=str)
    before = len(df)
    df = df.drop_duplicates("unique_key")
    df["agency_raw"] = df["agency"]
    df["agency"] = df["agency"].replace(AGENCY_RENAME)
    for code, name in AGENCY_NAME.items():
        df.loc[df["agency"] == code, "agency_name"] = name
    df["created"] = pd.to_datetime(df["created_date"])
    df["date"] = df["created"].dt.normalize()     # 뉴욕 현지 날짜 (병합 키)
    df["issue"] = "기타"
    for name, col, pat in ISSUES:
        m = df[col].fillna("").str.contains(pat, case=False, regex=True) & (df["issue"] == "기타")
        df.loc[m, "issue"] = name
    print(f"311: {before:,}행 → 중복 제거 후 {len(df):,}행, {df['date'].min().date()} ~ {df['date'].max().date()}")
    return df


def daily_counts(df: pd.DataFrame, by: str, days: pd.DatetimeIndex) -> pd.DataFrame:
    """날짜 × 그룹 건수. 접수가 없는 날도 0으로 채웁니다."""
    c = df.groupby(["date", by]).size().unstack(fill_value=0)
    c = c.reindex(days, fill_value=0)
    c.index.name = "date"
    return c.stack().rename("count").reset_index()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="311 민원 + Open-Meteo 기상 병합")
    p.add_argument("--nyc", type=Path, default=Path("data/raw/nyc311"), help="월별 파일 폴더 또는 합쳐진 311 CSV")
    p.add_argument("--weather", type=Path, default=Path("data/raw/weather/openmeteo_bronx_daily.csv"))
    p.add_argument("--out", type=Path, default=Path("data/processed"))
    a = p.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)

    w = weather_features(a.weather)
    df = load_311(a.nyc)
    days = pd.date_range(df["date"].min(), df["date"].max(), freq="D")

    lost = (~df["date"].isin(w["date"])).sum()
    if lost:
        print(f"경고: 기상 값이 없는 날짜의 민원 {lost:,}건")

    w_out = w[w["date"].isin(days)]
    w_out.to_csv(a.out / "weather_features_daily.csv", index=False)
    print(f"저장: weather_features_daily.csv ({len(w_out):,}일, {w_out.shape[1]}열)")

    for by, name in (("agency", "daily_agency_weather.csv"), ("issue", "daily_issue_weather.csv")):
        d = daily_counts(df, by, days).merge(w_out, on="date", how="left")
        d.to_csv(a.out / name, index=False)
        print(f"저장: {name} ({len(d):,}행 = {len(days):,}일 × {d[by].nunique()}개 {by})")

    keep = [c for c in df.columns if c not in ("created",)]
    merged = df[keep].merge(w_out.drop(columns=["dow"]), on="date", how="left")
    merged.to_csv(a.out / "nyc311_weather_merged.csv.gz", index=False, compression="gzip")
    print(f"저장: nyc311_weather_merged.csv.gz ({len(merged):,}행, {merged.shape[1]}열)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
