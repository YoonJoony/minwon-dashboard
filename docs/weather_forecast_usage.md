# How weather forecast data is used

## Short answer

**The complaint-count models don't use weather at all.** Neither the LightGBM weekly model (`engine/forecast_short.py`) nor the monthly seasonal model (`engine/forecast_long.py`) takes any weather input.

Weather forecasts are used **around** the count forecast instead. They turn forecast weather into NWS-style alerts, and those alerts then:

1. widen the **upper end of the 80% range** for affected agencies,
2. raise **issue warnings** (e.g. heat → hydrant complaints),
3. remove affected agencies from the **"can lend staff"** list, and
4. drive the **7-day weather strip** on screen.

The point forecast (the number shown) never changes because of weather.

## Why weather isn't in the count model

This was tested in the backtest (`analysis/verify_short_term.py`, see [forecast_error_verification.md](forecast_error_verification.md)). The weather given to the model was the **actual observed** weather, which is better than any real forecast could be:

| | Days 1–7 error | Days 8–14 error |
|---|---:|---:|
| Model without weather | **16.6%** | **18.1%** |
| Model + observed weather (best case) | 16.8% | 18.4% |

Even perfect weather knowledge didn't improve agency totals. Weather-related complaints are only a small share of each agency's total, so their effect gets lost.
At the **issue** level, weather did help (heat → hydrant complaints error −31%). That's why weather is used for issue alerts instead (`docs/검증결과_10년.md`, ③).

## The forecast data

| Item | Content |
|---|---|
| Source | Open-Meteo **Previous Runs API** (`pipelines/fetch_openmeteo_forecasts.py`) |
| What it holds | For each hour, what the forecast issued **1–7 days earlier** said. So on a past reference date, the dashboard sees only the forecast that was actually available then. |
| Variables | Temperature, humidity, precipitation, snowfall, wind speed, wind gusts (plus weather code and cloud cover, for icons) |
| Location | Bronx grid point (40.808, −73.892) |
| File | `data/raw/weather/openmeteo_bronx_hourly_forecast.parquet`, read by `engine/data.py:45-65` |

Which forecast is used for which day (`engine/config.py:44`, `LEAD`):

| Day | Weather used |
|---|---|
| 2 days and 1 day before the reference date | Observed weather |
| Reference date (day 0) | Forecast issued the day before |
| Day +k (k = 1–6) | Forecast issued k days earlier, i.e. on the reference date |

## Step 1: forecast weather → alert level

`engine/alerts.py:30` (`daily_levels`) applies **NWS New York office criteria** to the hourly forecast values, giving each day a level of 0 (none), 1 (advisory) or 2 (warning):

| Type | Advisory (1) | Warning (2) |
|---|---|---|
| Heat | Heat index ≥ 95°F on 2 days in a row, or ≥ 100°F | Heat index ≥ 105°F for 2 hours in a row |
| Wind | Sustained ≥ 30 mph or gust ≥ 46 mph | Sustained ≥ 40 mph or gust ≥ 58 mph |
| Snow | ≥ 3 in within 12 hours | ≥ 6 in within 12 hours or ≥ 8 in within 24 hours |
| Heavy rain | ≥ 0.5 in in 1 hour | ≥ 1 in in 1 hour |

- The heat index is computed from temperature and humidity using the NWS formula (`heat_index`, `engine/alerts.py:18`).
- NWS has no fixed heavy-rain criterion, so the 1-hour rain thresholds are a stand-in, treated as reference only.
- If more than 10% of a day's forecast hours are missing, no alert is issued for that day.

## Step 2: alert → affected agency

`alerts_for` (`engine/alerts.py:85`) links each alert type to an issue and an agency (`engine/config.py:47`, `LINKS`):

| Alert | Issue | Agency | Days affected after the alert day |
|---|---|---|---|
| Heat | Hydrants, tap water | DEP | same day – 1 day |
| Snow | Ice / snow removal | DSNY | 1 – 2 days |
| Wind | Fallen trees | DPR | same day – 1 day |
| Heavy rain | Flooding | DEP | same day – 1 day |

An agency is flagged if any affected day falls within the **first 7 days** after the reference date.

## Step 3: what the flag changes

**a) Upper end of the 80% range** (`engine/dashboard.py:45-52`)

```
widened upper = forecast + (factor − 1) × (forecast for the flagged days in the period)
shown upper   = max(normal upper, widened upper)
```

| Agency | factor |
|---|---:|
| DEP | 1.6 |
| DPR | 3.1 |
| DSNY | 3.1 |
| Others | 2.6 |

The factors are the 90th percentile of "actual ÷ forecast" in past alert weeks (`engine/config.py:36-39`, from `docs/리허설_검증.md`). Only the upper bound moves. The forecast itself and the lower bound stay the same.

**b) Issue warnings** (`backend/app/store.py:208`)
The issue panel lists each alert with its date, how many days ahead it was forecast, the forecast value, the related issues and agency, and the past hit rate (e.g. heat advisory → complaint surge 78% of the time; `engine/config.py:51`, `ALERT_INFO`).

**c) Staffing suggestions** (`engine/dashboard.py:74`)
A flagged agency is never marked "can lend staff", even if its forecast is low, because a weather-driven surge may be coming.

**d) 7-day weather strip** (`engine/weather.py:51`)
Shows icons and alert levels for the reference date + 7 days from the same forecasts. Actually issued NWS alerts (from the IEM archive, `data/raw/nws`) are shown alongside them.

## Weather data that is *observed*, not forecast

These parts use past observed weather, not forecasts:

- **Last 2 days' alerts** before the reference date (Step 1, "observed").
- **Spring pothole outlook** (`engine/issues.py:27`): last winter's total snowfall → expected March–April pothole increase for DOT. This also adds to DOT's upper range bound.
- **Past 7-year event history** in the weather strip's pop-up (`engine/weather.py:107`).

## Summary

| Used for | Weather forecast? |
|---|---|
| Forecast complaint count (the number) | **No** |
| 80% range upper bound | **Yes**, widened for agencies with a forecast alert |
| Issue warnings | **Yes** |
| Matrix / staffing: "can lend staff" | **Yes**, flagged agencies excluded |
| 7-day weather strip | **Yes** |

This description is based on reading the code. I didn't run this part, because the hourly forecast files (`data/raw/weather/openmeteo_bronx_hourly_forecast.parquet`, NWS archive) haven't been downloaded in this session.

---

## Follow-up: what is the "80% upper bound", and how is it used?

### What it means

Each forecast is shown with an **80% range**: a lower and an upper bound. Historically, the actual count fell inside it about 80% of the time, **below the upper bound about 90% of the time**, and above it about 10%.

It comes from the model's own past errors, not from a formula:

1. Take all past backtest forecasts for that agency that were already settled before the reference date (the backtest forecasts from the yearly-retrained model for weekly periods, and one-month-ahead forecasts for the monthly method).
2. For each one, compute actual ÷ forecast (on a log scale).
3. The **10th percentile** of those ratios gives `lo_ratio` and the **90th percentile** gives `hi_ratio`.
4. Bounds = forecast × `lo_ratio` and forecast × `hi_ratio`.

Code: `interval_ratios` in `engine/forecast_short.py:87` (separately for days 1–7 and 8–14) and `engine/forecast_long.py:52`.

Example: if DEP's `hi_ratio` is 1.25 and the forecast is 1,000, the upper bound is 1,250. In 9 out of 10 past weeks, DEP's actual stayed below 1.25 × the forecast.

On top of that, the upper bound is raised further for:
- weather alerts (the factors above), and
- the spring pothole outlook for DOT.

### How it's used

**Display only.** It doesn't feed any decision rule.

| Place | Use |
|---|---|
| Forecast chart | Hatched part of the bar above the forecast; the tooltip shows "80% range lo ~ hi" (`frontend/src/charts/forecastOption.ts`) |
| Agency panel | "lo ~ hi" next to each agency's forecast (`frontend/src/components/DeptPanel.tsx`) |
| Risk matrix | Horizontal bar around each agency's dot, from `x_lo` to `x_hi` (the range as % change vs normal) (`frontend/src/charts/matrixOption.ts`) |
| Past reference dates | When the actual is known, each agency is marked "within range" or "outside range" (`engine/dashboard.py:79`) |

What it does **not** change:
- **The forecast number.**
- **The matrix quadrant:** it uses the forecast change `x`, not `x_hi`.
- **The staffing amounts:** they use the forecast and the baseline (`engine/dashboard.py:83-94`).

A weather alert therefore makes the dashboard show "it could be much higher than forecast" without changing the forecast or the staffing numbers. The only alert effect on decisions is removing the agency from the "can lend staff" list.

---

## Follow-up: is "widening the upper end" the right end of the line in the risk matrix?

> Screenshot: DHS (노숙자) in the risk matrix: a horizontal line, a circle on it, and an ×.

**Yes.** In the risk matrix (`frontend/src/charts/matrixOption.ts`), the three marks for each agency are:

| Mark | Meaning | Value |
|---|---|---|
| **Circle** | Forecast change vs normal | `x` = forecast ÷ baseline − 1 |
| **Horizontal line** | 80% range of that change | from `x_lo` = lower bound ÷ baseline − 1 to `x_hi` = **upper bound** ÷ baseline − 1 |
| **×** | Actual change (past reference dates only) | `x_actual` = actual ÷ baseline − 1 |

Because `x_hi` is the upper bound divided by the baseline, widening the upper bound for a weather alert moves **only the right end of the line further right**. The circle and the left end stay put.

The vertical position is the backlog multiple (y-axis) and isn't affected.

Details:
- If the right end goes past the chart's maximum (+100%), the line is cut at the edge and ends in an **arrowhead** instead of a small vertical tick. Alert agencies often look like this, since DPR and DSNY have a ×3.1 factor (`matrixOption.ts:185-200`).
- An agency with a weather flag also gets a **dashed dark border** on its circle and a badge next to its name.

### About the DHS line in the screenshot

**DHS is never widened for weather.** No alert type is linked to DHS (`LINKS` covers only DEP, DSNY and DPR). Its long line comes only from its own past errors: DHS is the hardest agency to forecast (36% weekly error, see [forecast_error_verification.md](forecast_error_verification.md)), so its normal 10th–90th percentile range is already wide.

To see a weather-widened line, look at DEP, DSNY or DPR on a reference date with a forecast alert: those circles have the dashed border and badge.

---

## The 80% range, explained more simply

### The idea in one sentence

The range answers: **"Judging by how far off this forecast has been in the past, where will the real number most likely land?"**

### An everyday comparison

Say your commute is "usually 30 minutes". Over the last 100 trips:
- 10 trips were faster than 27 minutes,
- 10 trips were slower than 40 minutes,
- the other 80 were between 27 and 40.

So next time you'd say: "30 minutes, most likely between 27 and 40." That's an 80% range. 40 minutes is the **upper bound**: only 1 trip in 10 took longer.

The dashboard does the same thing with complaint forecasts.

### Real example: DSNY, reference date 2026-10-12, days 1–7

**Step 1. Look at past forecasts and how far off they were.**
The model has 249 past weekly DSNY forecasts with known results. For each, compute **actual ÷ forecast**:

| Week | Forecast | Actual | Actual ÷ forecast | |
|---|---:|---:|---:|---|
| 2026-03-02 | 1,770 | 885 | 0.50 | lowest |
| 2025-01-27 | 832 | 697 | 0.84 | about 10% of weeks were lower |
| 2022-09-19 | 756 | 750 | 0.99 | middle week: almost exact |
| 2026-09-28 | 828 | 952 | 1.15 | about 10% of weeks were higher |
| 2026-01-26 | 779 | 2,575 | 3.30 | highest (snowstorm, see below) |

**Step 2. Drop the most extreme 10% on each side.**
Sort the 249 ratios and cut off the lowest 10% and the highest 10%. What's left runs from **0.85 to 1.14**. In the past, DSNY's actual count landed between 85% and 114% of the forecast 8 weeks out of 10.

**Step 3. Apply that to the new forecast.**

| | Calculation | Result |
|---|---|---:|
| Forecast | LightGBM | **741** |
| Lower bound | 741 × 0.85 | **627** |
| Upper bound | 741 × 1.14 | **848** |

The dashboard shows: "DSNY next 7 days: **741** (80% range 627 ~ 848)."

### Easy agencies get a narrow range, hard ones a wide one

The range isn't a fixed ±10%. It reflects each agency's own track record. Same reference date, days 1–7:

| Agency | Forecast | 80% range | Range as % of forecast | Why |
|---|---:|---|---|---|
| DOHMH | 249 | 218 ~ 283 | −12% ~ +14% | Very steady; the forecast is usually close |
| DSNY | 741 | 627 ~ 848 | −15% ~ +14% | Steady, apart from snowstorms |
| DPR | 230 | 169 ~ 316 | −26% ~ +38% | Swings with weather (storms, fallen trees) |
| DHS | 87 | 63 ~ 120 | −27% ~ +39% | Small numbers that jump around a lot |

### How to read it, and how not to

- ✅ "The real number will **most likely** be between 627 and 848."
- ✅ "There's roughly a **1 in 10 chance it's above 848**." (25 of DSNY's 249 past weeks were above their upper bound.)
- ❌ "It **can't** go above 848." It can, and about 1 week in 10 it does.
- ❌ "848 is the worst case." The worst past DSNY week was 3.3 × the forecast.

### Why weather alerts widen the upper bound

Look again at the worst DSNY week: **2026-01-26**. On 2026-01-25, 20 cm of snow fell. DSNY got **2,575** complaints against a forecast of **779**, 3.3 times more.

The normal range for that week would have topped out around 779 × 1.14 ≈ **890**, nowhere near 2,575. The usual range comes mostly from ordinary weeks, so it badly understates storm weeks.

That's why, when the forecast weather reaches snow-alert level, the dashboard raises DSNY's upper bound with factor 3.1:

| | Calculation | Upper bound |
|---|---|---:|
| Normal | 779 × 1.14 | about 890 |
| With snow alert (all 7 days flagged) | 779 + (3.1 − 1) × 779 | about **2,415** |

The forecast itself stays at 779, and only the upper end moves. The dashboard is saying: "We still expect about 779, but with this snow it could go as high as about 2,400. Be prepared."

(I didn't check whether the forecast issued at the time actually reached alert level for that week, because the forecast archive isn't downloaded in this session. The numbers show what the widening does *if* it triggers.)

### In the risk matrix

The same range is drawn as the horizontal line, converted to "% change vs the last 4 weeks' daily average". The right end of the line = upper bound ÷ baseline − 1. A snow alert pushes DSNY's right end far to the right, often past the edge, where it is drawn as an arrowhead. The circle (the forecast) stays where it is.

---

## Follow-up: why does the matrix line move so much when I change the period?

> The 80% range shouldn't change much when I change the target dates. But in the risk matrix, the horizontal line shifts a lot. Why?

**Your understanding is right about the range itself.** The range *ratios* (e.g. DSNY 0.85 ~ 1.14) barely change with the period. But the matrix doesn't draw the range in complaints. It draws it as **"% change vs normal"**, and both the forecast and "normal" change with the period. On top of that, the method can switch mid-way.

Measured on reference date 2026-10-12 (no weather alerts applied):

| Period | Method used | Range ratios | DSNY line (circle) | DHS line (circle) |
|---|---|---|---|---|
| Mon–Sun, 7 days | weekly, days 1–7 | DSNY 0.85~1.14 | −30% ~ −5% (−17%) | −29% ~ +34% (−3%) |
| Mon–Wed, 3 days | weekly, days 1–7 | same | −21% ~ +7% (−7%) | −21% ~ +49% (+8%) |
| Sat–Mon, 3 days | weekly, days 8–14 | DSNY 0.84~1.15 | **−44% ~ −24%** (−34%) | −45% ~ +16% (−21%) |
| Days 1–14 | weekly, days 8–14 | same | −25% ~ +2% (−11%) | −29% ~ +49% (+1%) |
| Days 1–15 | **monthly** | DSNY 0.82~1.18 | −18% ~ +17% (0%) | **−62% ~ −26%** (−46%) |
| Days 1–30 | monthly | same | −22% ~ +12% (−5%) | −66% ~ −33% (−51%) |

The ratios move by only a few points, yet the lines jump by 20–50 points. Five things cause this.

### 1. The line is drawn relative to "normal", and "normal" ignores day of week

Each end of the line = bound ÷ baseline − 1, where baseline = **last 28 days' daily average × number of days**. The forecast includes the weekday pattern, but the baseline doesn't (see [sub_week_forecast_accuracy.md](sub_week_forecast_accuracy.md)).
So for the same agency and the same week:
- Mon–Wed (busy weekdays) puts DSNY's circle at −7%.
- Sat–Mon (weekend) puts it at −34%.

The whole line slides left or right with the circle. That's not a change in uncertainty; it's the weekday mix.

### 2. The line's length scales with forecast ÷ baseline

Length = (hi_ratio − lo_ratio) × forecast ÷ baseline. With the same ratios, a period with a lower forecast relative to normal gets a **shorter** line: DSNY's line is 28 points long for Mon–Wed but 20 for Sat–Mon.

### 3. The period's end date picks which range is used

`engine/dashboard.py:36-41` chooses by **the last day** of the period:

| Period ends on | Forecast and range used |
|---|---|
| Day 1–7 | Weekly model, days 1–7 range |
| Day 8–14 | Weekly model, **days 8–14 range** (slightly wider), even if the period starts on day 1 |
| Day 15 or later | **Monthly method** with its own forecast and range |

Moving the end date across day 7 or day 14 swaps the range. Crossing day 14 also swaps the entire forecast.

### 4. Crossing day 14 can move the line a lot, when the two methods disagree

DHS is the clearest case. Extending the period from 14 days to 15:

| | Days 1–14 (weekly model) | Days 1–15 (monthly method) |
|---|---:|---:|
| Forecast | 181 (≈ 12.9 a day) | 104 (≈ 6.9 a day) |
| Line | −29% ~ +49% | −62% ~ −26% |

The two methods see DHS differently:
- **Weekly model:** follows the recent level (12.8 a day over the last 28 days).
- **Monthly method:** uses the level from the last three months (July–September 2026 were low: 167, 172, 257) and a seasonal pattern where October–December fall sharply (2025: 378 → 224 → 104). It predicts only 215 for all of October.

October 2026 already had 192 complaints in its first 12 days (16 a day), so here the weekly model looks closer. Adding a single day flips DHS from "normal" to "−46%", deep in the "spare capacity" zone. **This discontinuity is a weakness of the switch at day 14.**

### 5. The chart rescales to fit all agencies

The x-axis range is recomputed for every view from all 8 agencies' lines, between −80% and +100% at most (`matrixBounds`, `frontend/src/charts/matrixOption.ts:9`). If one agency's line gets very long (DHS, or an agency with a weather alert), the axis stretches, and **every other line looks shorter on screen** even though its numbers didn't change. A line past +100% is cut off and drawn with an arrowhead.

### Also: weather alerts depend on the period

The alert widening applies only to days 1–7 after the reference date. Its size depends on how many flagged days fall inside the selected period, so the same alert widens a 3-day period that contains the snow day differently from a 30-day period.

### If you change the reference date instead

Then everything is recalculated: the 28-day baseline, the weekday ratios, the past errors used for the range, and the weather alerts. Large moves are expected there.

### Summary

| Cause | Changes the uncertainty? |
|---|---|
| Weekday mix vs a baseline without weekdays | No, just a shift |
| Line length ∝ forecast ÷ baseline | No, just scaling |
| End date crossing day 7 | A little (days 8–14 range is slightly wider) |
| End date crossing day 14 | Yes, a different forecast method, sometimes a large jump |
| Axis rescaling | No, display only |
| Weather alerts | Yes, the upper end only |

For comparing agencies, **full 7-day or 14-day periods starting on the reference date** give the most stable lines.
