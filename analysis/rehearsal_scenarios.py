"""시연 리허설: 과거 시점 재현 모드로 대시보드 값을 다시 계산하고 실제와 비교합니다.

각 시나리오의 기준일에 **그날까지 알려진 민원 데이터와 그날 실제로 발표된 예보만** 씁니다.
계산하는 값 (기획안 정의 그대로)
- 예상 건수: 7일은 단기 모델(기상 없음), 한 달·분기는 계절 지수 × 최근 수준, 80% 범위는 그 전까지의 과거 오차로
- 예상 이슈: 7일은 NWS 특보 기준 예보 경보, 한 달·분기는 이슈 달력 빈도 + 겨울 적설 → 봄 도로 파손
- 2×2 매트릭스: 가로 = 예상 일평균 ÷ 최근 4주 일평균 − 1, 세로 = 적체 배수(처리 중 민원 수 ÷ 직전 52주 중앙값), 기준 1.3배
  (리허설에서 '지연 중 비율' 정의가 일부 부서에서 크게 출렁여 바꿈: verify_matrix_y_stability.py)
- 기상 특보 영향 부서: 예보상 NWS 특보가 관련 이슈에 걸리면 범위 상한을 넓히고 '지원 가능'에서 제외 (verify_alert_uplift.py 3)
- 인력: 예상 적체 증가 = (예상 − 평소) × (1 − 즉시 종결 비율) × 적체 전환율, 지원 가능 = 접수 −10% 이하·지연 1.5배 미만

결과: analysis/results/rehearsal_*.csv, docs/rehearsal/*.png
실행: uv run python analysis/rehearsal_scenarios.py
"""
import sys
from pathlib import Path

import lightgbm as lgb
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
from verify_alert_uplift import alert_flags
from verify_alert_uplift import load as load_alerts
from verify_complementarity import CONV
from verify_matrix_y_stability import candidates
from verify_nws_alerts import daily_levels
from verify_short_term import BASE_F, build_rows

AG = ["DCWP", "DEP", "DHS", "DOB", "DOHMH", "DOT", "DPR", "DSNY"]
NAME = {"DCWP": "소비자보호", "DEP": "환경보호", "DHS": "노숙자", "DOB": "건축", "DOHMH": "보건",
        "DOT": "교통", "DPR": "공원", "DSNY": "위생"}
SCEN = [  # 이름, 기준일, 기간 시작, 기간 끝(포함), 종류
    ("S1 폭염", "2025-06-20", "2025-06-20", "2025-06-26", "7일"),
    ("S2 블리자드", "2026-02-20", "2026-02-20", "2026-02-26", "7일"),
    ("S3 봄철 도로 파손", "2026-03-01", "2026-03-01", "2026-05-31", "분기"),
    ("S4 평상시", "2025-10-01", "2025-10-01", "2025-10-31", "한 달"),
]
ALERT_ISSUE = {"heat": "폭염·소화전", "snow": "결빙·제설", "wind": "강풍·수목", "rain": "폭우·침수"}
ALERT_NAME = {"heat": "폭염", "snow": "대설", "wind": "강풍", "rain": "호우"}
PER_PERSON_DAY = 10  # 시연용 가정값: 1인당 하루 처리 건수
Y_TH = 1.3  # 세로축(적체 배수) 기준
WIDEN = {"DEP": 1.6, "DPR": 3.1, "DSNY": 3.1}  # 특보 주 실제÷예측 90% 지점 (verify_alert_uplift.py 3)
plt.rcParams["font.family"] = "AppleGothic"
plt.rcParams["axes.unicode_minus"] = False


def quadrant(x: float, y: float) -> str:
    if x <= -0.10 and y < Y_TH:
        return "지원 가능"
    if x >= 0.10:
        return "집중관리" if y >= Y_TH else "접수증가 주의"
    return "처리지연 주의" if y >= Y_TH else "안정"


# ------------------------------------------------------------------ 예상 건수
def short_term(cnt, w, rows, bt, asof):
    tr = rows[rows.origin + pd.Timedelta(days=13) < asof]
    m = lgb.LGBMRegressor(n_estimators=400, learning_rate=0.03, num_leaves=15, min_child_samples=30, subsample=0.8,
                          subsample_freq=1, colsample_bytree=0.8, verbose=-1, random_state=0)
    m.fit(tr[BASE_F], tr["target"])
    sc = build_rows(cnt, w, pd.DatetimeIndex([asof]))
    sc = sc[sc.block == 1].copy()
    sc["agency"] = pd.Categorical(sc["agency"].astype(str), categories=rows["agency"].cat.categories)
    sc["pred"] = np.exp(m.predict(sc[BASE_F])) * (sc["base"] + 1) - 1
    past = bt[(bt.block == 1) & (bt.origin + pd.Timedelta(days=6) < asof)]
    err = np.log((past.actual + 1) / (past.pred_model + 1)).groupby(past.agency.astype(str)).quantile([0.1, 0.9]).unstack()
    out = sc.set_index(sc.agency.astype(str))[["pred"]]
    out["lo"] = out.pred * np.exp(err[0.1])
    out["hi"] = out.pred * np.exp(err[0.9])
    return out


def seasonal_pred(mo: pd.DataFrame, target_months: list, asof: pd.Timestamp) -> pd.DataFrame:
    """계절 지수 × 최근 수준 (verify_long_term.py와 같은 방식). mo: 월별 건수 (PeriodIndex)."""
    known = mo[mo.index < asof.to_period("M")]

    def s_idx(y, per):
        r = []
        for k in range(1, 8):
            p = per - 12 * k
            win = y.loc[p - 6: p + 5] if p - 6 in y.index and p + 5 in y.index else None
            if win is not None and len(win) == 12 and p + 5 < asof.to_period("M"):
                r.append(y.loc[p] / win.mean())
        return np.median(r) if r else np.nan

    out = {}
    for ag in AG:
        y = known[ag]
        last = y.index[-1]
        level = np.mean([y.loc[last - r] / s_idx(y, last - r) for r in range(3)])
        out[ag] = {str(p): level * s_idx(y, p) for p in target_months}
    return pd.DataFrame(out).T


def long_term(cnt, asof, start, end):
    mo = cnt.groupby(cnt.index.to_period("M")).sum()
    months = list(pd.period_range(start, end, freq="M"))
    pred = seasonal_pred(mo, months, asof).sum(axis=1)
    errs = {ag: [] for ag in AG}           # 같은 방식의 과거 한 달 앞 오차로 80% 범위
    for t in pd.period_range("2019-01", (asof - pd.DateOffset(months=1)).strftime("%Y-%m"), freq="M"):
        p = seasonal_pred(mo, [t], t.to_timestamp())[str(t)]
        for ag in AG:
            errs[ag].append(np.log(mo.loc[t, ag] / p[ag]))
    q = pd.DataFrame({ag: np.quantile(v, [0.1, 0.9]) for ag, v in errs.items()}).T
    return pd.DataFrame({"pred": pred, "lo": pred * np.exp(q[0]), "hi": pred * np.exp(q[1])})


# ------------------------------------------------------------------ 예상 이슈
def forecast_alerts(fc: pd.DataFrame, asof: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """기준일에 발표돼 있던 예보로 기간 각 날짜의 NWS 특보 단계 계산."""
    rows = []
    for d in pd.date_range(asof, end):
        k = (d - asof).days
        lead = {0: 1, 1: 1, 2: 2, 3: 3, 4: 5, 5: 5, 6: 7}[min(k, 6)]
        h = fc[fc.time.dt.normalize() == d][["time"] + [c for c in fc.columns if c.endswith(f"_previous_day{lead}")]].copy()
        h.columns = ["time", "t", "rh", "prcp", "snow", "wind", "gust"]
        lv = daily_levels(h).iloc[0]
        rows.append({"date": d, "lead": lead, **{a: int(lv[a]) for a in ALERT_ISSUE}, "hi_max": lv.hi_max})
    return pd.DataFrame(rows).set_index("date")


def issue_calendar(iss: pd.DataFrame, asof: pd.Timestamp, months: list) -> pd.Series:
    m = iss.groupby(iss.index.to_period("M")).sum()
    m = m[m.index < asof.to_period("M")]
    surge = ((m / m.rolling(12).mean().shift(1) >= 1.5) & (m >= 30)).where(m.rolling(12).mean().shift(1).notna())
    out = {}
    for k in m.columns:
        yrs = surge[k][surge.index.month.isin([p.month for p in months])].dropna()
        by_year = yrs.groupby(yrs.index.year).max()
        out[k] = (int(by_year.sum()), len(by_year))
    return pd.Series(out)


def pothole_outlook(w: pd.DataFrame, iss: pd.DataFrame, asof: pd.Timestamp):
    """겨울(12~2월) 적설 → 3~4월 도로 파손 배수. 기준일 전 겨울들로 관계를 맞춘 뒤 이번 겨울에 적용."""
    m = iss["도로 파손"].groupby(iss.index.to_period("M")).sum()
    base = m.rolling(12).mean().shift(1)
    xs, ys = [], []
    for yr in range(2017, asof.year):
        xs.append(w.loc[f"{yr - 1}-12-01":f"{yr}-02-28", "snowfall_sum"].sum())
        ys.append(m.loc[[pd.Period(f"{yr}-03", "M"), pd.Period(f"{yr}-04", "M")]].mean() / base.loc[pd.Period(f"{yr}-03", "M")])
    b = np.polyfit(xs, np.log(ys), 1)
    snow = w.loc[f"{asof.year - 1}-12-01":f"{asof.year}-02-28", "snowfall_sum"].sum()
    return snow, float(np.exp(np.polyval(b, snow))), len(xs)


# ------------------------------------------------------------------ 시나리오
def main() -> None:
    out_dir = ROOT / "docs/rehearsal"
    out_dir.mkdir(parents=True, exist_ok=True)
    a = pd.read_csv(ROOT / "data/processed/daily_agency_weather.csv", parse_dates=["date"])
    cnt = a.pivot(index="date", columns="agency", values="count")[AG]
    w = pd.read_csv(ROOT / "data/processed/weather_features_daily.csv", parse_dates=["date"]).set_index("date")
    iss = pd.read_csv(ROOT / "data/processed/daily_issue_weather.csv", parse_dates=["date"]).pivot(
        index="date", columns="issue", values="count").drop(columns="기타")
    fc = pd.read_parquet(ROOT / "data/raw/weather/openmeteo_bronx_hourly_forecast.parquet")
    obs_h = pd.read_parquet(ROOT / "data/raw/weather/openmeteo_bronx_hourly_obs.parquet").rename(columns={
        "temperature_2m": "t", "relative_humidity_2m": "rh", "precipitation": "prcp", "snowfall": "snow",
        "wind_speed_10m": "wind", "wind_gusts_10m": "gust"})
    obs_lv = daily_levels(obs_h)
    feats = pd.read_parquet(ROOT / "data/processed/complaint_features.parquet",
                            columns=["created", "closed", "proc_days", "agency", "instant"])
    cands, _ = candidates(feats)
    dr = cands["C 적체 배수"]
    normal = dr.rolling(52, min_periods=40).median().shift(1).clip(lower=1)
    _, obs_lv2, F = load_alerts()
    rows = build_rows(cnt, w)
    bt = pd.read_csv(ROOT / "analysis/results/short_term_backtest.csv", parse_dates=["origin"])

    summary, matrix_rows = [], []
    for name, asof_s, start_s, end_s, kind in SCEN:
        asof, start, end = pd.Timestamp(asof_s), pd.Timestamp(start_s), pd.Timestamp(end_s)
        days = (end - start).days + 1
        print(f"\n{'=' * 90}\n{name}: 기준일 {asof:%Y-%m-%d}, 선택 기간 {start:%Y-%m-%d} ~ {end:%Y-%m-%d} ({kind}, {days}일)")

        P = short_term(cnt, w, rows, bt, asof) if kind == "7일" else long_term(cnt, asof, start, end)
        actual = cnt.loc[start:end].sum()
        recent = cnt.loc[asof - pd.Timedelta(days=28): asof - pd.Timedelta(days=1)].mean()
        monday = dr.index[dr.index <= asof][-1]
        y = dr.loc[monday] / normal.loc[monday]
        inst = feats[(feats.created >= asof - pd.DateOffset(months=12)) & (feats.created < asof)].groupby("agency").instant.mean()
        T = pd.DataFrame({"pred": P.pred, "lo": P.lo, "hi": P.hi, "actual": actual, "recent_day": recent, "y": y})
        T["x_pred"] = T.pred / days / T.recent_day - 1
        T["x_actual"] = T.actual / days / T.recent_day - 1
        flags = {}
        if kind == "7일":
            fl = alert_flags([asof], F, obs_lv2).iloc[0]
            flags = {a: "기상 특보" for a, v in fl.items() if v > 0}
            for a in flags:
                T.loc[a, "hi"] = max(T.loc[a, "hi"], T.loc[a, "pred"] * WIDEN.get(a, 2.6))
        elif asof.month in (3, 4):
            _, mult_w, _ = pothole_outlook(w, iss, asof)
            if mult_w >= 1.5:
                pm = iss["도로 파손"].groupby(iss.index.to_period("M")).sum()
                pot_base = pm[pm.index < asof.to_period("M")].iloc[-12:].mean()
                flags["DOT"] = "도로 파손 급증 예상"
                T.loc["DOT", "hi"] = T.loc["DOT", "hi"] + (mult_w - 1) * pot_base * 2
        T["flag"] = pd.Series(flags).reindex(T.index).fillna("")
        T["quad_pred"] = [quadrant(r.x_pred, r.y) for r in T.itertuples()]
        T.loc[(T.flag != "") & (T.quad_pred == "지원 가능"), "quad_pred"] = "안정"   # 특보 영향 부서는 지원 후보에서 제외
        T["in_range"] = (T.actual >= T.lo) & (T.actual <= T.hi)
        T["quad_actual"] = [quadrant(r.x_actual, r.y) for r in T.itertuples()]
        T["in_range"] = (T.actual >= T.lo) & (T.actual <= T.hi)
        T["err"] = (T.pred - T.actual).abs() / T.actual
        base = T.recent_day * days
        T["need"] = ((T.pred - base).clip(lower=0) * (1 - inst.reindex(T.index).fillna(0)) * pd.Series(CONV)).round()
        T["slack"] = (base - T.pred).clip(lower=0).where(T.quad_pred == "지원 가능", 0).round()
        workdays = len(pd.bdate_range(start, end))
        T["people"] = (T.need / (PER_PERSON_DAY * workdays)).round(1)

        print("\n[예상 건수와 매트릭스] (가로: 접수 증가율, 세로: 지연 배수)")
        for ag, r in T.iterrows():
            print(f"  {NAME[ag]:5s} 예상 {r.pred:7,.0f} (80% {r.lo:7,.0f}~{r.hi:7,.0f}) 실제 {r.actual:7,.0f} "
                  f"{'범위 안' if r.in_range else '범위 밖'} 오차 {r.err:4.0%} | 가로 예상 {r.x_pred:+5.0%} 실제 {r.x_actual:+5.0%} "
                  f"세로 {r.y:3.1f}배 | {r.quad_pred}{' [' + r.flag + ']' if r.flag else ''}{'' if r.quad_pred == r.quad_actual else ' → 실제 ' + r.quad_actual}")
        tot = T.pred.sum(), T.actual.sum()
        print(f"  전체 예상 {tot[0]:,.0f} / 실제 {tot[1]:,.0f} (오차 {abs(tot[0] - tot[1]) / tot[1]:.0%}), "
              f"80% 범위 안 {T.in_range.sum()}/8, 사분면 일치 {(T.quad_pred == T.quad_actual).sum()}/8")

        print("\n[인력] 예상 적체 증가(건)와 지원 필요 인원(가정: 1인당 하루 "
              f"{PER_PERSON_DAY}건, 근무일 {workdays}일)")
        for ag, r in T[T.need > 0].sort_values("need", ascending=False).iterrows():
            print(f"  {NAME[ag]:5s} {r.need:6,.0f}건 ≈ {r.people}명 ({r.quad_pred})")
        sup = T[T.quad_pred == "지원 가능"]
        print("  지원 가능 부서: " + (", ".join(f"{NAME[k]}(여유 {v:,.0f}건)" for k, v in sup.slack.items()) or "없음"))

        print("\n[예상 이슈]")
        issues_line = []
        if kind == "7일":
            A = forecast_alerts(fc, asof, end)
            for key, issue in ALERT_ISSUE.items():
                lv = A[key]
                if lv.max() > 0:
                    d = lv.idxmax()
                    txt = f"{ALERT_NAME[key]} {'경보' if lv.max() == 2 else '주의보'} 예보: {d:%m/%d} ({(d - asof).days}일 뒤, {A.loc[d, 'lead']}일 전 발표 예보)"
                    if key == "heat":
                        txt += f", 열지수 최고 {A.hi_max.max():.0f}°F"
                    print("  " + txt)
                    issues_line.append(txt)
            if not issues_line:
                print("  NWS 특보 수준 예보 없음")
            print("  실제 관측 특보 수준: " + (", ".join(
                f"{ALERT_NAME[k]} {d:%m/%d}" for k in ALERT_ISSUE for d in obs_lv.loc[start:end].index[obs_lv.loc[start:end, k] > 0]) or "없음"))
            peak = iss.loc[start:end + pd.Timedelta(days=2)]
            med = iss.rolling(28).median().shift(1).loc[start:end + pd.Timedelta(days=2)]
            surge = ((peak >= 2 * med.clip(lower=1)) & (peak >= 20))
            print("  실제 민원 급증: " + (", ".join(f"{k} 최대 {int(peak[k].max())}건({peak[k].idxmax():%m/%d}, 평소 {med[k].loc[peak[k].idxmax()]:.0f}건)"
                                               for k in surge.columns if surge[k].any()) or "없음"))
        months = list(pd.period_range(start, end, freq="M"))
        cal = issue_calendar(iss, asof, months)
        likely = cal[cal.apply(lambda v: v[1] > 0 and v[0] / v[1] >= 0.5)]
        print("  과거 빈도(같은 달 급증 해/전체 해): " + (", ".join(f"{k} {v[0]}/{v[1]}년" for k, v in likely.items()) or "50% 이상 이슈 없음"))
        if kind != "7일":
            if any(p.month in (3, 4) for p in months) and asof.month in (3, 4):
                snow, mult, n = pothole_outlook(w, iss, asof)
                m_act = iss["도로 파손"].groupby(iss.index.to_period("M")).sum()
                b_act = m_act.rolling(12).mean().shift(1)
                act_mult = m_act.loc[[pd.Period(f"{asof.year}-03", "M"), pd.Period(f"{asof.year}-04", "M")]].mean() / b_act.loc[pd.Period(f"{asof.year}-03", "M")]
                print(f"  겨울 적설 {snow:.1f}cm → 3~4월 도로 파손 예상 평소의 {mult:.1f}배 (과거 {n}개 겨울로 추정) | 실제 {act_mult:.1f}배")
            m = iss.groupby(iss.index.to_period("M")).sum()
            ratio = m / m.rolling(12).mean().shift(1)
            act = [(k, p) for p in months for k in m.columns if ratio.loc[p, k] >= 1.5 and m.loc[p, k] >= 30]
            print("  실제 월별 급증: " + (", ".join(f"{k} {p.month}월({ratio.loc[p, k]:.1f}배)" for k, p in act) or "없음"))

        summary.append({"시나리오": name, "기준일": asof_s, "기간": f"{start_s}~{end_s}", "전체 오차": abs(tot[0] - tot[1]) / tot[1],
                        "80% 범위 안": int(T.in_range.sum()), "사분면 일치": int((T.quad_pred == T.quad_actual).sum())})
        matrix_rows.append(T.assign(scenario=name))

        # 매트릭스 그림
        fig, ax = plt.subplots(figsize=(9, 5.4), dpi=130)
        xs, ys = (T.x_pred * 100).clip(-60, 300), T.y.clip(0, 2)
        ax.axvspan(10, 300, ymin=Y_TH / 2, ymax=1, color="#fde8e6", zorder=0)
        ax.axvline(10, color="#888", ls="--", lw=1)
        ax.axhline(Y_TH, color="#888", ls="--", lw=1)
        col = {"집중관리": "#c0392b", "처리지연 주의": "#c98a12", "접수증가 주의": "#e67e22", "안정": "#7f8c8d", "지원 가능": "#1e7d45"}
        size = np.sqrt(T.pred / T.pred.max()) * 500 + 60          # 큰 부서가 작은 부서를 가리지 않게 제곱근 크기
        lo_x = (T.lo / days / T.recent_day - 1) * 100
        hi_x = (T.hi / days / T.recent_day - 1) * 100
        for ag in T.index:                                           # 80% 예측 범위(특보 영향이면 넓어짐)
            ax.hlines(ys[ag], max(lo_x[ag], -60), min(hi_x[ag], 300), color="#c0392b" if T.loc[ag, "flag"] else "#999",
                      lw=2.5 if T.loc[ag, "flag"] else 1.2, alpha=0.7, zorder=2)
        ax.scatter(xs, ys, s=size, c=[col[q] for q in T.quad_pred], alpha=0.85,
                   edgecolors=["#c0392b" if f else "white" for f in T.flag], linewidths=[2.5 if f else 1.2 for f in T.flag], zorder=3)
        ax.scatter((T.x_actual * 100).clip(-60, 300), ys, s=46, marker="x", c="black", linewidths=1.6, zorder=4)
        order = ys.sort_values().index
        for i, ag in enumerate(order):
            lab = NAME[ag] + (" [" + T.loc[ag, "flag"] + "]" if T.loc[ag, "flag"] else "")
            ax.annotate(lab, (xs[ag], ys[ag]), xytext=(-8, 9 + (i % 2) * 11), textcoords="offset points", ha="right",
                        fontsize=9, color="#c0392b" if T.loc[ag, "flag"] else "#222", zorder=5)
        ax.set_xlim(-60, 300)
        ax.set_ylim(0, 2)
        ax.set_xlabel("접수 증가율 (선택 기간 예상 ÷ 최근 4주, %)   가로줄 = 80% 예측 범위,  × = 실제")
        ax.set_ylabel("적체 배수 (처리 중 민원 수 ÷ 부서 평소)")
        ax.set_title(f"{name} — 기준일 {asof:%Y-%m-%d}, {start:%m/%d}~{end:%m/%d} ({kind})", fontsize=12, pad=12)
        for (tx, ty, lab) in ((295, 1.95, "집중관리"), (-57, 1.95, "처리지연 주의"), (295, 0.03, "접수증가 주의"), (-57, 0.03, "지원 가능·안정")):
            ax.text(tx, ty, lab, ha="right" if tx > 0 else "left", va="top" if ty > 1 else "bottom", fontsize=9, color="#555")
        fig.tight_layout()
        fig.savefig(out_dir / f"{name.split()[0]}_matrix.png")
        plt.close(fig)

    pd.DataFrame(summary).to_csv(ROOT / "analysis/results/rehearsal_summary.csv", index=False)
    pd.concat(matrix_rows).to_csv(ROOT / "analysis/results/rehearsal_matrix.csv")
    print("\n" + pd.DataFrame(summary).to_string(index=False, formatters={"전체 오차": "{:.0%}".format}))


if __name__ == "__main__":
    main()
