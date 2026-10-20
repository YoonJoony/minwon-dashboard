"""Open-Meteo 시간별 기상 다운로드 (관측 + 과거 예보 기록), 미국 단위.

미국 기상청(NWS 뉴욕 지청) 특보 기준을 계산하려면 시간별 값이 필요합니다.
- 열지수(Heat Index): 기온 + 상대습도
- 강풍: 지속 풍속 1시간 이상, 돌풍
- 대설: 12시간·24시간 누적 적설

단위는 NWS 기준과 같게 받습니다: 기온 °F, 풍속 mph, 강수·적설 inch.
시간은 뉴욕 현지 시각입니다.
날씨 코드(weather_code, 세계기상기구 WMO 코드)와 전운량(cloud_cover, %)도 받습니다 (7일 기상 예보 띠 아이콘용).

출력
    data/raw/weather/openmeteo_bronx_hourly_obs.parquet        관측 (Archive API)
    data/raw/weather/openmeteo_bronx_hourly_forecast.parquet   1~7일 전 발표 예보 (Previous Runs API)

사용 예 (프로젝트 루트에서):
    uv run python pipelines/fetch_openmeteo_hourly.py --start 2016-01-01 --end 2026-10-12 --forecast-start 2022-01-01
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

import pandas as pd

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
PREVIOUS = "https://previous-runs-api.open-meteo.com/v1/forecast"
TIMEZONE = "America/New_York"
LAT, LON = 40.84, -73.87
VARS = ["temperature_2m", "relative_humidity_2m", "precipitation", "snowfall", "wind_speed_10m", "wind_gusts_10m",
        "weather_code", "cloud_cover"]
LEADS = [1, 2, 3, 4, 5, 6, 7]
CACHE_TAG = "v2"   # 변수·예보 시점을 늘린 판 (예전 캐시와 섞이지 않게)
UNITS = {"temperature_unit": "fahrenheit", "wind_speed_unit": "mph", "precipitation_unit": "inch"}


def get(url: str) -> dict:
    last: Exception | None = None
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "minwon-dashboard/0.1"})
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode("utf-8"))
        except json.JSONDecodeError as e:          # 큰 요청에 빈 응답이 오는 경우가 있어 다시 시도
            last = e
        except urllib.error.HTTPError as e:
            if e.code not in {429, 500, 502, 503, 504}:
                raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:500]}") from e
            last = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
        wait = min(2 ** attempt * 2, 60)
        print(f"    요청 실패({last}), {wait}초 후 재시도", flush=True)
        time.sleep(wait)
    raise RuntimeError(f"재시도 모두 실패: {last}")


def fetch(endpoint: str, hourly: list[str], start: date, end: date, cache: Path, tag: str) -> pd.DataFrame:
    path = cache / f"{tag}_{start}_{end}.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        params = {"latitude": LAT, "longitude": LON, "start_date": start.isoformat(), "end_date": end.isoformat(),
                  "hourly": ",".join(hourly), "timezone": TIMEZONE, **UNITS}
        data = get(endpoint + "?" + urllib.parse.urlencode(params))
        path.write_text(json.dumps(data), encoding="utf-8")
    df = pd.DataFrame(data["hourly"])
    df["time"] = pd.to_datetime(df["time"])
    return df


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Open-Meteo 시간별 관측·과거 예보 다운로드 (미국 단위)")
    to_date = lambda s: datetime.strptime(s, "%Y-%m-%d").date()
    p.add_argument("--start", type=to_date, required=True)
    p.add_argument("--end", type=to_date, required=True)
    p.add_argument("--forecast-start", type=to_date, default=date(2022, 1, 1))
    p.add_argument("--out-dir", type=Path, default=Path("data/raw/weather"))
    a = p.parse_args(argv)
    cache = a.out_dir / "_cache_hourly"
    cache.mkdir(parents=True, exist_ok=True)

    obs, fc = [], []
    for y in range(a.start.year, a.end.year + 1):
        s, e = max(a.start, date(y, 1, 1)), min(a.end, date(y, 12, 31))
        obs.append(fetch(ARCHIVE, VARS, s, e, cache, f"obs_{CACHE_TAG}"))
        if e >= a.forecast_start:
            # 예보는 열이 많아(8개 변수 × 7개 시점) 한 해를 한 번에 받으면 응답이 비는 경우가 있어 분기로 나눔
            for q in pd.date_range(max(s, a.forecast_start), e, freq="QS"):
                qs = max(q.date(), s, a.forecast_start)
                qe = min((q + pd.offsets.QuarterEnd(0)).date(), e)
                fc.append(fetch(PREVIOUS, [f"{v}_previous_day{d}" for v in VARS for d in LEADS], qs, qe, cache, f"fc_{CACHE_TAG}"))
        print(f"  {y}: 완료", flush=True)

    o = pd.concat(obs, ignore_index=True)
    o.to_parquet(a.out_dir / "openmeteo_bronx_hourly_obs.parquet", index=False)
    f = pd.concat(fc, ignore_index=True)
    f.to_parquet(a.out_dir / "openmeteo_bronx_hourly_forecast.parquet", index=False)
    print(f"저장: 관측 {len(o):,}시간, 예보 {len(f):,}시간 × {f.shape[1] - 1}개 열")
    print("예보 변수별 값이 있는 시간 비율(1일 전):",
          {v: round(f[f'{v}_previous_day1'].notna().mean(), 2) for v in VARS})
    return 0


if __name__ == "__main__":
    sys.exit(main())
