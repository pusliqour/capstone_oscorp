# Jiran ML model card (12 Nov 2026)

The ML-side answer to concerns A1, A5, A6, A8 and A9 (see `/Users/zoro/MLP`, CONCERNS).
All evaluation numbers are **simulated** (1,000-store generator, `simulation/PROTOCOL.md`), not real-retailer results.

## A1 — Which component produces which output

| Component | Code | What it outputs | What it is evaluated on | Evidence file |
|---|---|---|---|---|
| Stock policy rule v1 (fixed thresholds) | `inventory_policy.stock_policy_label` | the stock label when no delivery time is known | future shortage / excess / dead outcomes | `simulation/output/results/alerts.json` → `jiran_rule` |
| Stock policy rule v2 (delivery-time Low test) | `inventory_policy.stock_policy_label_v2` | the stock label when `lead_time_days` is given | same targets | `alerts.json` → `jiran_rule_v2` |
| New-product gate | `inventory_policy.is_new_product` | label "New" for < 28 days on sale here | cold-start block | `alerts.json` → `cold_start_test`, `results/cold_start.json` |
| Policy-copying ensemble (live) | `app.py` (`ensemble`) | `model_prediction`, `confidence`, `probabilities` only — **never the label** | agreement with the rule (not outcomes) | training report; do not quote as outcome accuracy |
| Forecast selector | `forecasting.selected_forecast` | `demand_30d`, forecast horizons | WAPE / MASE / bias vs true demand | `results/forecasts.json` |
| Benchmark outcome model (offline only) | `simulation/evaluate_alerts.py` (HistGradientBoosting) | nothing in the app | future shortage / excess / dead outcomes | `alerts.json` → `ml_hgb`, `alerts_tuned.json` |
| Transfer engine (rule-based) | `transfer_policy.plan_transfers` | transfers and restocks | lost sales prevented, donor harm (paired replay) | `results/transfers.json` |
| Stock ranges (policy targets) | `stock_planning.stock_planning_matrix` | 7/14/30/60-day min–max targets | **not yet validated** (task MLP-001) | — |

Every API prediction now carries `decision_source` = `new_product_gate` | `stock_policy_v2_delivery` | `stock_policy_v1`
and `model_agrees` (does the ensemble reproduce the label). Tested in `tests/test_edge_guards.py::Attribution`.
Transfer gains come from the rule-based engine, not from any ML model.

## A5 — What is and is not validated

Validated in simulation: forecast accuracy, lost-sales correction, alert rules vs a benchmark ML model, rule-based transfers, cold-start gate, 5 repeated worlds.
Implemented but not validated: the stock-range matrix (MLP-001); using ML risk to change stock decisions (MLP-002).
Not validated at all: real-retailer performance, user studies, any domain other than retail inventory.

## A6 — Is the benchmark ML model's advantage fair? (`simulation/evaluate_tuning.py`)

Both sides are now tuned on the validation snapshot only (day 216, non-test stores); results on the 200 test stores (days 276–304).
See `simulation/output/results/alerts_tuned.json`. 
| Target (test F1, 95% store-clustered CI) | Rule as shipped | Rule, thresholds tuned on validation | ML as before | ML, tuned on validation (25 settings) |
|---|---|---|---|---|
| Stock-out within 14 days | 0.668 | 0.673 [0.648, 0.693] | 0.738 | 0.739 [0.720, 0.755] |
| Excess over 60 days | 0.656 | 0.683 [0.671, 0.694] | 0.730 | 0.735 [0.724, 0.744] |
| Dead (no sale) over 60 days | 0.328 | 0.427 [0.404, 0.450] | 0.446 | 0.397 [0.370, 0.424] |

What this means:
- Stock-outs and excess: the ML lead (+0.07 and +0.05 F1) survives fair tuning of both sides. It is not an artefact of a weak baseline or an unlucky ML setting; ML tuning changes it by < 0.01.
- Dead stock: the earlier gap (ML 0.45 vs rule 0.33) was mostly the rule's 90-day no-sale threshold. With a validation-chosen threshold the rule (0.43) is level with the ML model, so "ML is better at dead stock" must **not** be claimed.
- Tuning can also hurt: the setting with the best validation PR-AUC for dead stock scored worse on test (0.397). Validation is a single snapshot with a rare target (1.8% of rows), so selection is noisy. Reported, not hidden.
- The rule labels in the app use rule v1/v2 as shipped; this benchmark model is not used live (see A1).

## A8 — Where every threshold comes from

| Threshold | Value | Source | Validation-set sensitivity (main world) |
|---|---|---|---|
| Dead: coverage > 8, days of stock > 180, no sale > 90 days | 8 / 180 / 90 | inherited from the original rule (hand-set) | no-sale 90 → **30** days chosen in **6/6** worlds; dead F1 0.30–0.35 → 0.41–0.45 (main 0.328 → 0.427). Coverage 8 vs 10: mixed (3 vs 3) |
| Slow: coverage > 4, days of stock > 120 | 4 / 120 | inherited (hand-set) | 4 → **2.5** chosen in **6/6** worlds; excess F1 +0.03 every world (main 0.656 → 0.683) |
| Low (v2): cover < days until delivery + SAFETY_DAYS | 3 days | reasoned | 3 kept in 4/6 worlds; 5 in the other 2 with < 0.01 F1 difference → **3 is justified** |
| New product: MIN_HISTORY_DAYS | 28 days | four weekly cycles; cold-start study (`results/cold_start.json`) | not swept |
| Donor reserve: DONOR_RESERVE_MULT | ×2 | chosen on development world seed 1001 (not test) | `results/dev1001_transfers.json` |
| Forecast max age: JIRAN_FORECAST_MAX_AGE_DAYS | 7 days | one weekly cycle | not swept |
| Stock ranges: safety / review allowance | 3 / 7 days | assumption; review = `order_cycle_days` (C1 fix) | MLP-001 |

The live defaults are unchanged. Sweep: `simulation/evaluate_tuning.py` (A8 block), selected on the validation snapshot only, reported on test.
Worlds: main (seed 20261111), development 1001, seeds 1–4 (`output/results/seeds/*_alerts_tuned_rules.json`).
The vectorised rule used for the sweep reproduces the shipped rule exactly (agreement 1.000 in every world).

**Decision: live defaults NOT changed yet.** Two consistent improvements were found (Slow 2.5, Dead after 30 days without a sale),
but (1) both values sit at the edge of the grid, so the best value may lie further out; (2) they move the rule toward the
target definitions themselves (excess = stock > next 60 days' sales ≈ coverage > 2; dead = no sale in 60 days), so part of
the gain is definitional; (3) more Dead/Slow labels mean more donor stock in transfers, which must be re-checked in the
paired transfer replay before going live.

**Task P1 — transfer replay with the tuned thresholds (done 12 Nov).** `evaluate_transfers.py` arms `improved+slow2.5`,
`improved+dead30`, `improved+slow2.5+dead30`; development world 1001 first, then the main world (same direction in both):

| Arm (main world) | Lost sales prevented | Giver stock-outs caused | Stores worse off | Dead stock cleared |
|---|---|---|---|---|
| Improved engine (live) | 8.3% | 9.8% | 227 | 71% |
| + Slow 2.5 | 8.2% | 10.9% | 252 | 78% |
| + Dead after 30 days | 7.8% | 12.7% | 291 | 80% |
| + both | 7.8% | 13.0% | 297 | 83% |

The thresholds that give better *alerts* make more stock count as spare, so transfers clear more dead stock but prevent
slightly fewer lost sales and cause more stock-outs at the giving store. This is a trade-off, not an improvement.
**Decision: keep the live thresholds** (they protect sales and givers). Switching is an owner choice (service level vs
dead-stock clearing); the evidence and arms are in place to switch. Results: `output/results/transfers_p1.json`,
`dev1001_transfers_p1.json`; chart `docs/mlp/figures/fig_p1_transfers.png`.

## A11 — Readable figures

`simulation/make_figures.py` draws the ML evidence from the results JSON (no re-runs): horizontal bars, value printed on
every bar, 95% store-clustered whiskers, one axis per chart, colour-blind-safe order, legend always shown, 300 dpi PNG + SVG.
Copies in `docs/mlp/figures/`: `fig_a6_fair_tuning`, `fig_a8_dead_60d_stability`, `fig_a8_excess_60d_stability`, `fig_p1_transfers`.

## A9 — Definitions and divide-by-zero guards

| Symbol | Definition | Guard |
|---|---|---|
| demand_30d | 30-day forecast; if ≤ 0, `max(recent_qty, 1)` | never 0 |
| demand_7d | 7-day forecast; if ≤ 0, `max(recent_qty / 4, 1)` | never 0 |
| coverage | stock / (demand_30d + 1) | +1 unit |
| days of stock | stock / (demand_30d / 30 + 0.1) | +0.1 units/day |
| forecast acceleration | (f7 / 7) / (f30 / 30 + 0.1) | +0.1 |
| in-stock rate | sold / max(in-stock days, min(7, days), 1) | ≥ 1 day; 7-day floor when mostly out of stock |
| runs out before delivery | (stock + on order) / rate < days until delivery + SAFETY_DAYS | rate ≤ 0 → never Low by this test |
| receiver target / donor reserve | rate × days (− on order) | clipped at 0 |
| transfer coverage after | stock / (demand_30d + 0.1) | +0.1 |

All of these are exercised at zero stock, zero sales, zero days and empty history in `tests/test_edge_guards.py`.
