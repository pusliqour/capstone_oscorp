# Jiran ML: full breakdown (12 Nov 2026)

Written for reading aloud and for working through step by step (e.g. with Codex voice mode).
New to this? Read sections 0–2, then do the **study sessions in section 10**: each has commands to run and functions to look at.
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
5. **Git:** source committed (`b69d945`) and pushed to `fork` (pusliqour/capstone_oscorp), branch `recovery/jiran-archive-20261110`. Simulation data (`ml_backend/simulation/output/`) is git-ignored and can be rebuilt with `generate.py`.

### Not done: needs you
1. **The public website's backend is offline.** The Cloudflare quick tunnel (`navy-genre-bind-fleece.trycloudflare.com`) has stopped, so https://pusliqour.github.io/jiran/ cannot reach the Mac. Claude was not allowed to open a public tunnel itself (safety rule). To restore it, follow `docs/TEAM_DEMO.md` "Restart instructions":
   - `cloudflared tunnel --url http://127.0.0.1:8787 --no-autoupdate --protocol http2` (the gateway on 8787 is already running);
   - copy the new `https://….trycloudflare.com` address;
   - `JIRAN_PUBLIC_SUPABASE_URL=<that address> JIRAN_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_jiran_team_gateway VITE_TEAM_DEMO=true bash scripts/build-pages.sh`;
   - copy `frontend/dist/` into `Deployment/pages/` (keep its `.git`), then commit and push there. This also publishes the new "New" tile.
2. **Fill the new columns with real values** when you have them, e.g. a `region` per store and a supplier `lead_time_days` per store. Even typing those in for the 3 stores turns on the delivery-based "Low" and neighbour-only transfers.
3. **Record daily stock** (or count stock-out days) so the lost-sales fix can work live.

---

## 10. Study sessions (one topic at a time)

Work through these in order, one per sitting. Each session has: the goal, the files, the functions (what each takes and returns), commands to run (copy exactly), what you should see, and questions to ask Codex.
All commands assume you start in `/Users/zoro/Projects/Jiran` unless a `cd` is shown. Python is always `.venv/bin/python` (or `../.venv/bin/python` from inside `ml_backend`).

---

### Session 1: What is running and how to start it

**Goal:** know every moving part and its port.

| Part | Port | Start command |
|---|---|---|
| Supabase (database, login, API) in Docker | 54321 (API), 54322 (Postgres) | `bash scripts/run-local.sh` (also applies migrations) |
| ML API | 8001 | `cd ml_backend && ../.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8001 --env-file .env` |
| Research (archive lab) API | 8003 | `ARCHIVE_LAB_DIR="$PWD/Private/recovery/20261110/lab" .venv/bin/uvicorn archive_lab_api:app --app-dir ml_backend --host 127.0.0.1 --port 8003 --no-access-log` |
| Team gateway (what the public site talks to) | 8787 | `.venv/bin/uvicorn scripts.team_gateway:app --host 127.0.0.1 --port 8787` |
| Frontend (local dev) | 5173 | `npm --prefix frontend run dev` |
| Public tunnel | – | `cloudflared tunnel --url http://127.0.0.1:8787 --no-autoupdate --protocol http2` |

**Check commands:**
- `curl -s localhost:8001/` → `"ai_available":true`, model name, 41 features, labels list.
- `docker ps --format '{{.Names}}'` → containers named `supabase_*_ISDIA`.
- `lsof -iTCP -sTCP:LISTEN -P | grep -E "8001|8003|8787|5173"` → which ports are listening.
- Restart the ML API after any code change: `kill $(lsof -ti tcp:8001 -sTCP:LISTEN)`, then the start command above.

**Ask Codex:** "Explain what each of these services does and what breaks if one stops."

---

### Session 2: The data flow, from database to dashboard

**Goal:** follow one product from the database to the label on screen.

1. Table `public.ml_inventory` holds one row per store and product: stock, recent sales and so on.
   - Created in `supabase/migrations/202610300001_jiran_ml_inventory_bridge.sql`.
   - New columns added in `202611120001_ml_inventory_policy_inputs.sql`.
2. It is filled by `ml_backend/import_jiran_ml_real_data.py`:
   - `build_ml_inventory(transactions, stock, products)` turns raw orders into 30-day and older totals, `days_since_last_sale` and the new `age_days`.
   - `push_inventory(inventory)` sends the rows to Supabase through the `replace_ml_inventory` database function.
3. The watcher `ml_backend/supabase_watcher.py`:
   - `poll()` waits for a row in table `ml_triggers`;
   - `process_trigger(trigger)` runs the job: `fetch_inventory()` reads `ml_inventory`, `build_api_payload(rows)` makes the JSON (optional fields only when present), then it POSTs to `/recommend` or `/predict-stock`;
   - the results are published back to Supabase for the dashboard.
4. The API `ml_backend/app.py`:
   - `recommend(req)` → `_run_predictions(products)` → `build_feature_row(p)` per product → `stock_policy_label_v2(row)` gives the label;
   - the ensemble model gives `confidence`;
   - `_compute_recommendations()` → `transfer_policy.plan_transfers()`.
5. The dashboard `frontend/src/pages/Analytics.jsx` counts labels (Dead, Excess, Low, New, Optimum, Slow) and shows tiles and tabs.

**Commands:**
- See the table: `docker exec supabase_db_ISDIA psql -U postgres -c "select store_id, product_id, stock_qty, recent_qty, age_days, region from public.ml_inventory limit 5;"`
- Reload it: `cd ml_backend && set -a && source .env && set +a && ../.venv/bin/python import_jiran_ml_real_data.py --push`
- Whole pipeline by hand:
```bash
cd ml_backend && set -a && source .env && set +a && ../.venv/bin/python - <<'PY'
import json, urllib.request
from supabase_watcher import fetch_inventory, build_api_payload
payload = build_api_payload(fetch_inventory(None, None))
req = urllib.request.Request("http://127.0.0.1:8001/recommend", json.dumps(payload).encode(), {"content-type": "application/json"})
print(json.load(urllib.request.urlopen(req))["summary"])
PY
```
**You should see:** 175 rows; label counts (about Dead 70, Slow 35, Excess 33, Optimum 26, Low 11); 2 transfers; 10 restocks.

**Ask Codex:** "Walk me through process_trigger line by line."

---

### Session 3: Stock labels (`ml_backend/inventory_policy.py`)

**Goal:** understand why a product is called Low, Dead, New and so on.

| Function | Takes | Returns / does |
|---|---|---|
| `policy_metrics(stock_qty=, forecast_30d=, forecast_7d=, recent_qty=)` | stock and demand | `coverage_30d_feat` (stock ÷ month demand), `days_of_stock_30d_feat`, `stockout_risk_7d` |
| `stock_policy_label(row)` | one feature row | old rule: Dead / Slow / Low / Excess / Optimum |
| `stock_policy_label_v2(row)` | same row + optional `age_days`, `lead_time_days`, `days_to_next_order`, `on_order`, `daily_rate` | "New" if under 28 days; delivery-based "Low" if lead time is known; otherwise exactly the old rule |
| `is_new_product(age_days)` | days on sale | True if under `MIN_HISTORY_DAYS` (28) |
| `in_stock_rate(units_sold, days, stockout_days)` | sales and empty days | units ÷ in-stock days (at least 7) |
| `days_until_next_delivery(lead_time_days, days_to_next_order)` | | the sum of the two |
| `runs_out_before_delivery(stock, on_order, rate, lead, next_order, safety_days=3)` | | True if the stock won't last |
| `receiver_target_stock(rate, days_until_delivery, on_order)` | | how much a Low store should be topped up to |
| `donor_reserve(rate, lead_time_days, order_cycle_days=7, mult=2.0)` | | how much a giving store must keep |
| `no_sale_days(history_days)` | | days without a sale for never-sold items (= history length) |

Constants: `MIN_HISTORY_DAYS = 28`, `SAFETY_DAYS = 3.0`, `DONOR_RESERVE_MULT = 2.0`.

**Try it** (`cd ml_backend && ../.venv/bin/python`):
```python
from inventory_policy import *
r = {'velocity_trend': 1.0, 'forecast_acceleration': 1.0, 'days_since_last_sale': 1}
r.update(policy_metrics(stock_qty=100, forecast_30d=30*36, forecast_7d=7*36, recent_qty=1080))
stock_policy_label(r)                      # 'Low'   (busy store, 100 units = ~3 days)
r2 = {'velocity_trend': 1.0, 'forecast_acceleration': 1.0, 'days_since_last_sale': 1}
r2.update(policy_metrics(stock_qty=100, forecast_30d=4, forecast_7d=1, recent_qty=4))
stock_policy_label(r2)                     # 'Dead'  (quiet store, same 100 units)
stock_policy_label_v2(dict(r, age_days=10))  # 'New'
in_stock_rate(30, 30, 15)                  # 2.0   (30 sold in 15 in-stock days)
runs_out_before_delivery(10, 0, 1.0, 5, 7) # True  (10 days of stock, delivery in 12)
```
**Ask Codex:** "Why is the order of checks Dead → Slow → Low → Excess important?"

---

### Session 4: Forecasting (`ml_backend/forecasting.py`)

| Function | Does |
|---|---|
| `daily_series(frame, as_of)` | turns orders into one number per day (missing days = 0) |
| `forecast_daily(series, horizon, method)` | one method: `weekly_naive` (repeat last week), `recent_mean` (28-day average) or `prophet` |
| `selected_forecast(series, horizon, methods=METHODS)` | tries each method on the last `VALIDATION_DAYS` (28), picks the lowest error, refits on all history; needs at least 56 days, otherwise uses `recent_mean` |
| `uncensor(values, stock, window=28)` | lost-sales fix: empty-shelf days → average of in-stock days |

**Try it:**
```python
import pandas as pd, numpy as np
from forecasting import selected_forecast, uncensor
s = pd.Series([2.0]*60, index=pd.date_range('2026-01-01', periods=60))
selected_forecast(s, 7, methods=('weekly_naive', 'recent_mean'))['method']
uncensor(np.array([2,2,2,2,2,2,2,2,0.]), np.array([5,5,5,5,5,5,5,5,0]))  # last day 0 -> 2
```
**In the API** (`app.py`):
- `get_forecast_features(p)`: fresh forecast from `daily_sales`; otherwise a saved forecast if `_forecast_age_days()` ≤ `FORECAST_MAX_AGE_DAYS` (7); otherwise `live_daily_rate(p)`.
- `_rate_features(rate, method)` turns a daily rate into the 7/14/30/60-day fields.

**Ask Codex:** "Why does the simple 28-day mean beat the selector on our data?"

---

### Session 5: The API by hand (`ml_backend/app.py`)

| Endpoint | Function | Does |
|---|---|---|
| `GET /` | `health()` | is AI loaded |
| `POST /predict-stock` | `predict_stock(req)` | labels only |
| `POST /recommend` | `recommend(req)` | labels + transfers + restocks + summary |
| `GET /feature-importance` | `get_feature_importance(top_n)` | which inputs matter (permutation importance) |

Input fields per product (`class ProductInput`):
- required: `store_id`, `product_id`, `category`, `stock_qty`, `retail_price`;
- sales: `recent_qty`, `recent_txns`, `days_since_last_sale`;
- **new optional:** `region`, `age_days`, `stockout_days_30d`, `on_order`, `lead_time_days`, `days_to_next_order`, `daily_sales`, `daily_stock`.

**Try it:**
```bash
curl -s -X POST localhost:8001/recommend -H 'content-type: application/json' -d '{"products":[
 {"store_id":"A","product_id":"P1","category":"snacks","stock_qty":2,"retail_price":5,"recent_qty":60,"recent_txns":20,"days_since_last_sale":1,"region":"r1","lead_time_days":4,"days_to_next_order":3},
 {"store_id":"B","product_id":"P1","category":"snacks","stock_qty":400,"retail_price":5,"recent_qty":60,"recent_txns":20,"days_since_last_sale":1,"region":"r1","lead_time_days":4},
 {"store_id":"C","product_id":"P1","category":"snacks","stock_qty":400,"retail_price":5,"recent_qty":60,"recent_txns":20,"days_since_last_sale":1,"region":"r2","lead_time_days":4}]}' | python3 -m json.tool | head -60
```
**You should see:** A = Low; B and C = Dead; one transfer of 18 units from B to A (same region r1); nothing from C (region r2).
Why 18: A sells 2 a day; the next delivery is 3 + 4 = 7 days away; plus 3 safety days = 10 days × 2 = 20, minus the 2 in stock = 18.

**Ask Codex:** "Change lead_time_days for store A to 1 and predict what happens."

---

### Session 6: The transfer engine (`ml_backend/transfer_policy.py`)

| Item | Meaning |
|---|---|
| `plan_transfers(records)` | main function; returns `(transfers, restocks)` |
| `calc_available(donor)` | units a donor can give: `keep_stock` if set; otherwise Dead gives everything, Excess keeps 0.9 × month, Slow keeps 1.5 × month |
| `_transfer(...)` | builds one transfer record and updates both stores' stock |
| `DONOR_LABELS` / `RECEIVE_LABELS` | givers = Excess, Slow, Dead; receivers = Low ("New" never takes part) |
| `DONOR_TIER` | order of givers: Excess, then Dead, then Slow |
| `OPTIMUM_TARGET_COVERAGE = 1.5` | old receiver target: 1.5 × monthly demand |

Steps inside `plan_transfers`:
1. Group by product (and by `group`, i.e. region, if given).
2. Sort receivers: most urgent first.
3. For each receiver, use a single donor if one can cover the whole need.
4. Otherwise combine several donors, biggest surplus first.
5. Any remaining need becomes a restock from the supplier.

**Try it:**
```python
from transfer_policy import plan_transfers
plan_transfers([dict(store_id='A', product_id='P', product_name='p', stock_qty=0, demand_30d=30, label='Low', group='dubai'),
                dict(store_id='B', product_id='P', product_name='p', stock_qty=200, demand_30d=30, label='Excess', group='dubai')])
# one transfer B -> A of 45 units (1.5 x 30)
```
**Ask Codex:** "What does keep_stock change, and why did we pick x2?"

---

### Session 7: The simulated world (`ml_backend/simulation/generate.py`)

| Function | Does |
|---|---|
| `build_world(rng)` | 600 products (category, price, pack size, popularity), 1,000 stores (region, size, ordering day, lead time, safety days, ordering habit), seasons, regional shocks |
| `build_series(rng, products, stores)` | which products each store sells; product decline and late launches |
| `demand_rate(...)` | expected units per day: store × product × weekday × season × trend × promotions × decline × launch × shock |
| `draw_demand(rng, lam)` | random customer counts and basket sizes |
| `simulate_inventory(...)` | day by day: deliveries arrive → sell min(demand, stock) → weekly order-up-to restock |
| `main()` | writes `sales.npy`, `stock.npy`, `on_order.npy`, `demand.npy`, `txns.npy`, `expected_demand.npy`, `series.csv`, `stores.csv`, `manifest.json` |

**Commands:**
- Rebuild the main world (about 10 s, 850 MB): `cd ml_backend/simulation && ../../.venv/bin/python generate.py`
- A different world: `../../.venv/bin/python generate.py --seed 7 --out output/seed_runs/seed7`
- Check the totals: `cat output/sim1000_v1/manifest.json | head -20`

**Ask Codex:** "Which parts of real retail does this simulation leave out?" (Answer: section 9 of the HTML report.)

---

### Session 8: Running the tests and reading results

All scripts are in `ml_backend/simulation/` and run with `../../.venv/bin/python <script>`. Results go to `output/results/`.

| Script | Main functions | Output | Time |
|---|---|---|---|
| `evaluate_forecasts.py` | `run_one()` per series, `score()` → WAPE, MAPE, MASE, RMSSE, bias | `forecasts.json` | ~3 min |
| `oracle_reference.py` | adds the perfect-knowledge forecast | updates `forecasts.json` | seconds |
| `evaluate_lost_sales.py` | `run_one()` raw vs `uncensor` forecasts; `score()` against sales and against true demand | `lost_sales.json` | ~3 min |
| `evaluate_alerts.py` | `snapshot()` features + outcomes; `rule_labels()`, `rule_v2_labels()`, `best_threshold()`, `cluster_ci()`, `metrics()` | `alerts.json` | ~1 min |
| `evaluate_cold_start.py` | weekly snapshots of products 1–41 days old | `cold_start.json` | ~1 min |
| `evaluate_transfers.py --stores all` | `simulate()`, `transfer_round()`, `summarise()`, `rule_labels_vec()` + `check_rule()` | `transfers.json` | ~2 min |
| `run_seeds.sh 1 2 3 4` | everything on 4 more worlds | `results/seeds/` | ~40 min |

**Read a result:**
```bash
cd ml_backend/simulation
python3 -c "import json; d=json.load(open('output/results/alerts.json')); print({m: round(d['targets']['shortage_14d'][m]['f1'],3) for m in ('jiran_rule','jiran_rule_v2','cover_threshold','ml_hgb')})"
python3 -c "import json; d=json.load(open('output/results/transfers.json')); b=d['arms']['none']['lost_units']; print({k: round(1-v['lost_units']/b,4) for k,v in d['arms'].items()})"
```
**Unit tests:** `cd ml_backend && ../.venv/bin/python -m unittest discover -s tests` → `Ran 36 tests … OK`.

**Ask Codex:** "Explain cluster_ci and why we resample stores, not rows."

---

### Session 9: Training the live models (`ml_backend/train.py`, `augmentation.py`)

- Learns from the 3-store data in `ml_backend/training/data/`.
- Labels come from the rule (`stock_policy_label`), so the model learns to **copy the rule**. That is why its score is about 0.99; it is not real accuracy.
- `GroupShuffleSplit` splits by product first; `PolicyAugmentedClassifier.fit()` adds synthetic "what if" rows to the training part only.
- Also reports: repeated grouped CV (5×3) with a confidence interval, and a leakage test without the rule's inputs (F1 drops to 0.73).
- Writes everything to `ml_backend/saved_models/`: `ensemble.pkl`, `scaler.pkl`, `forecasts_aggregated.csv` (now stamped with `generated_at`), `evaluation.json`, `feature_importance.csv`.
- **Retrain:** `cd ml_backend && ../.venv/bin/python train.py`. Back up `saved_models/` first; old backups are in `ml_backend/previous_models/`. Then restart the API (Session 1).

**Ask Codex:** "Why is a model that copies a rule not evidence that it works?"

---

### Session 10: Database changes and migrations

- Migrations live in `supabase/migrations/` and run in name order.
- Apply new ones: `npx supabase migration up --local`
- Today's migration `202611120001_ml_inventory_policy_inputs.sql`:
  - adds 6 nullable columns;
  - rewrites `replace_ml_inventory(inventory_rows jsonb)` to accept them;
  - only the service role may run it.
- **Turn on the delivery-based "Low" and neighbour-only transfers for the 3 stores.** Example only; use real values you know:
```bash
docker exec supabase_db_ISDIA psql -U postgres -c "update public.ml_inventory set region='dubai', lead_time_days=3, days_to_next_order=7;"
```
  Note: re-running the importer with `--push` replaces the table and clears these values. To make them permanent, add them in `build_ml_inventory()` (`import_jiran_ml_real_data.py`), where they are currently set to `None`.

**Ask Codex:** "Help me store region and lead time per store permanently."

---

### Session 11: Git, GRC and publishing

- **Source:** branch `recovery/jiran-archive-20261110`, remote `fork` (pusliqour/capstone_oscorp).
  - `git status`, then `git add …`, then `git commit -m "…"`, then `git push fork recovery/jiran-archive-20261110`.
  - Never commit `.env`, `Private/`, datasets, models or `ml_backend/simulation/output/`.
- **Website:** compiled files go in `Deployment/pages/` (a separate repo, pusliqour/jiran, branch `main`). Steps are in section 9 "Not done" and `docs/TEAM_DEMO.md`.
- **GRC** keeps the shared task board in `.grc/`. Codex can use the same GRC tools:
  - `grc_list_tasks`: all tasks;
  - `grc_context`: briefing;
  - `grc_update_task`: set a status or add a note;
  - `grc_handoff`: before stopping.
  - Open tasks: T9, T11, T12. T8 is cancelled (shown as blocked).

**Ask Codex:** "Show me git log -5 and explain each commit."

---

### Session 12: Fixing the paper (`paper/jiran_isdia_2027.tex`)

Go through section 6.2 one row at a time. Suggested order:
1. **Abstract:** replace "no accuracy claim / AI unavailable" with the simulation results, clearly labelled as simulation.
2. **Table 1:** change "FastAPI service: starts in explicit null-AI mode" and "ML artifacts: legacy artifacts rejected" to the current state.
3. **New section "Simulation evaluation":** design (section 4 here), then results (sections 5.1–5.9). Use the draft paragraph in the HTML report, section 11.
4. **Add the "which model does what" table** (section 2 here).
5. **Research questions:** RQ2 and RQ3 are answered in simulation; RQ1 and RQ4 move to future work.
6. **Related work:** add the six references and check each DOI.
7. **Method details:** define the symbols, units and the +0.1 / minimum-7-days guards; justify each threshold.
8. **Cleanup:** fix the acknowledgements placeholder, add keywords and a corresponding author, and spell-check.
- Build the PDF: `cd paper && pdflatex jiran_isdia_2027.tex` (run it twice for references).

**Ask Codex:** "Rewrite my abstract using only the results in breakdownreport.md sections 5 and 9, labelled as simulation evidence."

---

## 11. Glossary

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
