# Jiran 1,000-store simulation benchmark: evaluation protocol

Status: fixed on 11 Nov 2026 before any model was run on the simulated data.
Any later change must be listed under "Deviations" with its reason.

## Why a simulation

The live 3-store data cannot test forecasting or stock alerts:

- daily order counts behave like pure Poisson noise (variance/mean 0.96, lag-1 and
  lag-7 autocorrelation ~0), units per order are uniform on 1-8, and every product
  sells at almost the same rate. A forecast that knew each product's true mean still
  scores ~80% daily MAPE.
- there is one stock snapshot, so no stock outcome can be observed.
- the classifier's labels are produced by Jiran's own rule from its own inputs.

The simulation records daily stock, so alerts can be scored against what actually
happens next. All results from it are simulation evidence and must be labelled so.

## Data (generate.py, seed 20261111)

- 1,000 stores in 12 regions, 365 days (2025-01-01 to 2025-12-31).
- 600-product catalogue in the 10 live categories; each store carries 80-160 products.
- Daily demand = product base rate x store size x store-product affinity x
  category weekday profile x category yearly season and holidays x series trend x
  promotions x lifecycle (decline / late launch) x regional shock. Orders are
  gamma-Poisson (over-dispersed); units per order are 1 + negative binomial with
  rare bulk orders.
- Stores reorder with a periodic-review order-up-to policy using their own trailing
  28-day sales, store- and item-specific ordering bias, lead time of 2-6 days and
  case packs. Sales = min(demand, stock). Lost demand is never visible to models.
- Parameters were set from general retail properties (intermittent long tail,
  weekend peaks, promotions, product decline) before any model was run, and were not
  changed after seeing model results.

## Splits

- Stores: 800 training stores, 200 held-out test stores (random, seed 7).
- Alerts: snapshots every 14 days.
  - train: training stores, snapshot days 90-202 (labels end by day 262)
  - validation: training stores, snapshot day 216 (labels end day 276)
  - test: held-out stores, snapshot days 276, 290, 304 (labels from day 277 to 364)
  Test labels start after every training and validation label window ends.
- Forecasts: 3,000 series sampled at random from held-out stores (seed 11).
  Tuning origins day 244 and 274; test origins day 304 and 334; horizon 30 days.
  (Days are numbered 0-364; origin = last day of training history.)

## Targets (all from the future, never from inputs)

- shortage_14d: the item's stock reaches 0 on any of the next 14 days.
- excess_60d: stock on the snapshot day is more than the next 60 days of sales.
- dead_60d: stock > 0 on the snapshot day and no sale in the next 60 days.

Rows are store-items that have been launched and have had stock in the past 28 days.

## Methods

Alerts:
1. Jiran rule (inventory_policy.stock_policy_label; forecast = 28-day mean):
   Low -> shortage, Dead -> dead, Dead/Slow/Excess -> excess.
2. Days-of-cover threshold: one feature, threshold chosen on validation.
3. HistGradientBoosting, fixed settings (lr 0.05, 300 iterations, 31 leaves,
   early stopping on a 10% split of training rows), threshold chosen on validation
   to maximise F1.

Forecasts: Jiran selector (28-day window, current), previous selector (14-day),
Prophet, weekly naive, recent mean (28 days), Croston-SBA, forecast zero.

## Metrics

- Alerts: precision, recall, F1, PR-AUC, ROC-AUC (ML only), Brier score and
  reliability bins; 95% CIs by cluster bootstrap over test stores (1,000 resamples).
- Forecasts: MASE, RMSSE (M5 definition), WAPE (daily and 30-day total), bias,
  MAPE (requested; days with sales only, and 30-day total), all at 7/14/30 days and
  by demand class (Syntetos-Boylan ADI/CV2 on training history).

## Deviations

1. 11 Nov, before any results: all origins and snapshot days moved one day earlier.
   The first version let the last 30-day horizon and 60-day labels run past day 364.

## Additions after results (not part of the fixed plan; reported as such)

2. A perfect-knowledge forecast reference (the generator's true expected demand) was
   added to show the noise floor of each metric. It changes no other result.
3. An exploratory alert check retrained the ML model without open orders, lead time
   and review timing, to test whether its advantage over the rule depends on them.

### 12 Nov 2026 additions (designed after the 11 Nov results; reported as additions)

The settings below were fixed by reasoning, written into the code before each test
was first run, and were not changed after seeing its results.

4. **Lost sales** (`evaluate_lost_sales.py`). Same 3,000 test series and test origins.
   Each method runs on recorded sales and on sales with stock-out days replaced by
   the trailing in-stock mean (`forecasting.uncensor`, at least 7 in-stock days).
   Scored against future recorded sales *and* future true demand.
5. **Improved stock rule** (`inventory_policy.stock_policy_label_v2`), added as an
   alert method in `evaluate_alerts.py`: in-stock sales rate; "Low" = stock plus open
   orders will not last until the next supplier delivery + 3 safety days. Dead / Slow /
   Excess thresholds unchanged. Rows, targets and test stores unchanged. The same run
   reports how the current rule labels products under 28 days old (cold start).
6. **Transfers** (`evaluate_transfers.py`, paper RQ3). Paired replay of the year with
   identical demand, supplier policy and delivery delays; only the transfer policy
   differs. Weekly transfer rounds on days 182-357, arrival next morning, results on
   days 183-364. Arms: none, current engine, current + same-region only, improved
   (region + in-stock rate + delivery-based "Low", receiver target and donor reserve +
   new products excluded), and single-fix ablations. The current engine runs as
   shipped (`transfer_policy.plan_transfers`, the same code the API uses). Safety days
   = 3 and the 28-day new-product window were set by reasoning, not tuned.
   A first run on the 200 test stores was made before the 1,000-store run; nothing was
   changed between them.
7. **Repeat seeds** (`run_seeds.sh`). The full benchmark (generate, alerts, forecasts,
   lost sales, transfers) re-run on seeds 1-4 with every other setting unchanged, to
   report mean and spread across independently simulated worlds.
