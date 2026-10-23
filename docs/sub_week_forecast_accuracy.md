# Are forecasts for periods shorter than 7 days less accurate?

## The question

> The short-term model learned its rule on 7-day totals. It doesn't know how the day of the week affects the count.
> So a forecast for fewer than 7 days should be relatively less accurate. Is that right?

## Short answer

**Partly right.**

| Part of the expectation | Verdict |
|---|---|
| The model learned on 7-day totals | **Right.** It is trained only on 7-day sums (days 1–7 and 8–14). It never sees a single day. |
| It doesn't know the day of the week | **Half right.** The model itself has no day-of-week input. But the dashboard splits each weekly forecast into days using **day-of-week ratios** (`engine/build.py:41`, `engine/backlog.py:43`). So day of week *is* applied, as a fixed rule outside the model. |
| Shorter periods are less accurate | **Right**, and by a lot for 1–2 days. Most of that loss comes from day-to-day noise, though, not from missing day-of-week knowledge. |

## How the dashboard turns a week into days

1. LightGBM predicts the 7-day total, e.g. 700 complaints.
2. `dow_weights` takes the **last 8 weeks** of that agency and computes each weekday's average relative to the overall average.
3. The weekly total is split in those proportions. A period of fewer than 7 days is the sum of its days.

Day-of-week effects are strong, so this split is reasonable. Average 2022–2026 ratios to the daily mean:

| | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---:|---:|---:|---:|---:|---:|---:|
| DSNY | 1.09 | 1.21 | 1.15 | 1.13 | 1.03 | 0.70 | 0.68 |
| DOT | 1.14 | 1.23 | 1.25 | 1.22 | 1.11 | 0.55 | 0.49 |
| DHS | 1.03 | 1.09 | 1.11 | 1.11 | 1.03 | 0.87 | 0.75 |

Weekends run 25–50% below weekdays.

## Check: error by period length

This reuses the existing backtest predictions (247 Mondays, 2022-01 to 2026-09, 8 agencies, days 1–7). I didn't retrain anything.
For each week, I took the first 1, 2, 3, 5 or 7 days (starting Monday, as on the dashboard) and compared three ways of getting that sub-period:

- **Dashboard:** weekly forecast × day-of-week share (what the dashboard does now).
- **Even split:** weekly forecast × days / 7 (no day-of-week knowledge at all).
- **Perfect week:** the *actual* weekly total × day-of-week share. This isolates the error caused by the split alone.

The error measure is the same as in [forecast_error_verification.md](forecast_error_verification.md): the average of |forecast − actual| / actual per agency, then averaged across the 8 agencies. Weeks with 0 actual complaints (the DHS recording gap) are excluded.

| Period | Dashboard | Even split | Perfect week (split error only) |
|---|---:|---:|---:|
| 1 day (Mon) | **34.7%** | 31.4% | 31.4% |
| 2 days (Mon–Tue) | **23.0%** | 21.8% | 18.1% |
| 3 days (Mon–Wed) | **19.5%** | 20.1% | 12.4% |
| 5 days (Mon–Fri) | **16.7%** | 17.8% | 5.5% |
| 7 days | **15.4%** | 15.4% | 0.0% |

(1-day "even split" and "perfect week" both come to 31.4%; that's a coincidence. They differ once holidays are separated, below.)

### By agency (dashboard method)

| Agency | 1 day | 2 days | 3 days | 5 days | 7 days |
|---|---:|---:|---:|---:|---:|
| DOHMH | 24.1% | 13.5% | 10.9% | 8.8% | 8.4% |
| DSNY | 23.4% | 17.0% | 13.9% | 11.0% | 10.0% |
| DOB | 25.2% | 14.7% | 12.7% | 11.6% | 10.5% |
| DOT | 32.3% | 17.1% | 13.6% | 11.9% | 11.2% |
| DCWP | 51.3% | 25.8% | 19.9% | 16.5% | 15.9% |
| DPR | 36.7% | 27.5% | 23.6% | 20.5% | 19.4% |
| DEP | 31.0% | 26.2% | 25.0% | 22.7% | 21.4% |
| DHS | 53.9% | 42.1% | 36.4% | 30.3% | 26.1% |

## What this shows

1. **Your expectation about accuracy is right.** Error rises as the period shrinks: 15% for 7 days, 17% for 5, 20% for 3, 23% for 2, and 35% for 1 day. Small agencies suffer most: DCWP goes from 16% to 51%.

2. **The main cause is day-to-day noise, not the missing day-of-week input.** Even with a *perfect* weekly total, splitting it into one day already gives 31% error. One day's count is small and swings a lot. A model trained on daily data might reduce part of this (for example on holidays), but much of the swing is random and no model would remove it.

3. **The day-of-week split helps for 3–5 days but not for 1–2 days.**
   - 3 days: 19.5% vs 20.1% even split. 5 days: 16.7% vs 17.8%.
   - 1 day: 34.7% vs 31.4%. 2 days: 23.0% vs 21.8%. Here the split does *worse* than splitting evenly.

4. **Holidays are where the "doesn't know" part bites.** The day-of-week ratios are an 8-week average, so they don't know that *this* Monday is a holiday. About 20% of the weeks contain a holiday, and many US federal holidays fall on a Monday:

   | Period | Week has no holiday: dashboard / even split / perfect week | Holiday inside the period: dashboard / even split / perfect week |
   |---|---|---|
   | 1 day | 28.0% / 26.9% / 24.3% | **81.6%** / 61.5% / 77.8% |
   | 2 days | 21.8% / 21.7% / 16.4% | 31.5% / 22.2% / 27.5% |
   | 3 days | 19.0% / 20.3% / 11.6% | 21.9% / 17.9% / 15.6% |
   | 5 days | 16.4% / 17.7% / 5.4% | 17.7% / 18.1% / 5.7% |

   The weekly model accounts for the holiday through its `holidays` input, which lowers the weekly total. But the split then spreads that lower total across the days by the usual weekday pattern, instead of putting most of the drop on the holiday itself. For a 1-day period that falls on a holiday, error reaches 82%.

## Conclusion

- **Yes**, periods under 7 days are less accurate, and 1–2 days much less so (23–35% vs 15%).
- **Mostly not because of day of week.** The dashboard does apply day-of-week ratios, and they help for 3–5 days. Most of the extra error is unavoidable noise in small daily counts.
- **Where the expectation is fully right:** the split is a fixed rule, not something the model learned or that was validated. It breaks down on holidays and is no better than an even split for 1–2 days.
- The published 16.6% figure only applies to full 7-day periods. The dashboard doesn't currently state a separate error for shorter periods.

## Limits of this check

- Periods start on Monday only, because the backtest origins are Mondays (the same as the dashboard's reference dates). Other start days weren't tested.
- Only days 1–7 were checked. Sub-periods inside days 8–14 weren't.
- No model was retrained. Whether a model trained on daily data would do better wasn't tested; the "perfect week" column only shows how much error the split alone adds.
- Weeks with 0 actual complaints (the DHS recording gap in early 2026) are excluded, so the 7-day figure is 15.4%, not 16.6%.

---

## Follow-up: for a specific 3-day period, is the day-of-week ratio actually used?

> If I ask for the number of complaints over a specific 3-day period, does the dashboard actually use the day-of-week ratio described above?

**Yes.** Any period the user picks is the **sum of daily forecasts**, and every daily forecast was produced with the day-of-week ratio. There is no separate path for short periods.

### What happens, step by step

Example: reference date (asof) Monday 2026-10-12, period Wed 10-14 to Fri 10-16.

1. **Pre-computation** (`engine/build.py:87-91`), done once per reference date:
   - LightGBM forecasts the 7-day total for days 1–7 (10-12 to 10-18) and days 8–14 (10-19 to 10-25), per agency.
   - `dow_weights` (`engine/backlog.py:43`) takes the **8 weeks before the reference date** and computes each weekday's ratio for each agency.
   - `spread_daily` (`engine/build.py:41`) splits each 7-day total into 7 daily values in those proportions, and stores them in `forecast_daily`.
2. **When the period is requested** (`engine/dashboard.py:34-40`):
   - The period ends within 14 days, so the short-term rows are used.
   - The daily values for 10-14, 10-15 and 10-16 are summed per agency.

So the 3-day forecast = 7-day forecast × (Wed + Thu + Fri ratio) / (sum of all 7 ratios).

### Details that follow from this

| Case | What happens |
|---|---|
| The period starts on any weekday | Works. The custom date picker (`frontend/src/components/Controls.tsx:234-249`) lets you choose any start on or after the reference date. Only Monday-start periods were tested above. |
| The period crosses day 7 → day 8 (e.g. Sun–Tue) | Sunday's value comes from the days 1–7 forecast, Monday–Tuesday's from the days 8–14 forecast. Both use the ratio. |
| The period lies beyond day 14 (e.g. days 20–22) | The monthly forecast is used instead, and it is split into days with **the same** day-of-week ratio (`engine/build.py:96-103`). |
| A holiday falls in the period | No adjustment. The ratio is an 8-week weekday average, so a holiday Monday is treated as a normal Monday (see the holiday table above). |

### Two places where the ratio is *not* used

**1. The "change vs normal" baseline ignores day of week.**
The dashboard compares the forecast with a baseline of `28-day daily average × number of days` (`engine/dashboard.py:66`, `backend/app/store.py:152`). The baseline has no day-of-week ratio, but the forecast does.
For a short period, part of the "change" is therefore just the weekday mix. Using the 2022–2026 average ratios from the table above, with no real change in demand:

| Agency | Mon–Wed would show | Sat–Mon would show |
|---|---:|---:|
| DSNY | **+15%** | **−18%** |
| DOT | **+21%** | **−27%** |
| DHS | +8% | **−12%** |

The risk matrix uses +10% as "rising" and −10% as "spare capacity" (`engine/config.py`, `X_TH`, `SUPPORT_X`). A 3-day weekday period can push agencies into "rising", and a weekend period can make them look available to help, with no real change behind it. For 7-day periods the weekday mix cancels out, so this only affects periods that aren't whole weeks.

**2. The 80% range isn't adjusted for period length.**
The range uses the same lo/hi ratios as a full week (days 1–7 or days 8–14) (`engine/dashboard.py:41`). Since 3-day forecasts have more error (19.5% vs 15.4% above), the range is probably too narrow for short periods. I haven't measured the actual coverage for short periods; that would need a separate check.

### Answer

- **Yes**, the day-of-week ratio is applied to any 3-day period, whichever weekday it starts on.
- It is a fixed 8-week average per agency. It isn't learned by the model, and it doesn't account for holidays.
- The forecast uses it, but the baseline used for "change vs normal" and the matrix does not. So short periods that aren't whole weeks show a weekday-mix effect of up to about +21% (weekdays) or −27% (weekends). That is the larger practical problem for short periods.

---

## Follow-up: how is the day-of-week ratio calculated?

Code: `dow_weights` in `engine/backlog.py:43`. It's computed separately for each agency and each reference date.

1. Take the agency's daily counts for the **56 days (8 weeks) before the reference date**, so each weekday appears 8 times.
2. Average the counts for each weekday.
3. Divide each weekday's average by the average of the 7 weekday averages. The 7 ratios then always sum to 7, with 1.0 = an average day.

**Example:** DOT, reference date 2026-10-12, window 2026-08-17 to 2026-10-11.

| | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---:|---:|---:|---:|---:|---:|---:|
| 8-week average count | 101.5 | 108.2 | 107.6 | 113.5 | 102.2 | 51.1 | 47.6 |
| Ratio (÷ 90.3) | 1.12 | 1.20 | 1.19 | 1.26 | 1.13 | 0.57 | 0.53 |

A Wed–Fri period then gets (1.19 + 1.26 + 1.13) / 7 = **51.1%** of DOT's 7-day forecast.

Notes:
- The Monday average (101.5) includes Labor Day (2026-09-07). Holidays inside the 8-week window are averaged in, not removed.
- The table earlier in this file ("Average 2022–2026 ratios") uses the same formula over 2022-01 to 2026-09 instead of 8 weeks, to show the typical pattern. The dashboard always uses the 8-week version.
