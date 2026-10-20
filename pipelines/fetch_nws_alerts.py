"""미국 기상청(NWS) 실제 발표 특보 기록 다운로드 — 아이오와 주립대 IEM 보관소.

브롱크스에 발표된 주의보·경보·주의(Watch) 기록을 받습니다.
- NYZ073: 브롱크스 예보 구역 (폭염·강풍·겨울 폭풍 등 대부분의 특보)
- NYC005: 브롱크스 카운티 (돌발 홍수 경보 등 카운티 단위로 나오는 특보)

출력: data/raw/nws/nws_alerts_bronx.csv  (한 행 = 특보 1건 × 구역)
주요 열: phenomena(종류: HT 폭염, XH·EH 극한 폭염, WI·HW 강풍, WW·WS·BZ 겨울 폭풍·눈보라, FF·FA·FL 홍수),
        significance(Y 주의보, W 경보, A 주의), issued·expired(UTC), name

사용 예 (프로젝트 루트에서):
    uv run python pipelines/fetch_nws_alerts.py --start 2016-01-01 --end 2026-10-20
"""
from __future__ import annotations

import argparse
import io
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

URL = "https://mesonet.agron.iastate.edu/json/vtec_events_byugc.php"
UGCS = ["NYZ073", "NYC005"]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="NWS 특보 기록(IEM) 다운로드")
    p.add_argument("--start", default="2016-01-01")
    p.add_argument("--end", default="2026-10-20")
    p.add_argument("--out", type=Path, default=Path("data/raw/nws/nws_alerts_bronx.csv"))
    a = p.parse_args(argv)
    frames = []
    for ugc in UGCS:
        q = urllib.parse.urlencode({"ugc": ugc, "sdate": a.start, "edate": a.end, "fmt": "csv"})
        req = urllib.request.Request(f"{URL}?{q}", headers={"User-Agent": "minwon-dashboard/0.1"})
        with urllib.request.urlopen(req, timeout=120) as r:
            df = pd.read_csv(io.StringIO(r.read().decode("utf-8")))
        print(f"  {ugc}: {len(df):,}건")
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False)
    print(f"저장: {a.out} ({len(out):,}건)")
    print(out.groupby(["ph_name", "sig_name"]).size().sort_values(ascending=False).head(15).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
