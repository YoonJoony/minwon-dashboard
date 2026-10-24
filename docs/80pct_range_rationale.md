# Why base the 80% range on past forecast errors?

This approach was already in the project (`interval_ratios` in `engine/forecast_short.py` and `engine/forecast_long.py`). This note explains why it is a sound choice, and where it falls short.

For what the range is and how it's calculated, see [weather_forecast_usage.md](weather_forecast_usage.md) ("The 80% range, explained more simply").

## Why it's a good approach

1. **It measures the forecast's real error.** The range comes from how far this exact forecasting method has actually been off before. It doesn't rely on a theoretical formula, so anything the model systematically misses (data quirks, events it doesn't know about) is already part of the past errors.
2. **It works for any model.** LightGBM doesn't produce uncertainty on its own, and the monthly method has no statistical model at all. The same past-error approach gives both a range, built the same way, so they can be read the same way on screen.
3. **Each agency gets its own range.** Steady agencies get narrow ranges and volatile ones get wide ranges, without hand-tuning: DOHMH is about ±13%, DHS about −27% to +39%.
4. **It handles lopsided errors.** Surges are larger than dips, so the upper side can be wider than the lower side. A symmetric ±X% range would hide that.
5. **It uses only what was known at the time.** Only errors settled before the reference date are used, so on past dates the range never benefits from hindsight.
6. **It's easy to explain.** "8 out of 10 past weeks landed in this range" needs no statistics background, which suits an operations dashboard.
7. **It has been checked.** For the monthly method, the actual count fell inside the range 70–89% of the time across agencies, close to the 80% target.

## Where it falls short

- **It assumes the future will be off by about as much as the past.** If something changes, such as a new reporting system or an unusual year, the range lags behind.
- **Rare extremes are mostly ignored by design.** Snowstorms, for example, fall in the top 10% that gets cut off, which is why weather alerts widen the upper end separately.
- **The weekly range hasn't been checked on unseen data.** The 90% "below the upper bound" figure for weekly forecasts holds by construction on the same past errors. Weekly coverage on weeks the range wasn't built from hasn't been measured.
- **It doesn't adjust for period length.** Periods shorter than a week get the full-week range even though their error is larger, so the range is probably too narrow for them (see [sub_week_forecast_accuracy.md](sub_week_forecast_accuracy.md)).
