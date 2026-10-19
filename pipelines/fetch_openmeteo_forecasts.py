"""Open-Meteo 과거 예보 기록(Previous Runs API) 다운로드 스크립트.

"N일 전에 발표된 예보가 그날 날씨를 뭐라고 했는지"를 날짜별로 받습니다.
실제 운영처럼 **예보만 보고** 경보를 냈을 때의 적중률을 검증하는 데 씁니다.

- 시간별 예보(1·2·3·5·7일 전 발표분)를 받아 뉴욕 현지 날짜 기준 일 단위로 묶습니다.
- 연 단위로 받아 data/raw/weather/_cache_forecast/ 에 저장해 다시 받지 않습니다.

사용 예 (프로젝트 루트에서):
    python pipelines/fetch_openmeteo_forecasts.py --start 2022-01-01 --end 2026-10-12
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

ENDPOINT = "https://previous-runs-api.open-meteo.com/v1/forecast"
TIMEZONE = "America/New_York"
DEFAULT_LAT, DEFAULT_LON = 40.84, -73.87
LEADS = [1, 2, 3, 5, 7]
BASE = ["temperature_2m", "precipitation", "snowfall", "wind_gusts_10m"]
AGG = {"temperature_2m": ("tmax", max), "precipitation": ("precip", sum),
       "snowfall": ("snow", sum), "wind_gusts_10m": ("gust", max)}


def http_get_json(url: str) -> dict:
    last: Exception | None = None
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "minwon-dashboard/0.1"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
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


def fetch(lat: float, lon: float, start: date, end: date, cache: Path) -> dict:
    path = cache / f"{lat:.3f}_{lon:.3f}_{start}_{end}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    hourly = [f"{v}_previous_day{d}" for v in BASE for d in LEADS]
    params = {"latitude": lat, "longitude": lon, "start_date": start.isoformat(), "end_date": end.isoformat(),
              "hourly": ",".join(hourly), "timezone": TIMEZONE}
    data = http_get_json(ENDPOINT + "?" + urllib.parse.urlencode(params))
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Open-Meteo 과거 예보 기록 다운로드")
    p.add_argument("--start", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(), required=True)
    p.add_argument("--end", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(), required=True)
    p.add_argument("--lat", type=float, default=DEFAULT_LAT)
    p.add_argument("--lon", type=float, default=DEFAULT_LON)
    p.add_argument("--out", type=Path, default=Path("data/raw/weather/openmeteo_bronx_forecasts_daily.csv"))
    a = p.parse_args(argv)
    cache = a.out.parent / "_cache_forecast"
    cache.mkdir(parents=True, exist_ok=True)

    days: dict[tuple[str, int], dict] = defaultdict(dict)
    for y in range(a.start.year, a.end.year + 1):
        s, e = max(a.start, date(y, 1, 1)), min(a.end, date(y, 12, 31))
        h = fetch(a.lat, a.lon, s, e, cache)["hourly"]
        for var, (name, fn) in AGG.items():
            for d in LEADS:
                col = h[f"{var}_previous_day{d}"]
                by_day: dict[str, list[float]] = defaultdict(list)
                for t, v in zip(h["time"], col):
                    if v is not None:
                        by_day[t[:10]].append(v)
                for day, vals in by_day.items():
                    days[(day, d)][name] = round(fn(vals), 2) if len(vals) >= 20 else None
        print(f"  {y}: 완료", flush=True)

    with a.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "lead_days", "tmax", "precip", "snow", "gust"])
        for (day, d), v in sorted(days.items()):
            w.writerow([day, d, v.get("tmax"), v.get("precip"), v.get("snow"), v.get("gust")])
    print(f"저장: {a.out} ({len(days):,}행 = 날짜 × 예보 시점 {LEADS}일 전)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
