# Stock planning matrix — 12 November 2026

The user requested a quantified recommended stock range for each of 7, 14, 30 and 60 days. Each prediction now includes `stock_plan`; the same JSON is persisted in `ml_inventory_predictions` and displayed in Analytics → Stock through expandable per-product matrices.

For horizon H, use its own forecast F(H), not an automatic multiplication of the 30-day forecast. Let r = F(30)/30, L = known supplier lead time, S = 3 safety days, and R = the supplied next-order/review allowance (default 7 days).

- Recommended minimum = ceil(F(H) + r × (L + S)).
- Recommended maximum = ceil(F(H) + r × (L + S + R)).
- Add-to-range quantities compare both bounds with current on-hand stock, rounded up to whole units; surplus above maximum is rounded down.

These are transparent policy target bands, **not calibrated forecast intervals, fitted mathematical optima, or guarantees**. Buffer settings remain assumptions requiring validation. Unknown lead time produces a provisional range with zero delivery-time allowance and a visible warning; it does not silently claim confirmed zero-day delivery. Open orders are shown separately and not credited without an arrival date. Products younger than 28 days show Collecting data with no recommended bounds; unknown age is explicitly flagged. Dead/Slow overall labels trigger a replenishment-review warning rather than silently overriding that label.

Example: two units/day, ten on hand, confirmed zero delivery delay, three safety days, seven-day review allowance:

| Horizon | Forecast | Recommended stock | Add to reach range |
|---|---:|---:|---:|
| 7 days | 14 | 20–34 | 10–24 |
| 14 days | 28 | 34–48 | 24–38 |
| 30 days | 60 | 66–80 | 56–70 |
| 60 days | 120 | 126–140 | 116–130 |

The API computes these after prediction; no retraining or benchmark-score change is claimed. Historical archive plans retain their February snapshot date and separate source flag. `scripts/backfill_stock_plans.py` updates only archive matrix JSON, preserving labels and forecasts. Operational predictions use the normal atomic publication job. Existing predictions without a matrix show an explicit awaiting-refresh message.

Verified: 41 backend tests (including five new range tests), exact live API example, and all 6,135 stored prediction matrices. Longer horizons can share zero targets when forecast demand is zero; we do not force artificial differences. Matrix status (below/within/above range) is separate from the existing Dead/Slow/Low/New/etc. policy label.
