# Jiran.zip recovery — 10 November 2026

## What was recovered

The supplied `/Users/zoro/Projects/Jiran/Private/archives/Jiran-user-20261110.zip` was inspected and extracted to `/Users/zoro/Projects/Jiran/Private/recovery/20261110`. Its nested `Jiran/ml:sample.zip` contained the missing large transaction CSV. Neither the supplied SQL nor its Python training/serving programs were executed. Source files and extracted files were fingerprinted; the outer and nested product/stock CSVs matched exactly.

| Recovered asset | Verified count |
|---|---:|
| Catalog products | 2,555 |
| Stores | 50 |
| Store/product stock snapshots | 5,960 |
| Raw transaction lines | 17,025,416 |
| Daily store/product sales aggregates | 1,013,393 |
| Forecast records rebuilt | 5,960 |
| Stock classifications rebuilt | 5,960 |

The original catalog metadata is preserved: common-product flags, expiry dates, unit quantities, wholesale/retail prices and source store identifiers. All 17 million raw transaction lines are preserved in the external CSV and disk-backed DuckDB database. Supabase receives the complete daily aggregates, including original transaction counts and squared-quantity sums, rather than millions of redundant unit-sale rows.

The archive also contains notebooks, multiple versions of ML/API code, deployment examples, database definitions and sample forecasts. It contains **no saved trained models**, no recovered Supabase account/database backup and no historical user credentials. Trained research artifacts were rebuilt rather than claimed as recovered files.

## Provenance and data quality

`DATA_SUMMARY.md` explicitly calls this a generated 50-store grocery dataset, and a generator is included. It is synthetic research data, not verified real-store history. This is separate from the three-store Excel dataset used by the live team demo, whose authenticity remains unconfirmed.

The recovered CSV validation passed unique product IDs, unique store/product keys, unique transaction IDs, valid finite prices/quantities/timestamps, known products/stores and valid store/product relationships. One stock pair has no sales. Actual transactions run from 29 August 2025 to 26 February 2026; source prose says 25 February, so the machine-verified dates take precedence.

There are **80,369 transactions later than the stock snapshot**. Snapshot feature generation excludes records on or after the cutoff date of 25 February 2026. Tests explicitly verify that future records cannot affect snapshot quantities, transaction counts, means or standard deviations.

## Where to see it

1. Open **http://127.0.0.1:54323/project/default/editor?schema=jiran_archive_lab** on this Mac.
2. The schema selector should read `jiran_archive_lab`, not `public`.
3. Browse `datasets`, `products`, `stock`, `daily_sales`, `forecasts`, `stock_classifications` or `evaluations`.
4. Open **http://127.0.0.1:8003/docs** for the read-only research model API.

The research schema is not granted to anonymous/authenticated app roles, is not exposed by the team gateway, and does not replace public app tables. The live demo still has 175 product/inventory rows, 802 orders and 3,737 order lines. The previous live model remains in place.

The research API supports listing stores/inventory and testing stock, price, demand and inactivity scenarios. It saves no predictions back to production. Policy decisions and learned-model predictions are reported separately, with `review_required` set when they disagree.

## Model results and limitations

- Classifier evaluation holds out ten whole stores. Candidate selection uses grouped cross-validation only within the training stores; the category vocabulary also comes from training stores only.
- Stock-label macro F1 is approximately **0.991**, against explicit policy-generated labels; training macro F1 is approximately **1.000**. The majority baseline is approximately **0.166**. The direct rule baseline is **1.000 by construction**, so classifier agreement is not evidence that the learned model improves business decisions.
- Fifty store/product series were tested at two rolling temporal origins. Series ranking precedes the earliest test window; forecasting-method selection uses an inner historical validation window. Test-store sales history is an available operational input, not withheld future history.
- Forecast MAE is approximately **12.332** versus weekly baseline **12.751**. RMSE is approximately **17.861** versus **18.765**. WAPE remains approximately **25.5%**.
- Fifty additional API scenarios covered ten stores. Snapshot, stockout, large-stock and demand-surge cases agreed with the policy in those checks. **The learned classifier disagreed in every tested 365-day-inactivity case.** The policy correctly returned Dead and the API flags the disagreement.

These are development research results on generated data; the classifier test split has been re-evaluated after correcting temporal series selection. They are not untouched final business validation. No archive model was promoted to the live team demo. Real outcomes, independent stores, repeated stock snapshots and reviewed labels are still needed.

## Reproduce the recovery

Use the existing `.venv` and the dependencies in `ml_backend/requirements.txt` (the tested DuckDB version is 1.5.6). Archive/data/model paths are deliberately outside the Git repository.

```bash
cd /Users/zoro/Projects/Jiran
.venv/bin/python ml_backend/recover_archive_data.py \
  --source /Users/zoro/Projects/Jiran/Private/recovery/20261110/nested/data \
  --output /Users/zoro/Projects/Jiran/Private/recovery/20261110/lab
.venv/bin/python ml_backend/train_archive_lab.py \
  --lab /Users/zoro/Projects/Jiran/Private/recovery/20261110/lab
npx supabase migration up --local
.venv/bin/python scripts/load_archive_lab.py \
  --lab /Users/zoro/Projects/Jiran/Private/recovery/20261110/lab
ARCHIVE_LAB_DIR=/Users/zoro/Projects/Jiran/Private/recovery/20261110/lab \
.venv/bin/uvicorn archive_lab_api:app --app-dir ml_backend \
  --host 127.0.0.1 --port 8003 --no-access-log
```

Stop/restart the research API after retraining so its in-memory model matches the saved results. The research loader replaces only its isolated lab tables, atomically. On error, its transaction rolls back. It never runs the archive's conflicting `CREATE TABLE public.products` definitions.

Verification completed: 22 unit/regression tests passed; research API scenarios and invalid-input checks passed operationally while reporting the inactivity-model disagreement; all three existing demo account/isolation checks passed. Studio schema selection and research API documentation rendered in browser checks.

Repeat verification:

```bash
.venv/bin/python -m unittest discover -s ml_backend/tests -v
.venv/bin/python scripts/verify_archive_lab.py \
  --output /Users/zoro/Projects/Jiran/Private/recovery/20261110/lab/models/scenario_tests.json
.venv/bin/python scripts/verify_demo.py
```

Private manifests, source hashes, exact metrics, scenario results, rebuilt artifacts, source CSVs and `archive.duckdb` live under the external recovery directory. Code, migrations, tests and this report belong in Git; those data/artifacts do not.
