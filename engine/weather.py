"""7일 기상 예보 띠와 과거 7년 모달 — docs/기상예보_기능_검증.md
(analysis/verify_forecast_strip.py, analysis/verify_weather_events.py와 같은 정의).

예보 띠
- 칸: 기준일 포함 8일. 오늘 칸은 전날 발표(1일 전) 예보, +k일 칸은 기준일에 발표된 k일 전 예보
- 날씨 아이콘: 뇌우(강수 1mm 이상 + 날씨 코드 95~99) → 눈(적설 1cm 이상) → 비(강수 1mm 이상)
  → 흐림(낮 7~19시 평균 전운량 80% 이상) → 구름많음(40% 이상) → 맑음
- 특보 수준: 폭염·강풍·대설은 예보 값에 NWS 기준을 대입해 판정, 호우는 실제 발표된 NWS 특보만
- 실제 NWS 특보: 기준일까지 발표된 것만

과거 사건 (모달)
- 폭염·대설·강풍: 관측 날씨가 NWS 기준 특보 수준인 날이 이어진 기간 (하루 쉬고 다시 오면 같은 사건)
- 호우: 실제 발표된 NWS 홍수 주의보·돌발 홍수 경보가 걸린 날이 이어진 기간
- 영향 기간 = [첫날 + a일, 마지막 날 + b일] (engine.config.WEATHER_WINDOW). 영향 기간이 겹치면 한 사건
- 평소 = 영향 기간 직전 28일 중 같은 종류의 다른 영향 기간을 뺀 날의 하루 중앙값
- 영향 기간 내 처리 = 영향 기간에 접수된 민원 중 영향 기간 끝까지 처리(완료일이 있고 상태 Closed)된 수
"""
import numpy as np
import pandas as pd

from engine import alerts as al
from engine.config import NWS_ALERTS, WEATHER_ISSUES, WEATHER_LABEL, WEATHER_WINDOW
from engine.data import HOURLY_COLS, forecast_lead_sky, nws_alerts_raw

D = pd.Timedelta
NY = "America/New_York"
ICON_LABEL = {"clear": "맑음", "partly": "구름많음", "cloudy": "흐림", "rain": "비", "snow": "눈", "thunder": "뇌우"}


# ------------------------------------------------------------------ 예보 띠
def daily_summary(h: pd.DataFrame) -> pd.DataFrame:
    """시간별(t °F, prcp·snow inch, gust mph, code WMO, cloud %) → 날짜별 아이콘·최고/최저 기온(°C)·강수(mm)·적설(cm)·돌풍(km/h)."""
    g = h.set_index("time").sort_index()
    day = g.index.normalize()
    daytime = g[(g.index.hour >= 7) & (g.index.hour <= 19)]
    out = pd.DataFrame({
        "tmax": (g.t.groupby(day).max() - 32) * 5 / 9,
        "tmin": (g.t.groupby(day).min() - 32) * 5 / 9,
        "prcp": g.prcp.groupby(day).sum(min_count=20) * 25.4,
        "snow": g.snow.groupby(day).sum(min_count=20) * 2.54,
        "gust": g.gust.groupby(day).max() * 1.609,
        "cloud": daytime.cloud.groupby(daytime.index.normalize()).mean(),
        "thunder": g.code.ge(95).groupby(day).any(),
    })
    icon = np.select([out.thunder & (out.prcp >= 1), out.snow >= 1, out.prcp >= 1, out.cloud >= 80, out.cloud >= 40],
                     ["thunder", "snow", "rain", "cloudy", "partly"], "clear")
    out["icon"] = pd.Series(icon, index=out.index).where(out.cloud.notna() & out.prcp.notna())
    return out.drop(columns="thunder")


def forecast_days(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """날짜 × 예보 시점(1~7일 전) 하루 요약과 특보 수준. 예보 띠는 기준일마다 여기서 골라 씀."""
    rows = []
    for lead in range(1, 8):
        h = forecast_lead_sky(lead)
        lv = al.daily_levels(h[["time"] + HOURLY_COLS])
        t = daily_summary(h).join(lv[["heat", "wind", "snow", "valid_heat", "valid_wind", "valid_snow"]].rename(
            columns={"snow": "snow_level", "heat": "heat_level", "wind": "wind_level"}))
        for k in ("heat", "wind", "snow"):                     # 예보 값이 빠진 날은 특보 판정 안 함
            t[f"{k}_level"] = t[f"{k}_level"].where(t[f"valid_{k}"].fillna(False).astype(bool), 0)
        t = t[(t.index >= start) & (t.index <= end)].drop(columns=["valid_heat", "valid_wind", "valid_snow"])
        rows.append(t.assign(lead=lead))
    return pd.concat(rows).rename_axis("date").reset_index()


# ------------------------------------------------------------------ 실제 발표된 NWS 특보
def _local(t: pd.Timestamp) -> pd.Timestamp:
    return t.tz_convert(NY).tz_localize(None)


def nws_alerts() -> pd.DataFrame:
    """특보 1건 = 종류·단계·이름·발표 시각·유효 기간 (뉴욕 시각). 같은 특보가 구역·카운티로 두 번 나오면 하나로."""
    rows = []
    for r in nws_alerts_raw().itertuples():
        m = NWS_ALERTS.get((r.phenomena, r.significance))
        if m is None:
            continue
        issued = _local(pd.to_datetime(r.product_id[:12], format="%Y%m%d%H%M", utc=True))
        start, end = _local(pd.Timestamp(r.iso_issued)), _local(pd.Timestamp(r.iso_expired))
        if end <= start:                                     # 주의(Watch)가 경보로 바뀌며 일찍 끝난 경우
            end = start + D(days=1)
        rows.append({"kind": m[0], "level": m[1], "name": m[2], "name_en": r.name, "issued": issued, "start": start, "end": end})
    return pd.DataFrame(rows).drop_duplicates(["kind", "level", "name", "start"]).sort_values("start").reset_index(drop=True)


def nws_daily_levels(nws: pd.DataFrame, days: pd.DatetimeIndex) -> pd.DataFrame:
    """날짜별 실제 발표 특보 단계 (주의보 1·경보 2, 예비특보 제외). 유효 기간이 그날에 조금이라도 걸치면 그날 특보."""
    lv = pd.DataFrame(0, index=days, columns=list(WEATHER_LABEL))
    for r in nws[nws.level >= 1].itertuples():
        for d in pd.date_range(r.start.normalize(), (r.end - D(minutes=1)).normalize()):
            if d in lv.index:
                lv.at[d, r.kind] = max(lv.at[d, r.kind], r.level)
    return lv


# ------------------------------------------------------------------ 과거 사건
def _runs(levels: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp, int]]:
    out: list[list] = []
    for d in levels.index[levels >= 1]:
        if out and (d - out[-1][1]).days <= 2:
            out[-1][1] = d
        else:
            out.append([d, d])
    return [(a, b, int(levels.loc[a:b].max())) for a, b in out]


def history_events(obs_levels: pd.DataFrame, nws: pd.DataFrame, complaints: pd.DataFrame, data_end: pd.Timestamp) -> pd.DataFrame:
    """과거 사건 × 대상 민원 (2016-02 ~ 데이터 끝). 기준일별 선택은 API에서 (기준일 전에 끝난 사건만)."""
    days = pd.date_range("2016-02-01", data_end)
    levels = obs_levels.reindex(days)[["heat", "snow", "wind"]].fillna(0).astype(int)
    levels["rain"] = nws_daily_levels(nws, days)["rain"]
    issues = [i for v in WEATHER_ISSUES.values() for i in v]
    cf = complaints[complaints.issue.isin(issues)]
    daily = cf.groupby([cf.created.dt.normalize(), "issue"]).size().unstack(fill_value=0)
    daily = daily.reindex(index=pd.date_range("2016-01-01", data_end), columns=issues, fill_value=0)
    rows = []
    for kind, (a_off, b_off) in WEATHER_WINDOW.items():
        merged: list[list] = []
        for a, b, lvl in _runs(levels[kind]):
            ws, we = a + D(days=a_off), b + D(days=b_off)
            if merged and ws <= merged[-1][3] + D(days=1):
                merged[-1][1], merged[-1][3], merged[-1][4] = b, we, max(merged[-1][4], lvl)
            else:
                merged.append([a, b, ws, we, lvl])
        windows = [(ws, we) for _, _, ws, we, _ in merged]
        for eid, (a, b, ws, we, lvl) in enumerate(merged):
            if we > data_end:
                continue
            k_nws = nws[(nws.kind == kind) & (nws.level >= 1) & (nws.start < b + D(days=1)) & (nws.end > a)]
            names = list(dict.fromkeys(k_nws.sort_values("level", ascending=False).name))
            for issue in WEATHER_ISSUES[kind]:
                s = daily[issue]
                prev = s.loc[ws - D(days=28): ws - D(days=1)]
                keep = pd.Series(True, index=prev.index)
                for x, y in windows:
                    keep &= ~((prev.index >= x) & (prev.index <= y))
                base = float(prev[keep].median()) if keep.sum() >= 7 else float(prev.median())
                n = (we - ws).days + 1
                sub = cf[(cf.issue == issue) & (cf.created >= ws) & (cf.created < we + D(days=1))]
                done = lambda t, sub=sub: int((sub.closed.notna() & (sub.closed < t) & (sub.status == "Closed")).sum())
                win = s.loc[ws:we]
                rows.append({
                    "kind": kind, "event": eid, "start": a, "end": b, "level": lvl, "win_start": ws, "win_end": we, "days": n,
                    "nws": " · ".join(names), "issue": issue, "base": base, "received": len(sub),
                    "excess": len(sub) - base * n, "processed": done(we + D(days=1)), "processed_7": done(we + D(days=8)),
                    "peak": int(win.max()), "surge": bool(((win >= 2 * max(base, 1)) & (win >= 20)).any()),
                })
    return pd.DataFrame(rows)
