# Are the backtests cumulative (yearly)?

## Short answer

| Backtest | Cumulative? | How often the model is updated |
|---|---|---|
| Weekly forecast (LightGBM, the 16.6%) | **Yes**: an expanding window starting in 2017 | **Once a year** |
| Monthly forecast (seasonal index, the 14%) | **Partly**: no training; the seasonal pattern uses up to 7 past years, the level uses the last 3 months | **Every month** |
| 80% range (past errors) | **Yes**: all settled past errors up to the reference date | At every reference date |

## 1. Weekly forecast: cumulative, retrained once a year

Code: `backtest` in `engine/forecast_short.py:70` (the same logic as `analysis/verify_short_term.py`).

For each test year, the model is trained on **every week from 2017 up to the start of that year**, then predicts all of that year's weeks without retraining:

| Test year | Training data | Training rows | Weeks predicted with that model |
|---|---|---:|---|
| 2022 | 2017-01 ~ 2021-12 | 4,176 | all of 2022 |
| 2023 | 2017-01 ~ 2022-12 | 5,008 | all of 2023 |
| 2024 | 2017-01 ~ 2023-12 | 5,840 | all of 2024 |
| 2025 | 2017-01 ~ 2024-12 | 6,688 | all of 2025 |
| 2026 | 2017-01 ~ 2025-12 | 7,520 | 2026-01 ~ 2026-09 |

(Each "row" is one reference Monday × days 1–7 or 8–14 × one agency. The first usable Monday is in early 2017, because the inputs need about a year of history.)

- **Cumulative:** the start stays fixed at 2017 and the end moves forward. Old data is never dropped.
- **Yearly:** a forecast in December uses a model that hasn't seen anything from January–November of that year. Backtest accuracy is therefore slightly pessimistic compared with the dashboard.

### The dashboard is different: it retrains at every reference date

`forecast()` in `engine/forecast_short.py:82` trains a fresh model for **each reference date**, on every week whose result was already known 2 weeks before it (`origin + 13 days < reference date`). It's still cumulative from 2017, but up to date every week rather than once a year.

### A small overlap at each year boundary

The yearly backtest uses "reference Monday before January 1" as its training cut-off. A training week starting in late December has a days 8–14 target that ends in **early January**. So the first test week of each year overlaps a few days the model already learned from. The dashboard's own rule (`+13 days < reference date`) doesn't have this problem.

I re-ran the backtest with the dashboard's stricter cut-off. The effect is small:

| | As published | With the strict cut-off |
|---|---:|---:|
| Days 1–7 error | 16.6% | **16.8%** |
| Days 8–14 error | 18.1% | **18.2%** |
| First 2 weeks of each year only (days 1–7) | 16.4% | 17.2% |

The published numbers are about 0.1–0.2 points optimistic for this reason.

## 2. Monthly forecast: a monthly walk-forward, with no training

Code: `analysis/verify_long_term.py` for the 14%, and `walk_forward` in `engine/forecast_long.py:41` for the dashboard's range.

There's no model to train. For every month from 2022-01 to 2026-09, the forecast is recalculated using only the months already completed:

- **Seasonal index:** the median over **up to 7 past years** of "that month ÷ the 12-month average around it". The window grows until 7 years are available, then rolls forward, so it isn't purely cumulative.
- **Recent level:** **the last 3 completed months** only (a rolling window).

So it's updated **every month**, not yearly.

## 3. The 80% range: cumulative errors

`interval_ratios` (`engine/forecast_short.py:87`, `engine/forecast_long.py:52`) takes **all past forecast errors whose result was known before the reference date** and uses their 10th and 90th percentiles.

- Weekly range: errors from the yearly backtest above, starting in 2022. On 2026-10-12 that's 249 past weeks per agency.
- Monthly range: errors from the monthly walk-forward, starting in 2019.

Each new week (or month) adds one more error to the pool. Nothing is dropped, so the range reflects the whole history equally, including unusual years like 2020–2021 for the monthly range.

## Summary

- **Weekly backtest:** cumulative from 2017 and retrained once a year. The dashboard itself retrains at every reference date. A small overlap at year boundaries makes the published 16.6% about 0.2 points optimistic (strict: 16.8%).
- **Monthly backtest:** no training. It's recalculated every month from the last 3 months plus up to 7 years of seasonal history.
- **80% range:** uses all past errors up to the reference date, growing over time.

---

## Follow-up: is the 2022 model updated for 2023, or rebuilt from scratch?

> To predict 2023, do you take the model used for 2022 and tune it with 2022's actual data? Or do you build a new model from scratch?

**A new model is built from scratch every time.**

`fit` (`engine/forecast_short.py:62`) creates a brand-new LightGBM model and trains it on the full training set:

```python
def fit(train):
    return lgb.LGBMRegressor(**PARAMS).fit(train[FEATURES], train["target"])
```

For 2023, that means:

| | What happens |
|---|---|
| The 2022 model | **Thrown away.** It isn't saved, loaded, or continued. |
| New model's training data | **All weeks from 2017 to 2022** (5,008 rows), so 2017–2021 is learned again together with 2022 |
| Settings (number of trees, learning rate, leaves, …) | **The same fixed values** (`PARAMS`, `engine/forecast_short.py:18`). There is no per-year tuning. |
| Randomness | Fixed seed (`random_state=0`), so the same data gives the same model |

The code has no `init_model`, warm start, or saved models anywhere in `engine/` or `analysis/`.

The dashboard works the same way: `forecast()` builds a new model from scratch for each reference date.

### Why from scratch rather than updating

- **Simple and reproducible:** each model depends only on its training data, not on the order in which earlier models were trained.
- **Cheap:** about 4,000–8,000 rows train in a few seconds.
- **Gradient-boosted trees don't update well.** Continuing training would only *add* trees fitted to the new data on top of the old ones. The existing trees, built without 2022, would never be revised. Retraining lets every tree use 2022 together with the earlier years.

The trade-off is that 2017 counts as much as 2022 in every model. Recent years get no extra weight.
