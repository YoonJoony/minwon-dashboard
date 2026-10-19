"""10년치 검증 ③: 실제 예보(1~7일 전 발표분)만 보고 경보를 냈다면?

관측 기상으로 본 경보 적중률은 '날씨를 정확히 알았을 때'의 상한입니다. 여기서는 Open-Meteo 과거 예보 기록으로
(1) 예보가 실제 기상 이벤트를 얼마나 미리 잡았는지, (2) 예보 기반 경보 뒤 관련 민원이 실제로 급증했는지를 봅니다.
기간: 2022-01 ~ 2026-10 (예보 기록이 있는 기간).

실행: uv run python analysis/verify_forecast_alerts.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RULES = [  # 이름, 예보 열, 관측 열, 기준, 이슈, 급증을 볼 기간(기상일 기준)
    ("폭염 최고 ≥ 32°C", "tmax", "temperature_2m_max", 32, "폭염·소화전", (0, 1)),
    ("폭염 최고 ≥ 34°C", "tmax", "temperature_2m_max", 34, "폭염·소화전", (0, 1)),
    ("적설 ≥ 2cm", "snow", "snowfall_sum", 2, "결빙·제설", (1, 2)),
    ("적설 ≥ 5cm", "snow", "snowfall_sum", 5, "결빙·제설", (1, 2)),
    ("강수 ≥ 25mm", "precip", "precipitation_sum", 25, "폭우·침수", (0, 1)),
    ("강수 ≥ 40mm", "precip", "precipitation_sum", 40, "폭우·침수", (0, 1)),
    ("돌풍 ≥ 70km/h", "gust", "wind_gusts_10m_max", 70, "강풍·수목", (0, 1)),
]


def main() -> None:
    f = pd.read_csv(ROOT / "data/raw/weather/openmeteo_bronx_forecasts_daily.csv", parse_dates=["date"])
    w = pd.read_csv(ROOT / "data/processed/weather_features_daily.csv", parse_dates=["date"]).set_index("date")
    iss = pd.read_csv(ROOT / "data/processed/daily_issue_weather.csv", parse_dates=["date"]).pivot(
        index="date", columns="issue", values="count")
    days = pd.date_range("2022-01-01", "2026-10-09")
    rows = []
    for name, fc, oc, thr, issue, (lo, hi) in RULES:
        s = iss[issue].reindex(days)
        surge = (s >= 2 * iss[issue].rolling(28).median().shift(1).reindex(days).clip(lower=1)) & (s >= 20)
        hit_after = pd.concat([surge.shift(-k) for k in range(lo, hi + 1)], axis=1).any(axis=1)
        # 예보 기록이 빈 날은 '예보 없음'이지 '이벤트 없음'이 아니므로, 모든 예보 시점에 값이 있는 날만 평가합니다.
        # (기온 예보는 2022년부터, 강수·적설·돌풍 예보는 2024년부터 기록이 있음)
        fcs = {lead: f[f.lead_days == lead].set_index("date")[fc].reindex(days) for lead in (1, 3, 5, 7)}
        valid = pd.concat(fcs.values(), axis=1).notna().all(axis=1)
        obs = (w[oc].reindex(days) >= thr) & valid
        r = {"규칙": name, "평가 기간": f"{valid[valid].index.min():%Y-%m} ~ {valid[valid].index.max():%Y-%m}",
             "실제 발생일": int(obs.sum()), "관측 기준 민원 적중률": hit_after[obs].mean()}
        for lead in (1, 3, 5, 7):
            fl = (fcs[lead] >= thr) & valid
            r[f"{lead}일 전 예보: 실제 발생 포착"] = (fl & obs).sum() / max(obs.sum(), 1)
            r[f"{lead}일 전 예보: 헛경보"] = (fl & ~obs).sum() / max(fl.sum(), 1)
            r[f"{lead}일 전 예보: 민원 적중률"] = hit_after[fl].mean()
        rows.append(r)
    R = pd.DataFrame(rows)
    R.to_csv(ROOT / "analysis/results/forecast_alerts.csv", index=False)
    pd.set_option("display.width", 250)
    show = ["규칙", "평가 기간", "실제 발생일", "관측 기준 민원 적중률"] + [c for c in R.columns if c.startswith(("1일", "3일", "7일"))]
    print(R[show].to_string(index=False, float_format=lambda x: f"{x:.0%}"))


if __name__ == "__main__":
    main()
