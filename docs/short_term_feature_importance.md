# Short-term forecast model: feature contribution (%)

Model: `engine/forecast_short.py`, the LightGBM model behind the dashboard's 1–7 and 8–14 day forecasts.
Data: Bronx NYC 311, 8 agencies, 2016-01-01 to 2026-10-12 (1,546,798 complaints), weekly Monday origins from 2017.
Run on 2026-10-22.

> **Note:** this model is a **regressor**, not a classifier. It predicts
> `log((actual + 1) / (28-day average × 7 + 1))`, which is how far the coming week will move from the recent level.
> "Contribution" below means how much each input drives that prediction.

## The answer (production model, as of 2026-10-12)

The production model is the one `forecast()` trains on the latest date. It used 8,144 training rows.
The headline measure is **mean |SHAP|**, the average amount each feature actually moved a prediction.

| Rank | Feature | What it is | Contribution |
|---:|---|---|---:|
| 1 | `woy_sin` | Time of year (sine) | **26.9%** |
| 2 | `r7_r28` | Last 7 days ÷ last 28 days (recent momentum) | **24.0%** |
| 3 | `woy_cos` | Time of year (cosine) | **15.0%** |
| 4 | `holidays` | Public holidays in the forecast week | **12.0%** |
| 5 | `agency` | Which department | **11.4%** |
| 6 | `season_ratio` | Same week in the past 3 years ÷ their prior 28 days (median) | **9.8%** |
| 7 | `block` | 1–7 days vs 8–14 days ahead | **0.9%** |
| | | **Total** | **100%** |

### Grouped by meaning

| Group | Features | Contribution |
|---|---|---:|
| Time of year | `woy_sin` + `woy_cos` | **41.9%** |
| Recent momentum | `r7_r28` | **24.0%** |
| Holidays | `holidays` | **12.0%** |
| Department | `agency` | **11.4%** |
| Past years, same week | `season_ratio` | **9.8%** |
| Forecast horizon | `block` | **0.9%** |

Seasonality (calendar position plus past-year pattern) explains about **52%**. Recent momentum explains about **24%**.

## Three ways of measuring, compared

Each column sums to 100%.

| Feature | Gain (error reduced by splits) | Split (number of splits) | Mean \|SHAP\| (effect on predictions) |
|---|---:|---:|---:|
| `woy_sin` | 22.1% | 23.7% | 26.9% |
| `r7_r28` | **27.7%** | 22.6% | 24.0% |
| `woy_cos` | 19.1% | 22.5% | 15.0% |
| `holidays` | 2.9% | 2.1% | 12.0% |
| `agency` | 9.7% | 9.9% | 11.4% |
| `season_ratio` | 17.9% | 17.8% | 9.8% |
| `block` | 0.6% | 1.4% | 0.9% |

How to read the differences:

- **`holidays`: 3% gain, 12% SHAP.** The model splits on it rarely, because most weeks have no holiday. But each of those splits moves the forecast a lot: a holiday week has noticeably fewer complaints. Holidays matter a lot when they occur and do nothing otherwise.
- **`season_ratio`: 18% gain, 10% SHAP.** It reduces training error substantially, but its typical effect on any one prediction is smaller. The time-of-year features already cover much of the same signal.
- **`r7_r28`** ranks first by gain. It is the single most useful variable for fitting the data.

## Stability over time (backtest, retrained each year)

Mean |SHAP| for each yearly model. Each model is trained on all data before that year and evaluated on that year's forecasts.

| Feature | 2022 | 2023 | 2024 | 2025 | 2026 | Average |
|---|---:|---:|---:|---:|---:|---:|
| `woy_sin` | 25.9% | 26.6% | 28.3% | 27.6% | 28.1% | 27.3% |
| `r7_r28` | 21.2% | 22.0% | 21.4% | 21.1% | 27.4% | 22.6% |
| `woy_cos` | 16.9% | 15.8% | 14.5% | 16.1% | 14.2% | 15.5% |
| `holidays` | 13.8% | 12.6% | 12.7% | 13.0% | 10.0% | 12.4% |
| `agency` | 10.7% | 11.3% | 10.9% | 11.2% | 9.4% | 10.7% |
| `season_ratio` | 10.6% | 11.0% | 11.3% | 10.3% | 10.0% | 10.6% |
| `block` | 0.8% | 0.7% | 0.9% | 0.8% | 0.8% | 0.8% |

The ranking holds steady across all five years. In 2026, recent momentum (`r7_r28`) gained weight (27%).
Part of the reason: 2026 covers only January to October, so it has no Thanksgiving or Christmas weeks, and holidays account for less.

## By forecast horizon (production model, mean |SHAP|)

| Feature | Days 1–7 | Days 8–14 |
|---|---:|---:|
| `woy_sin` | 26.7% | 27.0% |
| `r7_r28` | 24.4% | 23.5% |
| `woy_cos` | 15.0% | 15.1% |
| `holidays` | 12.2% | 11.8% |
| `agency` | 11.6% | 11.3% |
| `season_ratio` | 9.2% | 10.4% |
| `block` | 0.9% | 0.9% |

As expected, recent momentum matters slightly less for the second week, and past-year seasonality slightly more. The difference is small.

## Takeaways

1. **Calendar seasonality drives the model** (about 42% from time of year, about 52% including past-year patterns).
2. **Recent momentum is the strongest single signal** (24% of the effect on predictions, 28% of the gain).
3. **Holidays have a large effect in the few weeks that contain one.** Split counts understate their importance.
4. **Forecast horizon (`block`) contributes almost nothing** (under 1%). Keeping it is harmless but optional.

## Method

- Contributions are computed on the same feature rows and hyperparameters used by `engine/forecast_short.py`. No model code was changed.
- **Gain**: the total loss reduction from splits on the feature (`booster.feature_importance("gain")`).
- **Split**: the number of splits on the feature.
- **Mean |SHAP|**: the average absolute per-row contribution (`predict(..., pred_contrib=True)`), on training rows for the production model and on test-year rows for the backtest.
- Each measure is normalised to 100%.
