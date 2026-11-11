# Jiran ML: full breakdown (12 Nov 2026)

Written for reading aloud and for working through step by step (e.g. with Codex voice mode).
Every claim points to a file and function so you can open it and check.
All numbers come from **simulated** stores, not real retailers.

---

## 0. The one-minute version

1. Jiran does three smart things: **forecasts** how much each store will sell, **labels** stock (Low / Optimum / Excess / Slow / Dead / New), and **suggests transfers** between stores.
2. We cannot get real data, so we built a **fake but realistic network of 1,000 stores** where we can see everything, including the customers who left because the shelf was empty.
3. We tested all three things fairly. Models learn on 800 stores and are tested on 200 other stores, at later dates. Answers are checked against what actually happened next.
4. We found problems, fixed six of them in the code, and tested the fixes:
   - transfers now prevent about **2× more lost sales** while moving **55% fewer units**, and hurt the giving store **less**;
   - the "Low" warning is now **right 71% of the time instead of 45%**;
   - forecasts no longer **ignore customers lost to empty shelves**;
   - **brand-new products** are held as "New" for 28 days instead of getting wrong labels;
   - forecasts in the live app are **no longer frozen**;
   - **repeat runs** on other simulated worlds give the same picture.
5. Not done yet: user studies, real data, and updating the paper text.

---

## 1. Where everything lives

| What | File |
|---|---|
| Stock labels (the rule) | `ml_backend/inventory_policy.py` |
| Transfer engine | `ml_backend/transfer_policy.py` (new, moved out of `app.py`) |
| Forecasting | `ml_backend/forecasting.py` |
| Live API | `ml_backend/app.py` (port 8001) |
| Supabase → API bridge | `ml_backend/supabase_watcher.py` |
| Training of live models | `ml_backend/train.py`, `ml_backend/augmentation.py` |
| Dashboard | `frontend/src/pages/Analytics.jsx` |
| Simulation + tests | `ml_backend/simulation/` |
| Test plan | `ml_backend/simulation/PROTOCOL.md` |
| Results (JSON) | `ml_backend/simulation/output/results/` |
| Unit tests | `ml_backend/tests/test_policy_additions.py`, `ml_backend/tests/test_forecast_refresh.py` (+ older ones; 36 pass) |
| Paper | `paper/jiran_isdia_2027.tex` |
| Visual report | `~/Desktop/Jiran-ML-Evaluation/` and the claude.ai artifact |

Run tests: `cd ml_backend && ../.venv/bin/python -m unittest discover -s tests`

---

## 2. The "models": what each one actually is

This is the most important thing to get right in the paper (reviewer point: "results credited to different models").

| Name | Where | What it does | Is it what users see? |
|---|---|---|---|
| **Stock rule** | `inventory_policy.stock_policy_label()` and the new `stock_policy_label_v2()` | Fixed if/then thresholds that turn stock and demand into a label | **Yes.** Every label in the app comes from this. |
| **Live ensemble** (RF + GB + XGB) | `ml_backend/saved_models/ensemble.pkl`, trained by `train.py` | Learns to copy the rule; gives a **confidence** number | No. Only the `confidence` field. Its high score (F1 0.989) measures copying the rule, not real accuracy. |
| **Forecast selector** | `forecasting.selected_forecast()` | Per store-product, tries weekly-naive, 28-day mean and Prophet; keeps the one that did best on the last 28 days | Yes, feeds the rule's demand |
| **Benchmark ML model** (HistGradientBoosting) | `simulation/evaluate_alerts.py` | Predicts real outcomes (stock-out, excess, dead) | **No. It exists only in the benchmark.** |
| **Transfer engine** | `transfer_policy.plan_transfers()` | Matches stores with too much to stores running low | Yes, `/recommend` endpoint |

---

## 3. How stock gets labelled (and why it is per store)

`inventory_policy.policy_metrics()` computes:
- `coverage_30d_feat` = stock ÷ (30-day demand + 1)
- `days_of_stock_30d_feat` = stock ÷ (daily demand + 0.1). The +0.1 avoids dividing by zero.
- `stockout_risk_7d` = stock below 7-day demand

`stock_policy_label()` applies, in this order:
- **Dead**: coverage > 8, or > 180 days of stock, or no sale for 90+ days
- **Slow**: coverage > 4, or > 120 days of stock
- **Low**: coverage < 0.6, or < 14 days of stock, or the 7-day risk
- **Excess**: coverage 2–4 and still selling
- otherwise **Optimum**

Because demand is **that store's own** sales rate, the same 100 units can be Low in a busy store and Dead in a quiet one.
Real example from the simulation, same frozen product on the same day: store 952 had 90 units and sold 36/day (2 days of stock → Low); store 185 had 96 units and sold almost nothing (707 days → Dead).

These thresholds came from the capstone and were **never tuned**. Say that in the paper.

---

## 4. The simulation (why we trust the tests)

File: `simulation/generate.py`, seed `20261111`. It runs in 8 seconds and produces about 850 MB.

- 1,000 stores, 12 regions, 600 products, 119,834 store-products, 365 days.
- Demand includes store size, weekday, season, holidays, promotions, trends, products dying off, late launches and regional shocks (`demand_rate()`).
- Customers arrive randomly with uneven basket sizes (`draw_demand()`).
- Each store reorders weekly from a supplier, with a 2–6-day delivery time and its own over/under-ordering habit (`simulate_inventory()`).
- **Sales = min(demand, stock).** 11.8% of demand is lost to empty shelves. The file `demand.npy` records it, but no model ever sees it.
- `--seed N` makes a different world (used for repeat runs).

Why not the 3-store spreadsheet data? Its origin is unconfirmed, it has one stock snapshot, and its daily sales are statistically pure noise (variance/mean 0.96, no weekly pattern).

**Fair-test rules** (written before running, in `PROTOCOL.md`):
- Train on 800 stores, test on 200 different ones (`stores.sample(200, random_state=7)`).
- Test dates come after all training dates.
- Alerts are graded on what really happened next, not on the rule's own label.
- Thresholds are picked on a validation period, never on test data.
- Uncertainty is measured by resampling whole test stores (`cluster_ci()` in `evaluate_alerts.py`).

---

## 5. Results and fixes, one by one

### 5.1 Forecasting: `simulation/evaluate_forecasts.py` → `results/forecasts.json`

3,000 test series, test start days 304 and 334, 30-day horizon.

| Method | 30-day error (WAPE) |
|---|---|
| Jiran selector | 27.8% |
| 28-day mean | **24.0%** |
| Prophet | 27.5% |
| Perfect knowledge (`oracle_reference.py`) | 24.5% |

- WAPE 28% means: for every 100 units sold in a month, the forecast's total is off by about 28.
- Even perfect knowledge of expected demand scores 24.5%, so most of the error is customer randomness.
- **The simple 28-day mean beats the selector.** The paper must say so honestly.
- Daily MAPE is about 77% for every method, even perfect knowledge (71%). When an item sells 1–3 a day, missing by 1 is a 33–100% error, so MAPE cannot separate good from bad forecasts here.
- MASE rates "always forecast zero" as good, so lead with WAPE and RMSSE instead.

### 5.2 FIX 1: lost sales hidden by empty shelves

**Problem:** on an empty-shelf day, sales show 0 even though customers wanted the item, so forecasts learn too low a demand.

**Code:**
- `forecasting.uncensor(values, stock)`: on days ending with stock 0, replace sales with the average of the in-stock days in the last 28 (needs at least 7 in-stock days).
- `inventory_policy.in_stock_rate(units, days, stockout_days)`: units ÷ in-stock days (at least 7).
- API inputs: `daily_stock` or `stockout_days_30d` on `ProductInput` in `app.py`.

**Test:** `simulation/evaluate_lost_sales.py` → `results/lost_sales.json`. The fix is scored against **true demand**, which only a simulation knows.

| | Under-forecast of true demand |
|---|---|
| All series, before | −21% |
| All series, after | **−13%** |
| Items that recently ran out, before | −35% |
| Items that recently ran out, after | **−17%** |

Catch: scored against recorded sales, the fix looks worse, because future sales are cut short too. Stock decisions need demand, so the fix is right.
**To use it live:** Jiran must record daily stock levels or stock-out days.

### 5.3 Stock alerts: `simulation/evaluate_alerts.py` → `results/alerts.json`

71,598 test rows, 200 held-out stores, days 276/290/304. F1 balances "caught the problem" against "few false alarms" (1.0 is perfect).

| Shortage in 14 days | Precision | Recall | F1 |
|---|---|---|---|
| Current rule | 0.45 | 0.89 | 0.60 |
| **Improved rule (FIX 2)** | **0.71** | 0.63 | **0.67** |
| Days-of-cover threshold | 0.62 | 0.71 | 0.66 |
| ML model | 0.75 | 0.73 | **0.74** |

- The current rule calls 55% of items "Low", so it cries wolf: only 45 of 100 warnings are right.
- Excess: rule 0.66, ML 0.73. Dead stock: rule 0.33, ML 0.45. Dead stock is rare (2.7%) and hard for everyone.

### 5.4 FIX 2: delivery time ("apply your logic")

**Idea:** "Low" should mean *it will run out before the next delivery can arrive*, not "under 14 days".

**Code:**
- `inventory_policy.runs_out_before_delivery()`: (stock + on order) ÷ daily rate < days until delivery + 3 safety days.
- `days_until_next_delivery(lead_time, days_to_next_order)`.
- `stock_policy_label_v2()` uses it when `lead_time_days` is supplied. Dead and Slow thresholds are unchanged.
- API inputs: `lead_time_days`, `days_to_next_order` (default 7), `on_order`.

**Result:** F1 0.60 → 0.67, warnings right 45% → 71% (table above). No training needed.

### 5.5 FIX 3: new products (cold start)

**Your rule:** a brand-new product waits and collects its own data. No borrowing from other stores.

**Code:**
- `inventory_policy.MIN_HISTORY_DAYS = 28` and `is_new_product(age_days)`.
- `stock_policy_label_v2()` returns **"New"** when `age_days < 28`.
- "New" items are never donors or receivers in `transfer_policy.plan_transfers()`, because only Low/Excess/Slow/Dead take part.
- API input: `age_days`.
- Dashboard: a "New" tile and tab in `frontend/src/pages/Analytics.jsx`.

**Test:** `simulation/evaluate_cold_start.py` → `results/cold_start.json`. It covers 7,148 launched products.
- In week 2, the old rule estimates demand at 5% of the truth, because the 28-day average counts pre-launch days as zero.
- It labels 30% of week-2 products Dead/Slow, but only 0.2% of those really went unsold. These labels are almost all wrong.
- By days 28–41 the estimate reaches 74% (the rest is lost sales).

### 5.6 Transfers: `simulation/evaluate_transfers.py` → `results/transfers.json`

**How the test works:** replay the second half of the year for all 1,000 stores. Every arm has the **same customers**, supplier orders and delivery delays; only the transfer policy changes. So any difference is caused by the transfers.
- Transfer rounds weekly from day 182; stock arrives the next morning.
- Functions: `simulate()` (the replay), `transfer_round()` (labels plus engine call), `summarise()` (metrics).
- `rule_labels_vec()` is a fast copy of the rule, checked against the real one by `check_rule()` on 20,000 random cases.

**Engine:** `transfer_policy.plan_transfers()`:
- receivers = Low;
- donors = Excess (then Dead, then Slow);
- one donor if possible, otherwise several ("combined");
- leftover need becomes a restock suggestion.

| Policy | Lost sales prevented | Prevented per 100 units moved | Giving store gets a new stock-out | Transfer not needed | Stores worse off |
|---|---|---|---|---|---|
| Current engine (as shipped) | 4.6% | 17 | 17.1% | 63% | 595 / 1000 |
| Current + same region | 5.6% | 24 | 17.6% | 59% | 421 |
| **Improved (final)** | **8.3%** | **67** | **9.8%** | **43%** | **227** |

Trade-off: the shipped engine clears more dead stock by year end (−90% vs −71%), because it sends stock to many stores that do not need it.

### 5.7 FIX 4: transfer improvements

All of these are in code, and the API uses them when the inputs are given:
1. **Neighbours only:** a `group` key in `plan_transfers()`; the API passes `ProductInput.region`.
2. **Receive only real need, sized to the next delivery:** `inventory_policy.receiver_target_stock()`, set as `target_stock` in `app._compute_recommendations()`.
3. **Protect the giver:** `inventory_policy.donor_reserve()` with `DONOR_RESERVE_MULT = 2.0`, set as `keep_stock`.
   - The ×2 was chosen on a **separate development world (seed 1001)**, never on the reported worlds: `results/dev1001_transfers.json`.
   - With ×1, 14% of donations hurt the giver; with ×2, 10%.
   - "No Excess donors" halved the benefit, so it was rejected.
4. **In-stock sales rate** (FIX 1).
5. **New products excluded** (FIX 3).
6. **Two bugs fixed:** a donor with less than 1 spare unit was still asked for 1; the receiver's stock was double-counted after a single-donor transfer.

Single-fix rows show that **sizing by the next delivery** gives most of the gain (8.1% alone).

### 5.8 FIX 5: unfrozen forecasts

**Problem:** `app.py` used the forecasts saved at training time (`saved_models/forecasts_aggregated.csv`) forever.

**Now** `app.get_forecast_features(p)` works in this order:
1. If the request has `daily_sales` (56+ days), it makes a fresh forecast on the spot with `selected_forecast(..., methods=("weekly_naive","recent_mean"))`, after `uncensor()`.
2. Otherwise it uses the saved forecast only if it is at most `FORECAST_MAX_AGE_DAYS` = 7 days old (env `JIRAN_FORECAST_MAX_AGE_DAYS`). `train.py` now writes `generated_at`; `_forecast_age_days()` reads it, or the file date.
3. Otherwise it uses `live_daily_rate(p)`: the request's 30-day sales ÷ in-stock days.

Tested in `tests/test_forecast_refresh.py`. To use step 1 live, the Supabase view must send `daily_sales` / `daily_stock`; `supabase_watcher.build_api_payload()` already passes them through.

### 5.9 FIX 6: no real data (what we do instead)

- Present the work as a **simulation study**, clearly labelled.
- Publish the generator, seed and checksums (`manifest.json`) so anyone can rebuild the data.
- **Repeat on several worlds:** `simulation/run_seeds.sh` ran everything on seeds 1–4 → `results/seeds/`. With the main world, that is **5 independent worlds**:

| Result (mean ± SD over 5 worlds) | Current | Improved / ML |
|---|---|---|
| Transfers: lost sales prevented | 5.0% ± 0.3% | **9.1% ± 0.7%** |
| Transfers: prevented per 100 units moved | 19 ± 2 | **72 ± 3** |
| Transfers: donations causing a giver stock-out | 16.6% ± 0.3% | **9.6% ± 0.3%** |
| Shortage alert F1 | 0.59 ± 0.02 | 0.67 ± 0.01 (improved rule), 0.74 ± 0.01 (ML) |
| Excess alert F1 | 0.65 ± 0.01 | 0.74 ± 0.01 (ML) |
| Dead-stock alert F1 | 0.33 ± 0.01 | 0.46 ± 0.02 (ML) |
| 30-day forecast WAPE | 27.0% ± 1.0% (selector) | 23.6% ± 0.4% (28-day mean) |
| Under-forecast of true demand | 20.6% ± 2.2% (as recorded) | 13.1% ± 2.0% (corrected) |

  In **all 5 worlds** the improved engine beats the shipped one on all three transfer measures, and the alert ranking is the same: current rule < improved rule < ML.
- List what the simulation leaves out: transport cost, owners refusing transfers, substitute products, expiry, supplier stock-outs.

---

## 6. Your friend's reviewer feedback, applied to our paper

### 6.1 What happened with your friend's paper

Your friend's paper is **FATIS**, a traffic system. It does three things:
- predicts **queue spillback** at an intersection (when a queue backs up into the previous junction), using XGBoost or TabPFN;
- classifies the **cause of congestion** into 3 classes (TabPFN, trained on 1,098 incident records);
- tests a controller in the **SUMO** traffic simulator.

A reviewer sent detailed comments (the uploaded file `Friends_feedback.md`). The main problems they found:

1. **The same results were credited to two different models.** Section III-A and the Conclusion said XGBoost produced the 82.3% spillback reduction, 26.47% throughput gain and 59.33% speed gain. Section IV and Table II gave the same numbers to TabPFN and much smaller ones to XGBoost (17%, 10%, 13%).
2. **Possible data leak.** Classes were balanced to 200 samples each *before* the 20% test split. Duplicated rows could then appear in both training and test, which inflates the 84.17% accuracy.
3. **Test set too small.** With 120 test samples, 84% accuracy is only known to about ±7 points. Also, the confidence gate *lowered* accuracy (84.17% → 83.76%) and the paper didn't say so.
4. **Thin simulation.** One intersection, no repeated runs, no seeds and no variance, yet the paper said the method "consistently outperformed". An average wait of 116 minutes looked like a unit error.
5. **Scope mismatch.** The introduction promised a three-intersection corridor with several agent types and five cause classes. What was built was one intersection, one agent type and three classes. "Federated" was never explained.
6. **Unsupported explanation.** The paper said XGBoost was "memorising noise", with no evidence. It was also run with default settings, so the comparison may have been unfair.
7. **Smaller issues:**
   - no related work on the paper's actual contributions;
   - thresholds (0.80, 15 s, 0.55) not justified, and maybe tuned on test data;
   - undefined symbols and a possible divide-by-zero;
   - an arithmetic slip (0.04% written as 0.02%);
   - unreadable figures;
   - template placeholders left in, a broken citation "[?]", typos, and informal words like "humble".

**Why this matters to us:** Jiran had or could have had most of these problems, so we checked every one. The table below shows each concern rewritten as a general rule and what we found in Jiran. Traffic-specific points were left out.

### 6.2 Each concern checked against Jiran

| Reviewer concern | Status | What to do |
|---|---|---|
| Same result credited to different models | **Paper** | Add the table from section 2. The draft still says the AI returns HTTP 503 and accuracy is "intentionally unreported". Update the abstract, Table 1, Current Results and Conclusion. |
| Resampling before the train/test split (leak) | OK | Checked: `train.py` splits first (`GroupShuffleSplit`), and `augmentation.PolicyAugmentedClassifier.fit()` adds synthetic rows to training only. Say so in one sentence. |
| Test set too small | Done | 71,598 test rows, 200 stores, store-level 95% intervals, several worlds. Never use the 3-store data as evidence. |
| One simulation run, no variance | Done | Seeds plus mean ± SD. Give the time window for every number. |
| Abstract promises more than was built | **Paper** | RQ2 and RQ3 are answered in simulation. RQ1 and RQ4 (user studies) and "general resource allocation" go to future work. |
| Unsupported "why it failed" claims | **Paper** | Use only explanations backed by data (e.g. the rule labels 55% Low). Say the ML model used fixed, untuned settings. |
| Missing related work | **Paper** | Add lateral transshipment (Paterson et al. 2011), lost-sales demand (Nahmias 1994), Croston 1972, Hyndman & Koehler 2006, M5 (Makridakis et al. 2022), Prophet (Taylor & Letham 2018). **Check each DOI.** |
| Thresholds unjustified / tuned on test | **Paper** | Rule thresholds come from the capstone. 28 days and 3 safety days were set by reasoning. ×2 was chosen on the dev seed. ML thresholds were chosen on validation. |
| Symbols, units, divide by zero | **Paper** | Define cover = stock ÷ (rate + 0.1), in-stock rate = units ÷ max(days, 7), and the units. |
| Arithmetic mistakes | Done | All report numbers come from scripts. Keep "% change" and "percentage points" separate. |
| Unreadable figures | **Paper** | Use horizontal bars with labels of at least 8 pt; PNGs are 2×. |
| Placeholders, typos, informal words | **Paper** | The acknowledgements still contain "must be confirmed by all contributors". Add keywords and a corresponding-author e-mail. |

---

## 7. GRC status (synced 12 Nov)

13 tasks: **9 done, 1 cancelled, 3 open.**

| Task | Status | What is left |
|---|---|---|
| T8 Stable team hosting, startup, backups | **cancelled** (shown as "blocked" because GRC has no cancelled status) | Not going to be done. The app stays on the Mac with a temporary tunnel, so the paper must not claim stable hosting. |
| T9 Confirm source provenance and team dataset | todo | Origin of the 3-store Excel data is still unconfirmed |
| T11 Remaining UX and optional connector gaps | todo | Square/Apideck path not reactivated; lint debt |
| **T12 Independent evaluation and paper evidence** | todo → **doing** | This work. Left to do: finish the seeds, update the paper text (section 6), and plan the user study (RQ1/RQ4) |

Done: T1–T7, T10, T13.

---

## 8. Your to-do list, in order

1. Read section 2 until you can explain "rule vs ensemble vs benchmark ML" without notes.
2. Fix the paper text using section 6, one row at a time. Start with the abstract and Current Results.
3. Add the related-work references and check each DOI.
4. Restart the public tunnel and redeploy Pages (section 9, "Not done").
5. Enter a region and supplier delivery time for each store, so the delivery-based "Low" and neighbour-only transfers switch on (the columns now exist).
6. Start recording daily stock so the lost-sales fix works live.
7. Later: a small user study (RQ1/RQ4). Hosting (T8) is cancelled.

---

## 9. Going live (12 Nov 2026): what was done, what is left

### Done
1. **Database:** new migration `supabase/migrations/202611120001_ml_inventory_policy_inputs.sql`.
   - Adds nullable columns to `public.ml_inventory`: `region`, `age_days`, `stockout_days_30d`, `on_order`, `lead_time_days`, `days_to_next_order`.
   - Updates `public.replace_ml_inventory()` to accept them.
   - Applied to the local Supabase with `npx supabase migration up --local`.
2. **Importer:** `ml_backend/import_jiran_ml_real_data.py` → `build_ml_inventory()` now fills `age_days` = days since the product's first sale in that store.
   - This is a lower bound: the product may have been stocked before it first sold.
   - The other new columns stay **empty (null)**, because the 3-store exports have no region, delivery time, open orders or daily stock history. Inventing them would be fabrication.
   - Re-ran it with `--push`: 175 rows reloaded.
3. **What that means today:** every product is 43–181 days old, so none is "New" yet; the label will appear when a product is added.
   - With region, delivery time and stock-out days empty, the API uses the old behaviour for those parts.
   - Live now regardless: forecast refresh (no saved forecast older than 7 days), the two transfer bug fixes, and the "New" logic.
4. **ML API** (port 8001) restarted with the new code. End-to-end check: Supabase → `supabase_watcher.fetch_inventory()` → `build_api_payload()` → `/recommend` returned 175 predictions (Dead 70, Slow 35, Excess 33, Optimum 26, Low 11), 2 transfers and 10 restocks.
5. **Git:** source committed and pushed to `fork` (pusliqour/capstone_oscorp), branch `recovery/jiran-archive-20261110`. Simulation data (`ml_backend/simulation/output/`) is git-ignored and can be rebuilt with `generate.py`.

### Not done: needs you
1. **The public website's backend is offline.** The Cloudflare quick tunnel (`navy-genre-bind-fleece.trycloudflare.com`) has stopped, so https://pusliqour.github.io/jiran/ cannot reach the Mac. Claude was not allowed to open a public tunnel itself (safety rule). To restore it, follow `docs/TEAM_DEMO.md` "Restart instructions":
   - `cloudflared tunnel --url http://127.0.0.1:8787 --no-autoupdate --protocol http2` (the gateway on 8787 is already running);
   - copy the new `https://….trycloudflare.com` address;
   - `JIRAN_PUBLIC_SUPABASE_URL=<that address> JIRAN_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_jiran_team_gateway VITE_TEAM_DEMO=true bash scripts/build-pages.sh`;
   - copy `frontend/dist/` into `Deployment/pages/` (keep its `.git`), then commit and push there. This also publishes the new "New" tile.
2. **Fill the new columns with real values** when you have them, e.g. a `region` per store and a supplier `lead_time_days` per store. Even typing those in for the 3 stores turns on the delivery-based "Low" and neighbour-only transfers.
3. **Record daily stock** (or count stock-out days) so the lost-sales fix can work live.

---

## 10. Glossary

- **WAPE:** total forecast error ÷ total actual sales. 28% means off by 28 units per 100 sold.
- **MAPE:** average daily percentage error. Misleading for slow sellers.
- **Precision:** of the warnings given, how many were right.
- **Recall:** of the real problems, how many got a warning.
- **F1:** one number balancing precision and recall (1.0 is perfect).
- **Fill rate:** share of customer demand actually sold.
- **Lost sales:** customers who wanted the item when the shelf was empty.
- **Cold start:** a new product with no history.
- **Paired replay:** re-running the same year with the same customers, changing only one policy.
- **Seed:** the number that fixes the simulation's randomness; a different seed is a different world.
- **Held-out stores:** stores the model never saw during training.
