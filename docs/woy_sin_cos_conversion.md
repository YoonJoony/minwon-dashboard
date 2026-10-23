# How a date becomes `woy_sin` and `woy_cos`

These are the two time-of-year inputs of the short-term forecast model (`engine/forecast_short.py`).
Together they make up 41.9% of the model's effect on predictions (see [short_term_feature_importance.md](short_term_feature_importance.md)).

## The code

`engine/forecast_short.py:51`:

```python
"woy_sin": np.sin(2 * np.pi * s.dayofyear / 365.25),
"woy_cos": np.cos(2 * np.pi * s.dayofyear / 365.25),
```

`s` is the **first day of the forecast block**, not the origin date itself:

- **Days 1–7:** `s` = the origin (a Monday).
- **Days 8–14:** `s` = the origin + 7 days.

Each block gets the season value of the week it's forecasting.

## Step by step: origin 2026-10-12, days 1–7

| Step | Formula | Value |
|---|---|---|
| 1. Date | `s` | 2026-10-12 |
| 2. Day of year | `s.dayofyear` | 285 |
| 3. Fraction of the year | 285 / 365.25 | 0.7803 |
| 4. Angle on a circle | 2π × 0.7803 | 4.9027 rad (≈ 281°) |
| 5. `woy_sin` | sin(4.9027) | **−0.9819** |
| 6. `woy_cos` | cos(4.9027) | **0.1892** |

The days 8–14 row of the same origin starts on 2026-10-19 (day 292), which gives `woy_sin` = −0.9521 and `woy_cos` = 0.3057.

## Where dates land on the circle

| Date | Day of year | woy_sin | woy_cos | Position |
|---|---:|---:|---:|---|
| 2026-01-01 | 1 | 0.017 | 1.000 | start of year |
| 2026-04-02 | 92 | 1.000 | −0.012 | spring (¼ year) |
| 2026-07-02 | 183 | −0.007 | −1.000 | summer (½ year) |
| 2026-10-12 | 285 | −0.982 | 0.189 | autumn (¾ year) |
| 2026-12-31 | 365 | −0.004 | 1.000 | back next to Jan 1 |

## Why two numbers instead of just "day 285"

If you used the day number alone, Dec 31 (365) and Jan 1 (1) would look as far apart as two dates can be, even though they're one day apart.
Putting the day on a circle fixes that: Dec 31 sits at (−0.004, 1.000) and Jan 1 at (0.017, 1.000), right next to each other.

You need both values because either one alone is ambiguous. For example, `woy_sin` ≈ 0 on both Jan 1 and Jul 2. The cosine (+1 vs −1) tells them apart.
Together, the pair identifies a unique point in the year.

This is also why the feature-importance report counts them together as "time of year" (41.9%).
Splitting that between `woy_sin` and `woy_cos` doesn't mean much on its own.

## Does "distance between two dates" equal "Euclidean distance between their (woy_sin, woy_cos)"?

**No, not in general.** Euclidean distance gives the same *ordering* by seasonal closeness, but not the same values.
It also ignores which year a date is in.

### The exact relationship

Both points lie on a unit circle, so the Euclidean distance between them is the chord between two angles:

```
distance = 2 × | sin( π × (doy_a − doy_b) / 365.25 ) |
```

`doy` is `s.dayofyear`. The formula depends only on the difference in **day of year**, not on the number of days between the dates.

### Checked on actual dates

"Linear" is what the distance would be if it grew in a straight line with the gap (2π × days / 365.25 ≈ 0.0172 per day).

| Date A | Date B | Days apart | Euclidean distance | Linear | Note |
|---|---|---:|---:|---:|---|
| 2026-10-12 | 2026-10-13 | 1 | 0.0172 | 0.0172 | equal |
| 2026-10-12 | 2026-10-19 | 7 | 0.1203 | 0.1204 | almost equal |
| 2026-10-12 | 2026-11-12 | 31 | 0.5270 | 0.5333 | 1% short |
| 2026-10-12 | 2026-07-12 | 92 | 1.4226 | 1.5826 | 10% short |
| 2026-10-12 | 2027-04-12 | 182 | **2.0000** | 3.1308 | maximum: opposite side of the year |
| 2025-10-12 | 2026-10-12 | 365 | **0.0000** | 6.2789 | one year apart = same point |
| 2016-10-12 | 2026-10-12 | 3,652 | 0.0172 | 62.8233 | ten years apart looks like 1 day |
| 2026-12-31 | 2027-01-01 | 1 | 0.0215 | 0.0172 | year-end wrap looks like 1.25 days |

### What this means

1. **Different units.** One day ≈ 0.0172. To read the distance in days, convert it: days ≈ 365.25 × arcsin(distance / 2) / π.
2. **Short gaps: approximately yes.** Up to about a month the error is about 1% or less, because a short chord is almost the same length as its arc.
3. **Long gaps: compressed.** The distance grows more slowly than the gap. It peaks at 2.0 around half a year, then *shrinks* as the dates come back around the circle.
4. **The year is lost.** Dates one year or ten years apart sit on (nearly) the same point. This is intended: the features describe *time of year* only. Long-term level is handled by the 28-day base and `r7_r28`.
5. **Calendar quirks** come from using `dayofyear` with 365.25:
   - In a leap year, every date after February 28 has a day-of-year one higher. So 2016-10-12 (day 286) and 2026-10-12 (day 285) sit one "day" apart.
   - Dec 31 → Jan 1 (day 365 → 1) measures as 1.25 days instead of 1.
6. **What is preserved:** for gaps up to half a year, a smaller seasonal gap always means a smaller Euclidean distance. So "which dates are seasonally closer" keeps the right order, with no Dec–Jan jump.

### Does it matter for this model?

**Not much.** LightGBM never computes a Euclidean distance. Each tree split looks at `woy_sin` or `woy_cos` on its own (e.g. `woy_sin < −0.8`), and several splits together cut out a range of the year.
What matters for LightGBM is that the circle has no Dec 31 → Jan 1 jump, and that each pair maps to one point in the year.
The distance property matters for distance-based models (k-nearest neighbours, k-means, kernels), which this project doesn't use for the short-term forecast.

## Why two values (sin and cos) instead of one?

> Why use two values, sin and cos, each with a half-year cycle, rather than just one of them with a full-year cycle?

### First, a correction: both already have a full-year cycle

`woy_sin` and `woy_cos` both divide by **365.25**, so each repeats **once a year**, not every half year:

```python
np.sin(2 * np.pi * s.dayofyear / 365.25)   # one full wave per year
np.cos(2 * np.pi * s.dayofyear / 365.25)   # one full wave per year, shifted by a quarter
```

(A half-year cycle would divide by 182.6, i.e. `4 * np.pi * dayofyear / 365.25`.)

So the real question is: why not keep **one** full-year wave and drop the other?

### One wave alone gives the same value to two different times of year

Within a year, a single sine or cosine passes through every value twice: once on the way up and once on the way down. Two dates that are far apart get the same number, and the model can't tell them apart.

| Kept only | Dates that look identical | Value | Their complaints (avg daily count ÷ annual avg, 2017–2025) |
|---|---|---|---|
| `woy_sin` | **Jul 15** (day 196) and **Dec 18** (day 352) | −0.228 vs −0.226 | DEP **2.53** (Jul) vs 0.59 (Dec); DPR **1.64** vs 0.46 |
| `woy_cos` | **Mar 15** (day 74) and **Oct 18** (day 291) | 0.293 vs 0.289 | DHS 0.51 (Mar) vs **1.53** (Oct); DCWP **1.56** vs 0.85 |

- `woy_sin` alone is mirrored around Apr 2 and Oct 1. It confuses **summer with early winter**, DEP's busiest month with one of its quietest.
- `woy_cos` alone is mirrored around Jan 1 and Jul 2. It confuses **spring with autumn**.

With both, the cosine separates the `woy_sin` pairs (−0.974 vs 0.974) and the sine separates the `woy_cos` pairs (0.956 vs −0.957). Every date gets its own point, as described in "Why two numbers instead of just 'day 285'" above.

### Checked: one wave vs two

I retrained the model with only the time-of-year inputs changed. Same backtest as `verify_short_term.py` (247 Mondays × 8 agencies, 2022-01 to 2026-09, yearly retrain), LightGBM seed 0.

| Time-of-year input | Days 1–7 | Days 8–14 | Days 1–7, excl. DHS zero week |
|---|---:|---:|---:|
| **`woy_sin` + `woy_cos` (now)** | **16.62%** | **18.10%** | **15.37%** |
| `woy_sin` only | 17.04% | 18.67% | 15.50% |
| `woy_cos` only | 16.89% | 18.64% | 15.59% |
| Half-year sin + cos (period 182.6 days) | 17.33% | 19.12% | 15.78% |
| Day number (`dayofyear`, 1–366) | 16.38% | 18.14% | 15.21% |
| No time-of-year input | 17.42% | 19.60% | 15.79% |

- **One wave is worse than two:** +0.3 to +0.6 points. It still helps compared with none, because `season_ratio` partly covers what the single wave can't distinguish.
- **A half-year cycle would be the worst choice.** It makes Jan 1 and Jul 2 identical (cos = 0.999 vs 1.000), so winter looks like summer. It's barely better than no time-of-year input at all.
- **The plain day number does about as well as sin + cos:** 0.24 points better on days 1–7 and 0.04 worse on days 8–14. That fits the point under "Does it matter for this model?": a tree model can cut the day number into ranges directly. The year-end jump (Dec 31 = 365, Jan 1 = 1) costs a tree little, because that's a quiet period in both directions.
  This is from one seed, and changing the seed alone moves results by about 0.13 points (see [xgboost_vs_lightgbm.md](xgboost_vs_lightgbm.md)). So this isn't enough evidence to switch. Sin + cos remains the safer encoding if the model ever changes to one that measures distances.

Reproduce: `uv run python analysis/compare_season_encoding.py`.
