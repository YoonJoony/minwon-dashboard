"""뉴욕시 311 민원 데이터(NYC Open Data) 기간별 다운로드 스크립트.

- 2020년부터는 erm2-nwe9(2020 to Present), 2019년까지는 76ig-c548(2010 to 2019)에서
  받습니다. 달마다 알맞은 데이터셋을 자동으로 고르므로 기간을 걸쳐 지정해도 됩니다.

- 표준 라이브러리만 사용합니다 (추가 설치 없음, Python 3.9 이상).
- 기간을 월 단위로 나눠 받고, 월별 CSV로 저장합니다. 이미 받은 달은 건너뛰므로
  중간에 끊겨도 다시 실행하면 이어서 받습니다.
- 받은 행 수를 서버의 건수(count)와 비교해 누락 여부를 확인합니다.

사용 예:
    # 최근 2년 전체 (기본값)
    python pipelines/fetch_nyc311.py

    # 최근 1년, 끝나면 하나의 CSV로 합치기
    python pipelines/fetch_nyc311.py --months 12 --combine

    # 기간 지정 + 특정 기관만
    python pipelines/fetch_nyc311.py --start 2024-10-01 --end 2026-10-01 --agency HPD DOT DSNY

    # 건수만 확인 (다운로드 안 함), 기관별 건수까지
    python pipelines/fetch_nyc311.py --months 24 --dry-run --by-agency

    # 2016년부터 브롱크스 8개 기관 (2019년 이전 소비자보호국 약어는 DCA)
    python pipelines/fetch_nyc311.py --start 2016-01-01 --borough BRONX \
        --agency DSNY DEP DOT DOB DOHMH DPR DCWP DCA DHS --combine

    # 자치구 하나(구청 하나에 해당)만 받기
    python pipelines/fetch_nyc311.py --months 24 --borough BRONX --exclude-agency NYPD --combine

앱 토큰(선택): https://data.cityofnewyork.us 에서 무료로 발급받아 환경변수로 넣으면
요청 제한이 넉넉해집니다.
    export NYC_APP_TOKEN="발급받은_토큰"
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

ENDPOINT = "https://data.cityofnewyork.us/resource/erm2-nwe9"          # 2020 to Present
ENDPOINT_2010 = "https://data.cityofnewyork.us/resource/76ig-c548"     # 2010 to 2019
SPLIT_DATE = date(2020, 1, 1)

# 프로젝트(접수량 예측·장기처리 분류·위험 매트릭스·심층분석)에 필요한 컬럼만 받습니다.
DEFAULT_COLUMNS = [
    "unique_key",                      # 민원 번호
    "created_date",                    # 접수일시
    "closed_date",                     # 처리완료일시
    "due_date",                        # 처리기한(SLA 기준 갱신 예정일)
    "resolution_action_updated_date",  # 마지막 처리 갱신일시
    "status",                          # 처리 상태
    "agency",                          # 담당 기관 약어 (= 부서)
    "agency_name",                     # 담당 기관명
    "complaint_type",                  # 민원 유형
    "descriptor",                      # 민원 세부 유형
    "location_type",                   # 장소 유형
    "open_data_channel_type",          # 접수 채널 (PHONE, ONLINE, MOBILE ...)
    "borough",                         # 자치구
    "community_board",                 # 커뮤니티 보드
    "incident_zip",                    # 우편번호
    "latitude",
    "longitude",
]

PAGE_SIZE = 50_000          # 한 번에 받는 행 수
MAX_RETRIES = 6             # 요청 실패 시 재시도 횟수
TIMEOUT = 300               # 요청 하나의 제한 시간(초)
RETRY_STATUS = {429, 500, 502, 503, 504}


# --------------------------------------------------------------------------- 기간
def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def month_ranges(start: date, end: date) -> list[tuple[date, date]]:
    """[start, end) 기간을 달력 기준 월 구간으로 나눕니다. 첫·마지막 달은 잘린 구간일 수 있습니다."""
    out: list[tuple[date, date]] = []
    cur = start
    while cur < end:
        nxt = min(add_months(date(cur.year, cur.month, 1), 1), end)
        out.append((cur, nxt))
        cur = nxt
    return out


def soql_ts(d: date) -> str:
    return d.strftime("%Y-%m-%dT00:00:00")


def build_where(start: date, end: date, agencies: list[str] | None,
                exclude: list[str] | None, boroughs: list[str] | None = None) -> str:
    cond = [f"created_date >= '{soql_ts(start)}'", f"created_date < '{soql_ts(end)}'"]
    if boroughs:
        cond.append("borough in(" + ",".join(f"'{b.upper()}'" for b in boroughs) + ")")
    if agencies:
        cond.append("agency in(" + ",".join(f"'{a}'" for a in agencies) + ")")
    if exclude:
        cond.append("agency not in(" + ",".join(f"'{a}'" for a in exclude) + ")")
    return " AND ".join(cond)


# --------------------------------------------------------------------------- HTTP
def http_get(url: str, token: str | None) -> bytes:
    headers = {"Accept-Encoding": "identity", "User-Agent": "minwon-dashboard/0.1"}
    if token:
        headers["X-App-Token"] = token
    req = urllib.request.Request(url, headers=headers)
    last: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_STATUS:
                body = e.read().decode("utf-8", "replace")[:500]
                raise RuntimeError(f"HTTP {e.code}: {body}") from e
            last = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
        wait = min(2 ** attempt * 2, 60)
        print(f"    요청 실패({last}), {wait}초 후 재시도 {attempt + 1}/{MAX_RETRIES - 1}", flush=True)
        time.sleep(wait)
    raise RuntimeError(f"재시도 {MAX_RETRIES}회 모두 실패: {last}")


def endpoint_for(start: date) -> str:
    """월 구간은 달 경계로 잘리므로 한 달은 항상 한 데이터셋에만 속합니다."""
    return ENDPOINT_2010 if start < SPLIT_DATE else ENDPOINT


def query_url(fmt: str, params: dict[str, str], endpoint: str = ENDPOINT) -> str:
    return f"{endpoint}.{fmt}?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


def server_count(where: str, token: str | None, endpoint: str = ENDPOINT) -> int:
    raw = http_get(query_url("json", {"$select": "count(*) AS n", "$where": where}, endpoint), token)
    rows = json.loads(raw.decode("utf-8"))
    return int(rows[0]["n"]) if rows else 0


def agency_counts(where: str, token: str | None, endpoint: str = ENDPOINT) -> list[tuple[str, int]]:
    params = {"$select": "agency, count(*) AS n", "$where": where,
              "$group": "agency", "$order": "n DESC", "$limit": "500"}
    rows = json.loads(http_get(query_url("json", params, endpoint), token).decode("utf-8"))
    return [(r.get("agency", "(없음)"), int(r["n"])) for r in rows]


def fetch_pages(where: str, columns: list[str], token: str | None,
                endpoint: str = ENDPOINT) -> Iterator[list[list[str]]]:
    """한 기간의 데이터를 페이지 단위로 돌려줍니다. 각 페이지의 첫 행은 헤더입니다."""
    offset = 0
    while True:
        params = {
            "$select": ",".join(columns),
            "$where": where,
            "$order": "created_date, unique_key",   # 정렬을 고정해야 페이지 간 누락·중복이 없습니다
            "$limit": str(PAGE_SIZE),
            "$offset": str(offset),
        }
        text = http_get(query_url("csv", params, endpoint), token).decode("utf-8")
        rows = list(csv.reader(io.StringIO(text)))
        if len(rows) <= 1:          # 헤더만 있거나 비어 있으면 끝
            return
        yield rows
        if len(rows) - 1 < PAGE_SIZE:
            return
        offset += PAGE_SIZE


# --------------------------------------------------------------------------- 저장
def download_month(start: date, end: date, out_dir: Path, columns: list[str],
                   agencies: list[str] | None, exclude: list[str] | None,
                   token: str | None, dry_run: bool,
                   boroughs: list[str] | None = None) -> tuple[str, int, int]:
    """한 달 치를 받아 저장합니다. (상태, 서버 건수, 받은 건수)를 돌려줍니다."""
    tag = start.strftime("%Y-%m")
    path = out_dir / f"nyc311_{tag}.csv"
    where = build_where(start, end, agencies, exclude, boroughs)
    endpoint = endpoint_for(start)

    if path.exists() and not dry_run:
        return "skip", -1, -1

    expected = server_count(where, token, endpoint)
    if dry_run:
        return "dry", expected, 0

    tmp = path.with_suffix(".csv.part")
    got = 0
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        header_written = False
        for rows in fetch_pages(where, columns, token, endpoint):
            if not header_written:
                w.writerow(rows[0])
                header_written = True
            w.writerows(rows[1:])
            got += len(rows) - 1
            print(f"    {tag}: {got:,} / {expected:,}행", flush=True)
        if not header_written:
            w.writerow(columns)

    if got != expected:
        # 받는 도중 서버 데이터가 갱신되면 약간 차이 날 수 있습니다. 파일은 남기고 경고만 합니다.
        print(f"    경고: {tag} 서버 건수 {expected:,}행, 받은 행 {got:,}행", flush=True)
    tmp.replace(path)
    return "ok", expected, got


def combine(files: list[Path], target: Path) -> int:
    total = 0
    with target.open("w", newline="", encoding="utf-8") as fo:
        w = csv.writer(fo)
        for i, p in enumerate(files):
            with p.open(newline="", encoding="utf-8") as fi:
                r = csv.reader(fi)
                header = next(r, None)
                if header is None:
                    continue
                if i == 0:
                    w.writerow(header)
                for row in r:
                    w.writerow(row)
                    total += 1
    return total


# --------------------------------------------------------------------------- CLI
def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="뉴욕시 311 민원 데이터 월별 다운로드")
    p.add_argument("--months", type=int, default=24, help="오늘 기준 최근 N개월 (기본 24). --start를 주면 무시")
    p.add_argument("--start", type=parse_date, help="시작일 YYYY-MM-DD (포함)")
    p.add_argument("--end", type=parse_date, help="종료일 YYYY-MM-DD (미포함, 기본: 오늘)")
    p.add_argument("--agency", nargs="+", help="받을 기관 약어만 지정 (예: HPD DOT DSNY)")
    p.add_argument("--exclude-agency", nargs="+", help="제외할 기관 약어 (예: NYPD)")
    p.add_argument("--borough", nargs="+",
                   help="자치구만 받기: BRONX BROOKLYN MANHATTAN QUEENS 'STATEN ISLAND'")
    p.add_argument("--by-agency", action="store_true",
                   help="--dry-run과 함께: 전체 기간의 기관별 건수 표시 (기관 고르기용)")
    p.add_argument("--columns", nargs="+", default=DEFAULT_COLUMNS, help="받을 컬럼 (기본: 프로젝트 필수 컬럼)")
    p.add_argument("--out", type=Path, default=Path("data/raw/nyc311"), help="저장 폴더")
    p.add_argument("--combine", action="store_true", help="다 받은 뒤 하나의 CSV로 합치기")
    p.add_argument("--dry-run", action="store_true", help="월별 건수만 확인하고 받지 않기")
    a = p.parse_args(argv)

    end = a.end or date.today()
    start = a.start or add_months(date(end.year, end.month, 1), -a.months)
    if start >= end:
        p.error("시작일이 종료일보다 앞이어야 합니다.")

    token = os.environ.get("NYC_APP_TOKEN")
    a.out.mkdir(parents=True, exist_ok=True)
    months = month_ranges(start, end)

    print(f"기간: {start} ~ {end} (종료일 미포함), {len(months)}개월")
    print(f"저장 위치: {a.out.resolve()}")
    if a.agency:
        print(f"기관: {', '.join(a.agency)}")
    if a.exclude_agency:
        print(f"제외 기관: {', '.join(a.exclude_agency)}")
    if a.borough:
        print(f"자치구: {', '.join(b.upper() for b in a.borough)}")
    if not token:
        print("참고: NYC_APP_TOKEN이 없어 요청 제한이 낮을 수 있습니다 (없어도 동작).")

    total_expected = total_got = 0
    t0 = time.time()
    for s, e in months:
        status, expected, got = download_month(s, e, a.out, a.columns, a.agency,
                                               a.exclude_agency, token, a.dry_run, a.borough)
        tag = s.strftime("%Y-%m")
        if status == "skip":
            print(f"  {tag}: 이미 있음, 건너뜀")
        elif status == "dry":
            print(f"  {tag}: {expected:,}건")
            total_expected += expected
        else:
            print(f"  {tag}: 완료 {got:,}행")
            total_expected += expected
            total_got += got

    if a.dry_run:
        weeks = max((end - start).days / 7, 1)
        print(f"합계: {total_expected:,}건, 주당 평균 {total_expected / weeks:,.0f}건 "
              f"(CSV 약 {total_expected * 330 / 1e9:.2f}GB, 대략치)")
        if a.by_agency:
            where = build_where(start, end, a.agency, a.exclude_agency, a.borough)
            print("기관별 건수 (많은 순):")
            totals: dict[str, int] = {}
            for ep in {endpoint_for(s) for s, _ in months}:
                for ag, n in agency_counts(where, token, ep):
                    totals[ag] = totals.get(ag, 0) + n
            for ag, n in sorted(totals.items(), key=lambda kv: -kv[1]):
                print(f"  {ag:<8} {n:>12,}건  주당 {n / weeks:>9,.0f}건")
        return 0

    print(f"새로 받은 행: {total_got:,} / 서버 건수 {total_expected:,} ({time.time() - t0:.0f}초)")
    if a.combine:
        target = a.out / f"nyc311_{start:%Y%m%d}_{end:%Y%m%d}.csv"
        files = [a.out / f"nyc311_{s:%Y-%m}.csv" for s, _ in months]
        n = combine([f for f in files if f.exists()], target)
        print(f"합친 파일: {target} ({n:,}행)")
    return 0


if __name__ == "__main__":
    sys.exit(main())