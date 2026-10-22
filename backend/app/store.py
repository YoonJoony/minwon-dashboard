"""사전 계산 결과(data/artifacts)를 메모리에 올려 두고 화면별 응답을 만듭니다.

용량이 작아(수십 MB) 서버 시작 때 Parquet을 모두 읽어 둡니다. 계산은 engine.dashboard의 함수를 그대로 씁니다.
"""
import json
import re

import numpy as np
import pandas as pd
from fastapi import HTTPException

from app.config import ARTIFACTS
from engine.config import (
    AGENCIES,
    AGENCY_INFO,
    ALERT_INFO,
    HISTORY_SEASON_DAYS,
    HISTORY_YEARS,
    ISSUE_INFO,
    LINKS,
    MAX_DAYS,
    PER_PERSON_DEFAULT,
    STRIP_DAYS,
    STRIP_FORECAST_DAYS,
    SUPPORT_X,
    WEATHER_ISSUES,
    WEATHER_LABEL,
    WEATHER_WINDOW,
    X_TH,
    Y_TH,
)
from engine.content import COMPLAINT_KO
from engine.dashboard import QUADRANTS, AsofData, matrix, period_forecast, staffing
from engine.weather import ICON_LABEL

D = pd.Timedelta
ALERT_ICON = {"heat": "flame", "snow": "snowflake", "wind": "wind", "rain": "cloud-rain"}
ISSUE_ICON = {"폭염·소화전": "flame", "수돗물": "droplets", "결빙·제설": "snowflake", "폭우·침수": "cloud-rain",
              "강풍·수목": "wind", "도로 파손": "construction", "가로등": "lamp", "쥐": "rat", "보일러": "heater"}
ALERT_AGENCY = {}
for _kind, _issue, _dept, _ in LINKS:
    ALERT_AGENCY.setdefault(_kind, [])
    if _dept not in ALERT_AGENCY[_kind]:
        ALERT_AGENCY[_kind].append(_dept)
WEEKDAY = ["월", "화", "수", "목", "금", "토", "일"]
DATA_NOTE = ("데이터: 뉴욕시 311 민원 (브롱크스, 8개 기관, 2016-01 ~ 2026-10-12) · 기상: Open-Meteo 관측·예보 기록 · "
             "특보 기준: 미국 기상청(NWS) 뉴욕 지청 · 모든 수치는 기준일까지의 데이터와 그날 발표된 예보만으로 계산")


def _f(v) -> float | None:
    return None if v is None or (isinstance(v, float) and np.isnan(v)) or pd.isna(v) else float(v)


def _d(t: pd.Timestamp) -> str:
    return f"{t:%Y-%m-%d}"


def _md(t: pd.Timestamp) -> str:
    return f"{t.month}/{t.day}"


def _ko_factors(text: str) -> str:
    """위험 요인 문구 속 민원 유형(영문)을 화면 표기로 바꿈. '세부 유형'은 원문 유지."""
    return re.sub(r"(?<!세부 )유형: ([^·]+?)(?= ·|$)", lambda m: f"유형: {COMPLAINT_KO.get(m.group(1), m.group(1))}", text)


class Store:
    def __init__(self, path=ARTIFACTS):
        self.path = path
        man = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        self.manifest = man
        rd = lambda n: pd.read_parquet(path / f"{n}.parquet")
        self.asofs = [pd.Timestamp(x) for x in man["asofs"]]
        self.data_end = pd.Timestamp(man["data_end"])
        self.latest = pd.Timestamp(man["latest"])
        by = lambda df: {k: g.drop(columns="asof") for k, g in df.groupby("asof")}
        self._fd = by(rd("forecast_daily"))
        self._iv = by(rd("intervals"))
        self._af = by(rd("affected"))
        self._st = by(rd("dept_state"))
        self._al = by(rd("alerts"))
        self._cal = by(rd("issue_calendar"))
        pot = rd("pothole")
        self._pot = {r.asof: r for r in pot.itertuples()} if len(pot) else {}
        self._rl = by(rd("risk_list"))
        self._rc = by(rd("risk_counts"))
        self.cnt = rd("actual_daily").pivot(index="date", columns="agency", values="count")[AGENCIES]
        self.iss = rd("issue_daily").pivot(index="date", columns="issue", values="count")
        self._cache: dict[pd.Timestamp, AsofData] = {}
        # 7일 기상 예보 띠 · 과거 7년 모달 (예전 사전 계산 결과에는 없을 수 있음)
        opt = lambda n: rd(n) if (path / f"{n}.parquet").exists() else pd.DataFrame()
        self._fdays = opt("forecast_days")
        if len(self._fdays):
            self._fdays = self._fdays.set_index(["date", "lead"]).sort_index()
        self._nws = opt("nws_alerts")
        self._wev = opt("weather_events")

    # ------------------------------------------------------------------ 공통
    def period(self, asof: str, start: str | None, end: str | None):
        try:
            a = pd.Timestamp(asof)
            s = pd.Timestamp(start) if start else a
            e = pd.Timestamp(end) if end else a + D(days=6)
        except ValueError as err:
            raise HTTPException(400, f"날짜 형식이 올바르지 않습니다: {err}") from err
        if a not in self.asofs:
            raise HTTPException(400, f"기준일 {asof}는 사전 계산 목록에 없습니다. /api/meta의 asofs에서 고르세요.")
        if s < a or e < s:
            raise HTTPException(400, "기간은 기준일 이후여야 하고, 끝 날짜가 시작 날짜보다 늦어야 합니다.")
        if e > a + D(days=MAX_DAYS - 1):
            raise HTTPException(400, f"기간은 기준일부터 최대 {MAX_DAYS}일까지 선택할 수 있습니다.")
        return a, s, e

    def asof_data(self, a: pd.Timestamp) -> AsofData:
        if a in self._cache:
            return self._cache[a]
        empty_af = pd.DataFrame(columns=["agency", "flag", "level", "reason", "factor", "start", "end", "extra_per_day"])
        self._cache[a] = AsofData(a, self._fd[a], self._iv[a], self._af.get(a, empty_af), self._st[a])
        return self._cache[a]

    def actual(self, s: pd.Timestamp, e: pd.Timestamp) -> pd.Series | None:
        return self.cnt.loc[s:e].sum() if e <= self.data_end else None

    def period_out(self, a, s, e, source: str) -> dict:
        return {"asof": _d(a), "start": _d(s), "end": _d(e), "days": (e - s).days + 1, "source": source,
                "has_actual": bool(e <= self.data_end)}

    def _matrix(self, a, s, e) -> pd.DataFrame:
        return matrix(self.asof_data(a), s, e, self.actual(s, e))

    # ------------------------------------------------------------------ 메타
    def meta(self) -> dict:
        return {
            "app_name": "스마트 민원케어",
            "agencies": [{"code": c, **AGENCY_INFO[c]} for c in AGENCIES],
            "asofs": [_d(x) for x in self.asofs], "latest": _d(self.latest), "data_end": _d(self.data_end),
            "scenarios": self.manifest["scenarios"],
            "presets": [{"key": "7d", "label": "다음 7일"}, {"key": "14d", "label": "다음 14일"},
                        {"key": "month", "label": "다음 한 달"}, {"key": "quarter", "label": "다음 분기"}],
            "max_days": MAX_DAYS, "thresholds": {"x": X_TH, "y": Y_TH, "support_x": SUPPORT_X}, "per_person_default": PER_PERSON_DEFAULT,
            "built_at": self.manifest["built_at"], "data_note": DATA_NOTE,
        }

    # ------------------------------------------------------------------ 예상 건수
    def forecast(self, asof, start, end, agency) -> dict:
        a, s, e = self.period(asof, start, end)
        ad = self.asof_data(a)
        pf = period_forecast(ad, s, e).set_index("agency")
        st = ad.state.set_index("agency")
        days = (e - s).days + 1
        act = self.actual(s, e)
        rows = []
        for ag in AGENCIES:
            base = st.at[ag, "recent_day"] * days
            rows.append({"agency": ag, "pred": pf.at[ag, "pred"], "lo": pf.at[ag, "lo"], "hi": pf.at[ag, "hi"], "base": base,
                         "change": pf.at[ag, "pred"] / base - 1, "actual": _f(act[ag]) if act is not None else None,
                         "flag": pf.at[ag, "flag"], "flag_reason": pf.at[ag, "flag_reason"]})
        sel = [r for r in rows if agency is None or r["agency"] == agency]
        tot = {k: float(sum(r[k] for r in sel)) for k in ("pred", "lo", "hi", "base")}
        tot["change"] = tot["pred"] / tot["base"] - 1
        tot["actual"] = float(sum(r["actual"] for r in sel)) if act is not None else None
        src = pf.source.iloc[0]

        # 추이: 31일 이내면 일 단위(직전 28일 실적 + 기간 예측), 넘으면 주 단위(직전 8주 + 기간)
        cols = AGENCIES if agency is None else [agency]
        fd = ad.forecast_daily[(ad.forecast_daily.source == src) & ad.forecast_daily.agency.isin(cols)]
        daily_pred = fd.groupby("date").pred.sum()
        lo_r, hi_r = tot["lo"] / tot["pred"], tot["hi"] / tot["pred"]
        alerts = self._alerts_by_date(a, agency)
        series = []
        gran = "day" if days <= 31 else "week"
        step = 1 if gran == "day" else 7
        n_hist = 28 if gran == "day" else 8
        for k in range(n_hist, 0, -1):
            ws, we = a - D(days=k * step), a - D(days=(k - 1) * step + 1)
            series.append({"start": _d(ws), "end": _d(we), "label": self._label(ws, gran), "kind": "history",
                           "actual": float(self.cnt.loc[ws:we, cols].sum().sum())})
        t = s
        while t <= e:
            we = min(t + D(days=step - 1), e)
            p = float(daily_pred.loc[t:we].sum())
            act_v = float(self.cnt.loc[t:we, cols].sum().sum()) if we <= self.data_end else None
            al = [alerts[d] for d in pd.date_range(t, we) if d in alerts]
            series.append({"start": _d(t), "end": _d(we), "label": self._label(t, gran), "kind": "forecast", "pred": p,
                           "lo": p * lo_r, "hi": p * hi_r, "actual": act_v, "alert": al[0] if al else None})
            t = we + D(days=1)
        return {"period": self.period_out(a, s, e, src), "agency": agency, "granularity": gran, "total": tot,
                "by_agency": rows, "series": series,
                "range_note": "막대의 빗금은 80% 예측 범위 상한입니다."}

    @staticmethod
    def _label(t: pd.Timestamp, gran: str) -> str:
        return f"{t.month}/{t.day}({WEEKDAY[t.dayofweek]})" if gran == "day" else f"{t.month}/{t.day}~"

    def _alerts_by_date(self, a, agency) -> dict:
        al = self._al.get(a)
        out = {}
        if al is None or al.empty:
            return out
        for r in al[al.source == "예보"].sort_values("level", ascending=False).itertuples():
            if agency is not None and agency not in ALERT_AGENCY[r.type]:
                continue
            out.setdefault(r.date, ALERT_INFO[r.type]["levels"][r.level])
        return out

    # ------------------------------------------------------------------ 예상 이슈
    def issues(self, asof, start, end, agency) -> dict:
        a, s, e = self.period(asof, start, end)
        src = "short" if e <= a + D(days=13) else "long"
        al = self._al.get(a, pd.DataFrame(columns=["date", "offset", "type", "level", "source", "lead_days", "value"]))
        alerts = []
        for r in al.sort_values(["date", "type"]).itertuples():
            ags = ALERT_AGENCY[r.type]
            if agency is not None and agency not in ags:
                continue
            if r.date > e or r.date < s - D(days=2):
                continue
            info = ALERT_INFO[r.type]
            alerts.append({"date": _d(r.date), "offset": int(r.offset), "type": r.type, "type_label": info["label"],
                           "level": int(r.level), "level_label": info["levels"][int(r.level)], "source": r.source,
                           "lead_days": int(r.lead_days), "value": r.value, "issues": info["issues"], "agencies": ags,
                           "hit_rate": info["hit"][int(r.level)], "confidence": info["confidence"]})

        months = sorted({d.month for d in pd.date_range(s, e)})
        cal = self._cal[a]
        cal = cal[cal.cal_month.isin(months)]
        outlook = []
        for issue, g in cal.groupby("issue"):
            if agency is not None and ISSUE_INFO.get(issue) != agency:
                continue
            by_year = g.groupby("year").surged.max()
            if len(by_year) == 0:
                continue
            surged_months = sorted(g[g.surged == 1].cal_month.unique().tolist())
            outlook.append({"issue": issue, "agency": ISSUE_INFO.get(issue, ""), "prob": float(by_year.mean()),
                            "surged": int(by_year.sum()), "total": len(by_year), "months": surged_months or months})
        outlook.sort(key=lambda o: -o["prob"])

        pot = None
        pr = self._pot.get(a)
        mar1, apr30 = pd.Timestamp(a.year, 3, 1), pd.Timestamp(a.year, 4, 30)
        if pr is not None and s <= apr30 and e >= mar1 and (agency in (None, "DOT")):
            pot = {"snow_cm": float(pr.snow_cm), "mult": float(pr.mult), "n_winters": int(pr.n_winters), "flag": bool(pr.flag),
                   "actual_mult": self._pothole_actual(a.year)}

        cards = self._issue_cards(a, alerts, pot, outlook)
        headline = self._headline(a, alerts, pot, outlook)
        return {"period": self.period_out(a, s, e, src), "alerts": alerts, "outlook": outlook, "pothole": pot,
                "cards": cards, "headline": headline, "actual_surges": self._actual_surges(s, e, agency)}

    def _pothole_actual(self, year: int) -> float | None:
        if pd.Timestamp(year, 4, 30) > self.data_end:
            return None
        m = self.iss["도로 파손"].groupby(self.iss.index.to_period("M")).sum()
        base = m.rolling(12).mean().shift(1)
        return float(m.loc[[pd.Period(f"{year}-03", "M"), pd.Period(f"{year}-04", "M")]].mean() / base.loc[pd.Period(f"{year}-03", "M")])

    def _issue_cards(self, a, alerts, pot, outlook) -> list[dict]:
        cards = []
        by_type: dict[str, list] = {}
        for x in alerts:
            by_type.setdefault(x["type"], []).append(x)
        for kind, xs in sorted(by_type.items(), key=lambda kv: kv[1][0]["date"]):
            top = max(xs, key=lambda x: (x["level"], -x["offset"]))
            first, last = pd.Timestamp(xs[0]["date"]), pd.Timestamp(xs[-1]["date"])
            when = _md(first) if first == last else f"{_md(first)}~{_md(last)}"
            off = (first - a).days
            when += " (관측)" if top["source"] == "관측" else (" (오늘)" if off == 0 else f" ({off}일 후)")
            basis = ("관측 · " if top["source"] == "관측" else f"{top['lead_days']}일 전 발표 예보 · ") + top["value"]
            cards.append({"kind": "alert", "icon": ALERT_ICON[kind], "title": top["level_label"],
                          "agency": ALERT_AGENCY[kind][0], "tag": "기상 특보", "when": when, "basis": basis,
                          "metric_label": "과거 민원 급증", "metric": f"{top['hit_rate']:.0%}",
                          "tone": "danger" if top["level"] == 2 else "warning"})
        if pot is not None and pot["flag"]:
            cards.append({"kind": "pothole", "icon": "construction", "title": "도로 파손 급증", "agency": "DOT",
                          "tag": "겨울 적설 기반", "when": "3~4월",
                          "basis": f"지난겨울 적설 {pot['snow_cm']:.1f}cm · 과거 {pot['n_winters']}개 겨울로 추정",
                          "metric_label": "예상 배수", "metric": f"{pot['mult']:.1f}배", "tone": "warning"})
        strong = [o for o in outlook if o["prob"] >= 0.5] or [o for o in outlook if o["prob"] >= 0.3][:2]
        for o in strong[:4]:
            ms = o["months"]
            when = f"{ms[0]}월" if len(ms) == 1 else f"{ms[0]}~{ms[-1]}월"
            cards.append({"kind": "outlook", "icon": ISSUE_ICON.get(o["issue"], "sparkles"), "title": f"{o['issue']} 급증",
                          "agency": o["agency"], "tag": "과거 빈도", "when": when,
                          "basis": f"최근 {o['total']}년 중 {o['surged']}년 같은 시기 급증", "metric_label": "가능성",
                          "metric": f"{o['prob']:.0%}", "tone": "info"})
        return cards

    def _headline(self, a, alerts, pot, outlook) -> dict:
        fut = [x for x in alerts if x["source"] == "예보"]
        if fut:
            top = max(fut, key=lambda x: (x["level"], -x["offset"]))
            off = (pd.Timestamp(top["date"]) - a).days
            names = ", ".join(AGENCY_INFO[g]["name"] for g in top["agencies"])
            return {"title": f"향후 7일 기상 특보 예보 {len({(x['type'], x['date']) for x in fut})}건 — {top['level_label']} "
                             f"{_md(pd.Timestamp(top['date']))}" + ("" if off == 0 else f" ({off}일 후)"),
                    "detail": f"{names}: {', '.join(top['issues'])} 민원 급증 대비. 과거 같은 수준 날씨 뒤 민원 급증 {top['hit_rate']:.0%}.",
                    "tone": "danger" if top["level"] == 2 else "warning"}
        past = [x for x in alerts if x["source"] == "관측"]
        if past:
            top = max(past, key=lambda x: x["level"])
            names = ", ".join(AGENCY_INFO[g]["name"] for g in top["agencies"])
            return {"title": f"최근 이틀 {top['level_label']} 수준 날씨 관측",
                    "detail": f"{names}: {', '.join(top['issues'])} 민원이 기간 초반까지 이어질 수 있습니다.",
                    "tone": "warning"}
        if pot is not None and pot["flag"]:
            return {"title": f"봄철 도로 파손 급증 예상 — 평소의 {pot['mult']:.1f}배",
                    "detail": f"지난겨울 적설 {pot['snow_cm']:.1f}cm. 교통국 도로 파손 민원 대비 (10개 겨울 순위상관 0.94).",
                    "tone": "warning"}
        if outlook and outlook[0]["prob"] >= 0.5:
            o = outlook[0]
            return {"title": f"{o['issue']} 급증 가능성 {o['prob']:.0%}",
                    "detail": f"최근 {o['total']}년 중 {o['surged']}년 같은 시기에 급증했습니다 ({AGENCY_INFO[o['agency']]['name']}).",
                    "tone": "info"}
        return {"title": "특이 기상·이슈 없음", "detail": "향후 7일 기상 특보 예보가 없고, 같은 시기 급증 이력이 드뭅니다. 평상시 패턴으로 예측합니다.",
                "tone": "info"}

    def _actual_surges(self, s, e, agency) -> list[dict]:
        if s > self.data_end:
            return []
        e2 = min(e + D(days=2), self.data_end)
        iss = self.iss
        med = iss.rolling(28).median().shift(1)
        out = []
        for issue in iss.columns:
            if agency is not None and ISSUE_INFO.get(issue) != agency:
                continue
            seg, mseg = iss.loc[s:e2, issue], med.loc[s:e2, issue].clip(lower=1)
            hit = seg[(seg >= 2 * mseg) & (seg >= 20)]
            if len(hit):
                d = (hit / mseg[hit.index]).idxmax()
                out.append({"issue": issue, "date": _d(d), "count": float(seg[d]), "normal": float(med.loc[d, issue])})
        return sorted(out, key=lambda x: -x["count"] / max(x["normal"], 1))[:5]

    # ------------------------------------------------------------------ 매트릭스·인력·요약
    def matrix(self, asof, start, end) -> dict:
        a, s, e = self.period(asof, start, end)
        m = self._matrix(a, s, e)
        has_actual = "actual" in m.columns
        items = []
        for r in m.itertuples():
            items.append({"agency": r.agency, "name": AGENCY_INFO[r.agency]["name"], "short": AGENCY_INFO[r.agency]["short"],
                          "x": r.x, "x_lo": r.x_lo, "x_hi": r.x_hi, "y": r.y, "quadrant": r.quadrant, "flag": r.flag,
                          "flag_reason": r.flag_reason, "pred": r.pred, "lo": r.lo, "hi": r.hi, "base": r.base,
                          "backlog_open": r.backlog_open, "backlog_normal": r.backlog_normal,
                          "actual": _f(r.actual) if has_actual else None, "x_actual": _f(r.x_actual) if has_actual else None,
                          "quadrant_actual": r.quadrant_actual if has_actual else None,
                          "in_range": bool(r.in_range) if has_actual else None})
        counts = {q: int((m.quadrant == q).sum()) for q in QUADRANTS}
        return {"period": self.period_out(a, s, e, m.source.iloc[0]), "thresholds": {"x": X_TH, "y": Y_TH, "support_x": SUPPORT_X},
                "items": items, "counts": counts}

    def staffing(self, asof, start, end, per_person_day) -> dict:
        a, s, e = self.period(asof, start, end)
        if per_person_day <= 0:
            raise HTTPException(400, "1인당 하루 처리 건수는 0보다 커야 합니다.")
        m = self._matrix(a, s, e)
        r = staffing(m, s, e, per_person_day)
        return {"period": self.period_out(a, s, e, m.source.iloc[0]), "per_person_day": per_person_day,
                "workdays": r["workdays"], "needs": r["needs"], "supports": r["supports"],
                "pairs": [{"from_agency": p["from"], "to_agency": p["to"], "amount": p["amount"], "people": p["people"]}
                          for p in r["pairs"]],
                "total_need": r["total_need"], "total_people": r["total_people"], "covered": r["covered"],
                "coverage": _f(r["coverage"])}

    def summary(self, asof, start, end, agency, per_person_day) -> dict:
        a, s, e = self.period(asof, start, end)
        f = self.forecast(asof, start, end, agency)
        m = self._matrix(a, s, e).set_index("agency")
        st = staffing(m.reset_index(), s, e, per_person_day)
        fut = []
        al = self._al.get(a)
        if al is not None and not al.empty:
            for r in al[al.source == "예보"].itertuples():
                if agency is None or agency in ALERT_AGENCY[r.type]:
                    fut.append(r)
        if fut:
            top = min(fut, key=lambda r: (-r.level, r.offset))
            alert_top = f"{ALERT_INFO[top.type]['levels'][top.level]} {_md(top.date)}"
            alert_detail = f"{top.lead_days}일 전 발표 예보 기준"
        else:
            alert_top, alert_detail = None, "향후 7일 기상 특보 예보 없음"
        sel = AGENCIES if agency is None else [agency]
        open_, normal = float(m.loc[sel, "backlog_open"].sum()), float(m.loc[sel, "backlog_normal"].sum())
        needs = [n for n in st["needs"] if agency is None or n["agency"] == agency]
        return {"period": f["period"], "agency": agency, "kpis": {
            "forecast": f["total"], "alert_count": len({(r.type, r.date) for r in fut}), "alert_top": alert_top,
            "alert_detail": alert_detail,
            "focus_count": int((m.quadrant == "집중관리").sum()), "increase_count": int((m.quadrant == "접수증가 주의").sum()),
            "focus_names": [AGENCY_INFO[g]["name"] for g in m.index[m.quadrant == "집중관리"]],
            "agency_quadrant": m.at[agency, "quadrant"] if agency else None,
            "backlog_open": open_, "backlog_normal": normal, "backlog_multiple": open_ / normal if normal else 0.0,
            "need_people": float(sum(n["people"] for n in needs)), "need_count": float(sum(n["need"] for n in needs)),
            "support_count": len(st["supports"]), "coverage": _f(st["coverage"]),
        }}

    # ------------------------------------------------------------------ 지연 위험 민원
    def risk(self, asof, agency, limit) -> dict:
        a, _, _ = self.period(asof, None, None)
        rl, rc = self._rl[a], self._rc[a]
        if agency is not None:
            items = rl[rl.agency == agency].sort_values("rank").head(limit)
            note = ("이 부서는 지연 위험 모델의 구별력이 낮아(AUC 0.62) 위험 확률 대신 경과일 ÷ 기준처리기간으로 정렬합니다."
                    if agency == "DCWP" else "처리 중 민원(최근 6개월 접수분)을 지연 위험 확률이 높은 순서로 보여 줍니다.")
        else:
            # 한 부서가 목록을 독차지하지 않도록 부서마다 위험이 큰 민원을 골라(부서당 최대 per건) 위험 순으로
            per = max(1, -(-limit // len(AGENCIES)))
            # 확률 모델 부서를 위험 순으로 먼저, 경과일 기준 부서(소비자보호국)는 그 뒤에
            items = (rl[rl["rank"] <= per].assign(_m=lambda d: (d.method != "model").astype(int))
                     .sort_values(["_m", "score"], ascending=[True, False]).head(limit))
            note = (f"부서마다 지연 위험이 가장 큰 민원을 {per}건씩 골라 위험 확률 순으로 보여 줍니다. "
                    "소비자보호국은 위험 확률 대신 경과일 ÷ 기준처리기간으로 맨 뒤에 둡니다. 부서를 선택하면 그 부서 목록을 봅니다.")
        out = [{"unique_key": str(r.unique_key), "agency": r.agency, "complaint_type": r.complaint_type,
                "type_ko": COMPLAINT_KO.get(r.complaint_type, r.complaint_type), "descriptor": r.descriptor, "created": f"{r.created:%Y-%m-%d}", "elapsed_days": float(r.elapsed_days),
                "threshold_days": float(r.threshold_days), "ratio": float(r.ratio), "prob": _f(r.prob), "method": r.method,
                "factors": _ko_factors(r.factors)} for r in items.itertuples()]
        counts = [{"agency": r.agency, "open": int(r.open), "over_threshold": int(r.over_threshold), "high_risk": int(r.high_risk)}
                  for r in rc.itertuples()]
        return {"asof": _d(a), "agency": agency, "counts": counts, "items": out, "note": note}

    # ------------------------------------------------------------------ 7일 기상 예보 띠 · 과거 7년 모달
    def _strip_day(self, a: pd.Timestamp, k: int) -> dict:
        """기준일 + k일 칸. 오늘은 전날 발표, +k일은 기준일에 발표된 k일 전 예보. NWS 특보는 기준일까지 발표된 것만."""
        d = a + D(days=k)
        lead = max(k, 1)
        r = self._fdays.loc[(d, lead)] if len(self._fdays) and (d, lead) in self._fdays.index else None
        alerts = []
        if r is not None:
            for kind in ("heat", "snow", "wind"):              # 호우는 예보 판정 대신 실제 NWS 특보만 (검증 문서 2-3)
                lv = int(r[f"{kind}_level"]) if pd.notna(r[f"{kind}_level"]) else 0
                if lv >= 1:
                    alerts.append({"kind": kind, "kind_label": WEATHER_LABEL[kind], "level": lv, "source": "예보",
                                   "label": f"{WEATHER_LABEL[kind]}{'경보' if lv == 2 else '주의보'} 수준"})
        if len(self._nws):
            n = self._nws
            hit = n[(n.issued < a + D(days=1)) & (n.start < d + D(days=1)) & (n.end > d)]
            for x in hit.sort_values("level", ascending=False).drop_duplicates("name").itertuples():
                alerts.append({"kind": x.kind, "kind_label": WEATHER_LABEL[x.kind], "level": int(x.level), "label": x.name,
                               "source": "NWS", "issued": f"{x.issued.month}/{x.issued.day} {x.issued:%H:%M}"})
        icon = r["icon"] if r is not None and isinstance(r["icon"], str) else None
        return {"date": _d(d), "offset": k, "label": "오늘" if k == 0 else WEEKDAY[d.dayofweek], "lead": lead,
                "mode": "예보" if k < STRIP_FORECAST_DAYS else "참고", "icon": icon, "icon_label": ICON_LABEL.get(icon),
                **{c: (_f(r[c]) if r is not None else None) for c in ("tmax", "tmin", "prcp", "snow", "gust")},
                "alerts": alerts}

    def weather_strip(self, asof: str) -> dict:
        a, _, _ = self.period(asof, None, None)
        return {"asof": _d(a), "days": [self._strip_day(a, k) for k in range(STRIP_DAYS)],
                "note": (f"오늘 칸은 전날, +k일 칸은 기준일에 발표된 k일 전 예보입니다(Open-Meteo 예보 보관 기록). "
                         f"앞 {STRIP_FORECAST_DAYS}칸은 예보, 뒤 칸은 참고(가능성). 특보 수준은 예보 값에 미국 기상청(NWS 뉴욕 지청) "
                         "기준을 대입한 판정이고, 'NWS'는 기준일까지 실제 발표된 특보입니다.")}

    def _history(self, a: pd.Timestamp, d: pd.Timestamp, kind: str) -> dict:
        """같은 종류 과거 사건: 고른 날짜의 해 전 7년, 해마다 같은 날짜 앞뒤 120일 안에서 가장 가까운 사건. 기준일 전에 끝난 사건만."""
        ev = self._wev[(self._wev.kind == kind) & (self._wev.win_end < a)] if len(self._wev) else pd.DataFrame()
        main = WEATHER_ISSUES[kind][0]
        heads = ev[ev.issue == main] if len(ev) else ev
        nws_based = kind == "rain"
        years = []
        for y in range(d.year - 1, d.year - 1 - HISTORY_YEARS, -1):
            c = pd.Timestamp(y, d.month, 28 if (d.month, d.day) == (2, 29) else d.day)
            cand = heads[(heads.start - c).abs().dt.days <= HISTORY_SEASON_DAYS] if len(heads) else heads
            event = None
            if len(cand):
                best = cand.loc[(cand.start - c).abs().idxmin()]
                rows = ev[ev.event == best.event].set_index("issue").reindex(WEATHER_ISSUES[kind])
                event = {
                    "start": _d(best.start), "end": _d(best.end), "level": int(best.level),
                    "level_label": ("경보" if best.level == 2 else "주의보") + ("" if nws_based else " 수준"),
                    "win_start": _d(best.win_start), "win_end": _d(best.win_end), "days": int(best.days),
                    "nws": [x for x in str(best.nws).split(" · ") if x and x != "nan"], "surge": bool(best.surge),
                    "issues": [{"issue": iss, "base": float(r.base), "received": int(r.received), "excess": float(r.excess),
                                "processed": int(r.processed), "open_end": int(r.received - r.processed),
                                "open_7": int(r.received - r.processed_7) if best.win_end + D(days=7) < a else None,
                                "peak": int(r.peak), "surge": bool(r.surge)} for iss, r in rows.iterrows()],
                }
            years.append({"year": y, "compare_date": _d(c), "count": len(cand), "event": event})
        a_off, b_off = WEATHER_WINDOW[kind]
        word = "특보" if nws_based else "특보 수준"
        return {
            "kind": kind, "kind_label": WEATHER_LABEL[kind], "issues": WEATHER_ISSUES[kind],
            "window_rule": f"영향 기간 = {word} 첫날{' 하루 전' if a_off < 0 else ''} ~ 마지막 날 {b_off}일 뒤",
            "basis": ("실제 발표된 NWS 홍수 주의보·돌발 홍수 경보가 걸린 날" if nws_based
                      else f"관측 날씨가 미국 기상청(NWS 뉴욕 지청) {WEATHER_LABEL[kind]} 특보 기준에 든 날"),
            "total_events": len(heads), "surged_events": int(heads.surge.sum()) if len(heads) else 0,
            "years": years,
        }

    def weather_day(self, asof: str, date: str) -> dict:
        a, _, _ = self.period(asof, None, None)
        try:
            d = pd.Timestamp(date)
        except ValueError as err:
            raise HTTPException(400, f"날짜 형식이 올바르지 않습니다: {err}") from err
        k = (d - a).days
        if not 0 <= k < STRIP_DAYS:
            raise HTTPException(400, f"날짜는 기준일부터 {STRIP_DAYS}일 안에서 고르세요.")
        day = self._strip_day(a, k)
        # 그날 특보가 있는 종류만 과거 7년 표를 만듦 (특보 없는 날은 빈 목록 → 화면은 예보만)
        kinds = [x for x in WEATHER_LABEL if any(al["kind"] == x for al in day["alerts"])]
        tabs = [self._history(a, d, kind) for kind in kinds]
        return {"asof": _d(a), "day": day, "tabs": tabs,
                "note": ("과거 7년은 고른 날짜의 해 전 7년이며, 해마다 같은 날짜 앞뒤 120일 안에서 가장 가까운 사건을 보여 줍니다. "
                         "기준일 전에 끝난 사건만 씁니다. 평소 = 영향 기간 직전 28일 중 다른 영향 기간을 뺀 날의 하루 중앙값, "
                         "늘어난 건수 = 접수 − 평소 × 영향 일수.")}

    def evidence(self) -> dict:
        return {"sections": self.manifest["evidence"], "sources": [
            "docs/검증결과_10년.md — 10년치 데이터 검증 (예측 정확도, 기상 경보, 이슈, 지연 위험, 상보성)",
            "docs/리허설_검증.md — 시연 시나리오 재현과 화면 규칙",
            "docs/서비스기획_정리.md — 기획안",
            "NYC Open Data 311 Service Requests (erm2-nwe9, 76ig-c548)",
            "Open-Meteo Historical Weather / Previous Runs API",
            "NWS New York (OKX) 특보 기준 https://www.weather.gov/okx/wwa_definitions"]}


_STORE: Store | None = None


def get_store() -> Store:
    global _STORE
    if _STORE is None:
        if not (ARTIFACTS / "manifest.json").exists():
            raise HTTPException(503, "사전 계산 결과가 없습니다. `uv run python -m engine.build`를 먼저 실행하세요.")
        _STORE = Store()
    return _STORE
