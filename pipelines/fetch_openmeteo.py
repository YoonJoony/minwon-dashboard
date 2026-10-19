"""Open-Meteo 과거 기상(Archive API) 일별 데이터 다운로드 스크립트.

- 표준 라이브러리만 사용합니다 (추가 설치 없음, Python 3.9 이상).
- 뉴욕 현지 날짜 기준(timezone=America/New_York)으로 받습니다. 311 접수일시도 현지 시각이므로
  날짜만 맞추면 그대로 병합됩니다.
- 일별 값에 더해, 시간별 값으로 하루 단위 파생 변수(폭염 시간, 영하 시간, 1시간 최대 강수, 적설 깊이)를 만듭니다.
- 연 단위로 나눠 받고, 받은 연도는 data/raw/weather/_cache/ 에 저장해 다시 받지 않습니다.

사용 예:
    # 브롱크스, 2016-01-01 ~ 2026-10-13
    python pipelines/fetch_openmeteo.py --start 2016-01-01 --end 2026-10-13

    # 다른 지점
    python pipelines/fetch_openmeteo.py --lat 40.71 --lon -74.01 --out data/raw/weather/openmeteo_manhattan_daily.csv

참고: Open-Meteo 무료 API는 비상업적 용도 기준입니다. 상용 서비스로 운영할 때는 유료 API 키가 필요합니다.
Archive API는 최근 5일 정도는 아직 값이 없을 수 있습니다.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"
TIMEZONE = "America/New_York"

# 브롱크스 중심부. Open-Meteo는 가장 가까운 격자점 값을 돌려줍니다.
DEFAULT_LAT, DEFAULT_LON = 40.84, -73.87

DAILY = [
    "temperature_2m_max",        # 최고기온 (°C)
    "temperature_2m_min",        # 최저기온 (°C)
    "temperature_2m_mean",       # 평균기온 (°C)
    "apparent_temperature_max",  # 최고 체감온도 (°C)
    "apparent_temperature_min",  # 최저 체감온도 (°C)
    "precipitation_sum",         # 강수량 합계 (mm, 비+눈 환산)
    "rain_sum",                  # 비 (mm)
    "snowfall_sum",              # 신적설 (cm)
    "precipitation_hours",       # 강수 시간 (h)
    "wind_speed_10m_max",        # 최대 풍속 (km/h)
    "wind_gusts_10m_max",        # 최대 돌풍 (km/h)
    "weather_code",              # 대표 날씨 코드 (WMO)
]
HOURLY = ["temperature_2m", "precipitation", "snow_depth"]

HOT_C = 32.0       # 폭염 기준 시간 기온
FREEZE_C = 0.0     # 결빙 기준 시간 기온

MAX_RETRIES = 6
TIMEOUT = 120
RETRY_STATUS = {429, 500, 502, 503, 504}


def http_get_json(url: str) -> dict:
    last: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "minwon-dashboard/0.1"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_STATUS:
                raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:500]}") from e
            last = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
        wait = min(2 ** attempt * 2, 60)
        print(f"    요청 실패({last}), {wait}초 후 재시도 {attempt + 1}/{MAX_RETRIES - 1}", flush=True)
        time.sleep(wait)
    raise RuntimeError(f"재시도 {MAX_RETRIES}회 모두 실패: {last}")


def fetch_year(lat: float, lon: float, start: date, end: date, cache: Path) -> dict:
    """[start, end] 구간(양 끝 포함)을 받아 캐시에 저장합니다."""
    path = cache / f"{lat:.3f}_{lon:.3f}_{start}_{end}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "daily": ",".join(DAILY), "hourly": ",".join(HOURLY), "timezone": TIMEZONE,
    }
    data = http_get_json(ENDPOINT + "?" + urllib.parse.urlencode(params))
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def hourly_to_daily(hourly: dict) -> dict[str, dict]:
    """시간별 값으로 하루 단위 파생 변수를 만듭니다. 시각은 이미 현지 시각입니다."""
    agg: dict[str, dict] = defaultdict(lambda: {"hot_hours": 0, "freezing_hours": 0,
                                                 "precip_max_1h": None, "snow_depth_max": None})
    for t, temp, pr, sd in zip(hourly["time"], hourly["temperature_2m"],
                               hourly["precipitation"], hourly["snow_depth"]):
        d = agg[t[:10]]
        if temp is not None:
            d["hot_hours"] += temp >= HOT_C
            d["freezing_hours"] += temp <= FREEZE_C
        if pr is not None:
            d["precip_max_1h"] = pr if d["precip_max_1h"] is None else max(d["precip_max_1h"], pr)
        if sd is not None:
            d["snow_depth_max"] = sd if d["snow_depth_max"] is None else max(d["snow_depth_max"], sd)
    return agg


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Open-Meteo 과거 기상 일별 데이터 다운로드")
    p.add_argument("--start", type=parse_date, required=True, help="시작일 YYYY-MM-DD (포함)")
    p.add_argument("--end", type=parse_date, required=True, help="종료일 YYYY-MM-DD (포함)")
    p.add_argument("--lat", type=float, default=DEFAULT_LAT)
    p.add_argument("--lon", type=float, default=DEFAULT_LON)
    p.add_argument("--out", type=Path, default=Path("data/raw/weather/openmeteo_bronx_daily.csv"))
    a = p.parse_args(argv)

    a.out.parent.mkdir(parents=True, exist_ok=True)
    cache = a.out.parent / "_cache"
    cache.mkdir(exist_ok=True)

    rows: list[dict] = []
    grid = None
    for y in range(a.start.year, a.end.year + 1):
        s, e = max(a.start, date(y, 1, 1)), min(a.end, date(y, 12, 31))
        data = fetch_year(a.lat, a.lon, s, e, cache)
        grid = (data.get("latitude"), data.get("longitude"), data.get("elevation"))
        daily, extra = data["daily"], hourly_to_daily(data["hourly"])
        for i, t in enumerate(daily["time"]):
            row = {"date": t}
            row.update({k: daily[k][i] for k in DAILY})
            row.update(extra.get(t, {}))
            rows.append(row)
        print(f"  {y}: {len(daily['time'])}일", flush=True)

    cols = ["date"] + DAILY + ["hot_hours", "freezing_hours", "precip_max_1h", "snow_depth_max"]
    with a.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    missing = sum(1 for r in rows if r["temperature_2m_max"] is None)
    print(f"저장: {a.out} ({len(rows):,}일, 기온 결측 {missing}일)")
    print(f"격자점: 위도 {grid[0]}, 경도 {grid[1]}, 고도 {grid[2]}m, 시간대 {TIMEZONE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
