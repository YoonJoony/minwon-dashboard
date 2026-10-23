"""사전 계산: 기준일마다 화면에 필요한 결과를 data/artifacts/에 저장하고, 리허설 수치와 대조합니다.

실행 (프로젝트 루트에서): uv run python -m engine.build
            빠른 확인용:  uv run python -m engine.build --only-scenarios
"""
import argparse
import json
import subprocess
import sys
import time
import warnings
from datetime import datetime

import numpy as np
import pandas as pd

from engine import alerts as al
from engine import backlog as bl
from engine import forecast_long as fl
from engine import forecast_short as fs
from engine import issues as isu
from engine import risk as rk
from engine import weather as wx
from engine.config import AGENCIES, ARTIFACTS, ASOF_START, LATEST, MAX_DAYS, ROOT, STRIP_DAYS, STRIP_PAST_DAYS
from engine.content import EVIDENCE, SCENARIOS
from engine.dashboard import AsofData, matrix
from engine.data import complaints, daily_counts, daily_issues, holidays, weather_daily

D = pd.Timedelta
# pandas 2.3 + NumPy 2.5 조합에서 pandas 내부가 내는 경고 (계산 결과와 무관)
warnings.filterwarnings("ignore", message="The 'generic' unit for NumPy timedelta", category=DeprecationWarning)


def asof_list(only_scenarios: bool) -> list[pd.Timestamp]:
    sc = [pd.Timestamp(s["asof"]) for s in SCENARIOS]
    if only_scenarios:
        return sorted(set(sc))
    return sorted(set(pd.date_range(ASOF_START, LATEST, freq="W-MON")) | set(sc))


def spread_daily(total: float, days: pd.DatetimeIndex, w: pd.Series) -> np.ndarray:
    """기간 합계를 요일 비율로 날짜에 나눔."""
    wt = w.reindex(days.dayofweek).to_numpy()
    return total * wt / wt.sum()


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="대시보드 사전 계산")
    p.add_argument("--only-scenarios", action="store_true", help="시나리오 날짜만 계산 (빠른 확인)")
    a = p.parse_args(argv)
    t0 = time.time()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)

    cnt, iss, w, hol = daily_counts(), daily_issues(), weather_daily(), holidays()
    data_end = cnt.index.max()
    asofs = asof_list(a.only_scenarios)
    log(f"기준일 {len(asofs)}개, 민원 데이터 끝 {data_end:%Y-%m-%d}")

    # ---------------- 단기 모델 입력·백테스트, 월별 방식 과거 오차
    origins = pd.date_range("2017-01-02", data_end, freq="W-MON")
    rows = fs.feature_rows(cnt, hol, origins)
    bt = fs.backtest(rows)
    mo = fl.monthly(cnt)
    wf = fl.walk_forward(mo)
    log(f"단기 입력 {len(rows):,}행, 백테스트 {len(bt):,}행, 월별 과거 예측 {len(wf):,}행")

    # ---------------- 특보, 이슈, 적체, 지연 위험 준비
    obs_lv, fc_lv = al.all_levels()
    mi = isu.monthly_issues(iss)
    df = complaints()
    weekly = bl.weekly_backlog(df, "2022-01-03", LATEST)
    mult, normal = bl.backlog_multiple(weekly)
    prep = rk.prepare(df)
    log("특보·적체 준비 완료")

    fd_rows, iv_rows, al_rows, af_rows, cal_rows, pot_rows, st_rows, rl_rows, rc_rows = ([] for _ in range(9))
    models: dict[pd.Timestamp, tuple] = {}
    for i, asof in enumerate(asofs):
        end_max = asof + D(days=MAX_DAYS - 1)
        dw = bl.dow_weights(cnt, asof)

        # 단기: 1~7일·8~14일 블록 → 요일 비율로 날짜에 나눔
        sp = fs.forecast(asof, rows, cnt, hol)
        for r in sp.itertuples():
            days = pd.date_range(r.start, r.end)
            for d, v in zip(days, spread_daily(r.pred, days, dw[r.agency])):
                fd_rows.append((asof, r.agency, d, "short", v))
        iv = fs.interval_ratios(bt, asof).assign(source="short")

        # 월별: 기준일이 속한 달부터 92일 끝이 속한 달까지 → 그 달 날짜에 요일 비율로 나눔
        months = list(pd.period_range(asof.to_period("M"), end_max.to_period("M"), freq="M"))
        lp = fl.seasonal_pred(mo, months, asof)
        for ag in AGENCIES:
            for per in months:
                days = pd.date_range(per.start_time, per.end_time.normalize())
                vals = spread_daily(lp.at[ag, per], days, dw[ag])
                for d, v in zip(days, vals):
                    if asof <= d <= end_max:
                        fd_rows.append((asof, ag, d, "long", v))
        iv = pd.concat([iv, fl.interval_ratios(wf, asof).assign(source="long")])
        iv_rows.append(iv.assign(asof=asof))

        # 특보와 특보 영향 부서
        alerts, affected = al.alerts_for(asof, obs_lv, fc_lv)
        al_rows.append(alerts.assign(asof=asof))
        pot = isu.pothole_outlook(w, mi, asof)
        if pot is not None:
            pot_rows.append({"asof": asof, **{k: v for k, v in pot.items() if k != "corr_note"}})
            if pot["flag"]:
                mar1 = pd.Timestamp(asof.year, 3, 1)
                extra = (pot["mult"] - 1) * pot["pot_base"] * 2 / 61
                affected = pd.concat([affected, pd.DataFrame([{
                    "agency": "DOT", "flag": "도로 파손 급증 예상", "level": 1,
                    "reason": f"지난겨울 적설 {pot['snow_cm']:.1f}cm → 3~4월 도로 파손 평소의 {pot['mult']:.1f}배 예상",
                    "factor": 1.0, "start": mar1, "end": pd.Timestamp(asof.year, 4, 30), "extra_per_day": extra}])])
        af_rows.append(affected.assign(asof=asof))

        # 이슈 달력 (기간에 걸릴 수 있는 달)
        cal_rows.append(isu.calendar(mi, asof, months).assign(asof=asof))

        # 부서 상태
        st = bl.dept_state(asof, cnt, weekly, mult, normal, df)
        st_rows.append(st.assign(asof=asof))

        # 지연 위험: 달마다 한 번 학습
        m0 = pd.Timestamp(asof.year, asof.month, 1)
        if m0 not in models:
            model, _ = rk.train(prep, m0)
            thr_disp = pd.concat([rk.thresholds(prep, m0 - pd.DateOffset(months=k)) for k in range(6)], axis=1).median(axis=1)
            models[m0] = (model, thr_disp)
        model, thr_disp = models[m0]
        top, counts = rk.score(prep, model, thr_disp, asof)
        rl_rows.append(top.assign(asof=asof))
        rc_rows.append(counts.assign(asof=asof))
        if (i + 1) % 10 == 0 or i == len(asofs) - 1:
            log(f"  {i + 1}/{len(asofs)} 기준일 완료 ({asof:%Y-%m-%d})")

    # ---------------- 7일 기상 예보 띠 · 과거 7년 모달 (기준일과 상관없이 한 번 계산, 기준일별 선택은 API)
    nws = wx.nws_alerts()
    weather = {
        "forecast_days": wx.forecast_days(asofs[0], asofs[-1] + D(days=STRIP_DAYS - 1)),
        "observed_days": wx.observed_days(obs_lv, asofs[0] - D(days=STRIP_PAST_DAYS), asofs[-1]),
        "nws_alerts": nws,
        "weather_events": wx.history_events(obs_lv, nws, df, data_end),
    }
    log(f"기상 예보 띠 {len(weather['forecast_days']):,}행, 지난 7일 관측 {len(weather['observed_days']):,}일, NWS 특보 {len(nws):,}건, "
        f"과거 사건 {weather['weather_events'].groupby('kind').event.nunique().to_dict()}")

    # ---------------- 저장
    out = {
        "forecast_daily": pd.DataFrame(fd_rows, columns=["asof", "agency", "date", "source", "pred"]),
        "intervals": pd.concat(iv_rows, ignore_index=True),
        "alerts": pd.concat([x for x in al_rows if len(x)], ignore_index=True),
        "affected": pd.concat(af_rows, ignore_index=True),
        "issue_calendar": pd.concat(cal_rows, ignore_index=True),
        "pothole": pd.DataFrame(pot_rows),
        "dept_state": pd.concat(st_rows, ignore_index=True),
        "risk_list": pd.concat(rl_rows, ignore_index=True),
        "risk_counts": pd.concat(rc_rows, ignore_index=True),
        "actual_daily": cnt.stack().rename("count").reset_index().rename(columns={"level_1": "agency"}),
        "issue_daily": iss.stack().rename("count").reset_index().rename(columns={"level_1": "issue"}),
        **weather,
    }
    for name, t in out.items():
        t.to_parquet(ARTIFACTS / f"{name}.parquet", index=False)
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], check=False, capture_output=True, text=True, cwd=ROOT).stdout.strip()
    except OSError:
        commit = ""
    manifest = {"built_at": datetime.now().isoformat(timespec="seconds"), "code_commit": commit,
                "data_end": f"{data_end:%Y-%m-%d}", "latest": LATEST, "asofs": [f"{x:%Y-%m-%d}" for x in asofs],
                "only_scenarios": a.only_scenarios, "scenarios": SCENARIOS, "evidence": EVIDENCE,
                "rows": {k: len(v) for k, v in out.items()}}
    (ARTIFACTS / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"저장 완료: {ARTIFACTS} ({time.time() - t0:.0f}초)")

    return 0 if check_rehearsal(out, data_end) else 1


def asof_data(out: dict, asof: pd.Timestamp) -> AsofData:
    sel = lambda t: t[t["asof"] == asof]
    return AsofData(asof, sel(out["forecast_daily"]), sel(out["intervals"]), sel(out["affected"]), sel(out["dept_state"]))


def check_rehearsal(out: dict, data_end: pd.Timestamp) -> bool:
    """빌드 게이트: 시나리오 4개의 예측·범위·적체 배수·사분면이 리허설 결과(analysis/results/rehearsal_matrix.csv)와 같은지."""
    ref_path = ROOT / "analysis/results/rehearsal_matrix.csv"
    if not ref_path.exists():
        log("리허설 결과 파일이 없어 대조를 건너뜀")
        return True
    ref = pd.read_csv(ref_path).rename(columns={"Unnamed: 0": "agency"})
    cnt = out["actual_daily"].pivot(index="date", columns="agency", values="count")
    ok = True
    for s in SCENARIOS:
        name = [n for n in ref.scenario.unique() if n.startswith(s["id"] + " ")]
        if not name:
            continue
        asof, start, end = pd.Timestamp(s["asof"]), pd.Timestamp(s["start"]), pd.Timestamp(s["end"])
        actual = cnt.loc[start:end].sum() if end <= data_end else None
        m = matrix(asof_data(out, asof), start, end, actual).set_index("agency")
        r = ref[ref.scenario == name[0]].set_index("agency").reindex(m.index)
        diffs = {
            "예측": float((m.pred / r.pred - 1).abs().max()),
            "범위 하한": float((m.lo / r.lo - 1).abs().max()),
            "범위 상한": float((m.hi / r.hi - 1).abs().max()),
            "적체 배수": float((m.y - r.y).abs().max()),
        }
        quad_same = int((m.quadrant == r.quad_pred).sum())
        in_range = int(m.in_range.sum()) if actual is not None else None
        good = diffs["예측"] < 0.01 and diffs["범위 하한"] < 0.02 and diffs["범위 상한"] < 0.02 and diffs["적체 배수"] < 0.02 \
            and quad_same == 8 and in_range == int(r.in_range.sum())
        ok &= good
        log(f"  대조 {s['id']}: {'일치' if good else '불일치'} | 최대 차이 " + ", ".join(f"{k} {v:.2%}" for k, v in diffs.items())
            + f" | 사분면 일치 {quad_same}/8 | 80% 범위 안 {in_range} (리허설 {int(r.in_range.sum())})")
    log("리허설 대조: " + ("통과" if ok else "실패 — 화면 계산이 검증한 계산과 다릅니다"))
    return ok


if __name__ == "__main__":
    sys.exit(main())
