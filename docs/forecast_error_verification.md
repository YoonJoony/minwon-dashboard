# How the forecast error rates were calculated

The dashboard's evidence panel (`engine/content.py:38-40`) and the presentation show two headline error rates:

| Figure | Shown as | Model | Calculated by |
|---|---|---|---|
| Weekly (days 1–7) error | **16.6%** | LightGBM (`engine/forecast_short.py`) | `analysis/verify_short_term.py` |
| Monthly error | **14%** | Seasonal index × recent level (`engine/forecast_long.py`) | `analysis/verify_long_term.py` |

Both are **MAPE** (mean absolute percentage error) from a **backtest**: go back to a past date, forecast using only the data known at that time, compare with what actually happened, and repeat.

Both were re-run on 2026-10-22 from the current data, and both reproduced exactly (16.6% and 14%).

---

## Data used for verification

| Item | Content |
|---|---|
| Source | NYC Open Data, 311 Service Requests (`erm2-nwe9` for 2020 onward, `76ig-c548` for 2010–2019) |
| Scope | Bronx, 8 agencies: DSNY, DEP, DOT, DOB, DOHMH, DPR, DCWP, DHS (DCA before 2020 renamed to DCWP) |
| Period | 2016-01-01 to 2026-10-12 |
| Size | 1,546,798 complaints, 0 duplicates |
| What the models see | Daily complaint count per agency (`data/processed/daily_agency_weather.csv`, 3,938 days × 8 agencies; days with no complaints = 0) |
| Day boundary | Complaint `created_date` in New York local time |
| Holidays | US federal holidays, computed in code (`engine/data.py`) |
| Weather | Not used by either model. The short-term check tested adding observed weather; it didn't help (16.6% → 16.8%), so it was left out. |

Pipeline: `pipelines/fetch_nyc311.py` → `pipelines/merge_weather.py` → `data/processed/`.

**Evaluation window:** 2022-01 to 2026-09 for both figures. Data from 2016–2021 is used only for training and history, never scored.

---

## Weekly error: 16.6%

### Setup

| Item | Value |
|---|---|
| Forecast made | Every Monday (the "origin"), using data up to the day before |
| Forecast target | Total complaints per agency over days 1–7 (this week). Days 8–14 are scored separately: **18.1%**. |
| Origins evaluated | **247 Mondays**, 2022-01-03 to 2026-09-21 |
| Forecasts scored | 247 weeks × 8 agencies = **1,976** for days 1–7 |
| Training | Retrained once per year on all origins **before** that year (2017 onward), e.g. the 2024 forecasts use a model trained on 2017–2023 |
| Model | Same inputs and settings as the dashboard model (see [short_term_feature_importance.md](short_term_feature_importance.md)) |

### Formula

For each agency and week:

```
error = | forecast − actual | / max(actual, 1)
```

1. Average the error over the 247 weeks **for each agency**.
2. Average the 8 agency results with **equal weight** → 16.6%.

`max(actual, 1)` guards against division by zero. It matters once in this window; see note 2 under "Things to know".

### Worked example: origin 2024-07-15, days 1–7

| Agency | Actual | Forecast | Error |
|---|---:|---:|---:|
| DCWP | 69 | 62.4 | 9.5% |
| DEP | 1,745 | 1,782.1 | 2.1% |
| DHS | 47 | 56.4 | 19.9% |
| DOB | 421 | 439.9 | 4.5% |
| DOHMH | 264 | 283.4 | 7.3% |
| DOT | 386 | 443.5 | 14.9% |
| DPR | 378 | 479.1 | 26.8% |
| DSNY | 932 | 1,001.6 | 7.5% |

The same calculation over all 247 weeks gives the per-agency averages below.

### Result by agency (days 1–7)

| Agency | Naive (last 28 days × 7) | **Model** |
|---|---:|---:|
| DOHMH | 9.1% | 8.4% |
| DSNY | 11.4% | 10.0% |
| DOB | 11.2% | 10.5% |
| DOT | 13.3% | 11.2% |
| DCWP | 16.0% | 15.9% |
| DPR | 24.2% | 19.4% |
| DEP | 26.5% | 21.4% |
| DHS | 42.0% | 36.1% |
| **Average** | **19.2%** | **16.6%** |

The baseline "naive" forecast simply repeats the last 4 weeks' daily average. The model reduces its error by about 2.6 points.

---

## Monthly error: 14%

### Setup

| Item | Value |
|---|---|
| Forecast target | Total complaints per agency for the **next calendar month** |
| Data available | Only months completed before the target month |
| Months evaluated | **57 months**, 2022-01 to 2026-09 |
| Forecasts scored | 57 × 8 agencies = 456 |
| Method | **Seasonal index × recent level**, no training step |

### How a monthly forecast is made

1. **Seasonal index** for the target month (e.g. July): for each of up to 7 past years, take "that July ÷ the 12-month average centred on it". Use the **median** of those ratios.
2. **Recent level**: for each of the last 3 completed months, divide the actual count by that month's own seasonal index. Average the 3 results.
3. **Forecast** = recent level × seasonal index of the target month.

### Formula

```
error = | forecast − actual | / actual
```

Average over the 57 months for each agency, then average the 8 agencies with equal weight → **14%** (shown rounded to a whole percent).

### Result by agency, compared with other methods

| Agency | Same month last year | Average of last 3 months | **Seasonal index × recent level** |
|---|---:|---:|---:|
| DOHMH | 9% | 12% | 7% |
| DOB | 12% | 11% | 7% |
| DCWP | 12% | 13% | 10% |
| DOT | 21% | 12% | 11% |
| DSNY | 23% | 15% | 11% |
| DPR | 30% | 43% | 20% |
| DEP | 24% | 49% | 21% |
| DHS | 31% | 55% | 29% |
| **Average** | **20%** | **26%** | **14%** |

The same method one **quarter** ahead (19 quarters) gives **12%**.

---

## Things to know when quoting these numbers

1. **"Average" means equal weight per agency.** A small agency like DHS (about 50 complaints a week) counts as much as DEP (over 1,000). Weighted by volume (total |error| ÷ total actual), the weekly error is **15.8%** (days 1–7) and **17.1%** (days 8–14).
2. **One DHS week inflates the headline by about 1.3 points.** DHS recorded **0 complaints on every day from 2026-01-31 to 2026-02-12**, after about 5 a day in January. This is most likely a recording gap, not a real drop. The week starting 2026-02-02 therefore has actual = 0 and forecast = 25. Divided by `max(0, 1) = 1`, that gives an error of **2,497%** for that single week.

   | | Days 1–7 | Days 8–14 |
   |---|---:|---:|
   | As shown (all weeks) | 16.6% (DHS 36.1%) | 18.1% (DHS 38.2%) |
   | Excluding the zero-actual week | **15.4%** (DHS 26.1%) | **16.9%** (DHS 28.6%) |

   The shown figure is the conservative one. Without that week, the model's typical weekly error is about 15%.
3. **The range is wide.** Weekly error runs from 8% (DOHMH) to 36% (DHS). Monthly runs from 7% to 29%. DEP, DPR and DHS are hard to forecast, which is why the dashboard shows a range for them.
4. **The two figures aren't directly comparable.** Monthly sums are larger and smoother, so percentage errors shrink. The monthly method being "better" (14% vs 16.6%) doesn't mean it would beat the LightGBM model on weekly forecasts.
5. **The 80% range coverage (70–89%) comes from a slightly different variant.** `verify_long_term.py` measures coverage for "seasonal index × recent level, **excluding 2020–2021** from the seasonal history". That variant's error is **15%**. The 14% comes from the variant without the exclusion, which is the one `engine/forecast_long.py` uses.
6. **These are backtests, not live results.** Each forecast only used data available at the time, but the method itself was chosen after looking at this period. Expect live error to be similar or slightly higher.

## Reproducing

```bash
uv run python analysis/verify_short_term.py   # weekly: 16.6% (days 1–7), 18.1% (days 8–14)
uv run python analysis/verify_long_term.py    # monthly: 14%, quarterly: 12%
```

Both scripts read `data/processed/daily_agency_weather.csv`. `verify_short_term.py` writes its per-forecast results to `analysis/results/short_term_backtest.csv`.
