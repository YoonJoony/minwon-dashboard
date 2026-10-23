# Would XGBoost beat LightGBM for the weekly forecast?

## The question

> Would changing the week forecast model (`engine/forecast_short.py`) from LightGBM to XGBoost give better performance?

This is an **expectation, not a measured result**. Nothing was retrained or implemented. The numbers below come from the existing backtest (`analysis/results/short_term_backtest.csv`, 247 Mondays, 2022-01 to 2026-09, 8 agencies).

## Short answer

**Probably not by any amount that matters.**

| | Current (LightGBM) | Expected with XGBoost |
|---|---:|---:|
| Weekly error, days 1–7 (as shown) | 16.6% | **about 16.3–16.9%** |
| Weekly error, excluding the DHS zero week | 15.4% | **about 15.1–15.7%** |
| Days 8–14 | 18.1% | **about 17.8–18.4%** |

My best guess is a change of **±0.3 points**, in either direction. That's smaller than the year-to-year swing in the backtest, and too small for anyone to notice on the dashboard. If XGBoost comes out ahead, I'd expect the cause to be its different default settings, not the algorithm.

## Why I expect no real gain

### 1. The two are the same kind of model

Both are gradient-boosted decision trees. They fit the same target (`log((actual + 1) / (28-day average × 7 + 1))`) in the same way. The differences are in the details:

| | LightGBM (now) | XGBoost |
|---|---|---|
| Tree growth | Leaf by leaf (`num_leaves: 15`) | Level by level by default (`max_depth`) |
| Split search | Histogram | Histogram (`tree_method="hist"`) |
| `agency` (8 values) | Native categorical | Native with `enable_categorical=True`, or one-hot |
| Regularisation | `min_child_samples`, subsampling | `min_child_weight`, `lambda`, `gamma`, subsampling |

With 15 leaves, LightGBM's trees are about the size of a depth-4 XGBoost tree. On a dataset this size, the two usually land within a few tenths of a point of each other once both are set up sensibly.

### 2. The data is small and simple

- About **8,100 training rows** and **7 inputs** (see [short_term_feature_importance.md](short_term_feature_importance.md)).
- Two of those inputs (`woy_sin`, `woy_cos`) are smooth curves, and the rest are a few ratios and counts.

Neither library has room to find anything here that the other misses. Differences in how they handle large or sparse data don't come into play.

### 3. The learner isn't what's limiting accuracy

The whole model only beats the naive forecast (last 28 days × 7) by **2.6 points** (19.2% → 16.6%). Most of the remaining error comes from things the inputs can't see, not from the model fitting the inputs badly.

A rough check: if complaints followed pure chance around a perfectly known average (Poisson noise), what error would be unavoidable? Using each week's actual count, days 1–7, zero-actual week excluded:

| Agency | Avg. per week | Naive | **Model** | Unavoidable noise only | Gap left |
|---|---:|---:|---:|---:|---:|
| DOHMH | 239 | 9.1% | **8.4%** | 5.2% | 3.2 |
| DSNY | 815 | 11.4% | **10.0%** | 2.9% | 7.1 |
| DOB | 331 | 11.2% | **10.5%** | 4.5% | 6.0 |
| DOT | 574 | 13.3% | **11.2%** | 3.4% | 7.8 |
| DCWP | 62 | 16.0% | **15.9%** | 10.3% | 5.6 |
| DPR | 237 | 24.2% | **19.4%** | 5.8% | 13.6 |
| DEP | 552 | 26.5% | **21.4%** | 3.9% | 17.5 |
| DHS | 44 | 29.1% | **26.1%** | 13.4% | 12.7 |
| **Average** | | | **15.4%** | **6.2%** | **9.2** |

There is a 9-point gap above pure noise, but it's concentrated in **DEP, DPR and DHS**. Those agencies have sudden jumps: storms flooding sewers (DEP), tree damage (DPR), and recording gaps (DHS). None of the 7 inputs warns about these in advance. A different tree library gets the same inputs, so it can't predict these jumps either.

### 4. Past changes to the model moved the number very little

- Adding observed weather moved the error from 16.6% to **16.8%** ([forecast_error_verification.md](forecast_error_verification.md)). That was new *information*, and it still didn't help.
- A library swap adds no new information, so I'd expect an even smaller effect.

## What switching would cost

- **Every quoted figure changes.** The 16.6%, the 18.1%, the per-agency table, the 80% ranges (`interval_ratios`) and the feature-contribution doc would all need re-running and re-checking.
- **Settings need tuning again.** The current `PARAMS` were picked for LightGBM. A fair comparison needs XGBoost tuned to the same degree, or the result mostly reflects how good the settings are.
- **Reproducibility.** `feature_rows` sorts rows on purpose, because LightGBM's sampling depends on row order. XGBoost's sampling does too, so the dashboard and `verify_short_term.py` would need to be re-checked against each other.
- **A new dependency** (`xgboost`) in `pyproject.toml` (macOS also needs `libomp`, as LightGBM does now).

## If the goal is a lower error, where I'd look instead

Rough expected gains, also estimates:

| Option | Expected change | Why |
|---|---:|---|
| Swap to XGBoost | ±0.3 pt | Same model family, same inputs |
| Average LightGBM + XGBoost predictions | −0.1 to −0.3 pt | Averaging slightly different models usually cancels a little noise. Adds complexity for little gain. |
| Train on the error we report (e.g. L1 / absolute-error loss on the log ratio) | −0.2 to −0.5 pt | The model minimises squared error but we score it on absolute % error. Big misses get extra weight in training. |
| Inputs that warn about DEP/DPR jumps (e.g. the 7-day weather *forecast*, already on the dashboard strip) | Uncertain, possibly −0.5 to −1.5 pt for those agencies | This is where the gap is. But observed weather already failed once, so I'd expect any gain to be small. |

## If you want to test it anyway

It's cheap to check without touching the dashboard:

1. In a copy of `analysis/verify_short_term.py`, swap `fit()` for `xgboost.XGBRegressor(tree_method="hist", enable_categorical=True, max_depth=4, learning_rate=0.03, n_estimators=400, subsample=0.8, colsample_bytree=0.8, min_child_weight=…)`.
2. Run the same yearly-retrain backtest (2022–2026), with **3–5 random seeds for both** models, so seed noise is visible.
3. Compare **per week**, not just the headline: count how many of the 1,976 forecasts each model wins, and check each year and agency separately.
4. **Switch only if** XGBoost is at least **0.5 points better** on average **and** wins in most years. Otherwise, keep LightGBM.

My expectation is that step 4 fails.

---

## Result of the test (run 2026-10-23)

**The expectation held. XGBoost is no better in any way that matters.** It fails the switch rule: the best version is **0.04 points** better on the headline figure. The rule required 0.5.

Script: `analysis/compare_xgboost_short_term.py`. Per-forecast output: `analysis/results/xgb_vs_lgbm_backtest.csv`.
Same inputs, target and yearly-retrain backtest as `verify_short_term.py` (247 Mondays × 8 agencies, 2022-01 to 2026-09). Each model was run with 5 seeds (0–4). xgboost 3.4.1, lightgbm 4.7.0.
LightGBM with seed 0 gives 16.62%, which reproduces the published 16.6%.

### Models compared

| Name | Setup |
|---|---|
| `lgbm` | The current model (`num_leaves=15`, `min_child_samples=30`) |
| `xgb_leaves15` | XGBoost built the same way: grows leaf by leaf, up to 15 leaves |
| `xgb_depth3/4/5` | XGBoost's default style: grows level by level, depth 3, 4 or 5 |

All use the same learning rate, number of trees and subsampling. `min_child_weight=30` matches `min_child_samples=30`, because each row has a weight of 1 under squared error.

### Headline error (MAPE, same definition as the published 16.6%)

| Model | Days 1–7, range over seeds | Days 1–7, seed-averaged forecast | Days 1–7, excl. DHS zero week | Days 8–14 | Days 8–14, excl. zero week |
|---|---:|---:|---:|---:|---:|
| **`lgbm` (now)** | 16.62–16.75% | **16.66%** | **15.36%** | **18.12%** | **16.90%** |
| `xgb_leaves15` | 16.57–16.75% | 16.64% | 15.34% | 18.10% | 16.88% |
| `xgb_depth3` | 16.64–16.73% | 16.67% | 15.17% | 18.25% | 16.89% |
| `xgb_depth4` | 16.59–16.70% | 16.62% | 15.22% | 18.09% | 16.83% |
| `xgb_depth5` | 16.65–16.70% | 16.65% | 15.31% | 18.10% | 16.85% |
| Average of `lgbm` + `xgb_depth4` | | 16.61% | 15.26% | 18.07% | 16.83% |

- Every XGBoost variant lands within **0.1 points** of LightGBM on the published figure.
- Changing only LightGBM's seed moves the result by **0.13 points**. That's as much as switching libraries does.
- Excluding the zero week, the best case (`xgb_depth3`) is 0.19 points better on days 1–7. But it's 0.13 points *worse* on days 8–14. Picking the winner after seeing these results would overstate the gain anyway.
- `xgb_leaves15`, built the same way as LightGBM, matches it to within 0.02 points. That confirms the library itself makes no difference.

### By year (days 1–7, seed-averaged)

| Year | `lgbm` | `xgb_depth4` | `xgb_leaves15` |
|---|---:|---:|---:|
| 2022 | 15.78% | 15.51% | 15.72% |
| 2023 | 15.13% | 15.03% | 15.22% |
| 2024 | 14.47% | 14.39% | 14.48% |
| 2025 | 13.08% | 12.88% | 13.01% |
| 2026 | 27.90% | 28.51% | 27.82% |

`xgb_depth4` is ahead in 4 of 5 years, but by only 0.1–0.3 points each. In 2026 it's 0.6 points behind. (2026 is inflated for every model by the DHS week with zero recorded complaints.)

### By agency (days 1–7, excl. zero week)

| Agency | `lgbm` | `xgb_depth4` |
|---|---:|---:|
| DOHMH | 8.4% | 8.3% |
| DSNY | 10.0% | 9.7% |
| DOB | 10.6% | 10.5% |
| DOT | 11.2% | 11.4% |
| DCWP | 15.7% | 15.6% |
| DPR | 19.5% | 19.1% |
| DEP | 21.6% | 21.5% |
| DHS | 25.8% | 25.7% |

The hard agencies (DEP, DPR, DHS) are just as hard with XGBoost, as expected.

### Head to head, forecast by forecast

Out of 1,976 forecasts for days 1–7, `xgb_depth4` was closer **51.5%** of the time and `lgbm` 48.5%. For days 8–14 it was 51.2% vs 48.8%. With this many forecasts, a 50/50 coin would land 1.3 points from even fairly often, so this is no real evidence of a difference.

### Verdict

| Switch rule | Result |
|---|---|
| At least 0.5 points better on average | **No.** 0.04 points (published figure), 0.14 points (excl. zero week) |
| Wins in most years | Yes, 4 of 5, but by 0.1–0.3 points |

**Keep LightGBM.** Switching would change every published number and the 80% ranges, for a gain smaller than the effect of changing the random seed. Averaging the two models doesn't help enough either: about 0.05–0.1 points.

### Reproducing

`xgboost` is not a project dependency. Install it first, then run:

```bash
pip install xgboost
uv run python analysis/compare_xgboost_short_term.py
```
