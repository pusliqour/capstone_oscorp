# Jiran ML Real-Data Integration

This bridge connects the private `M4MD-M7SN/jiran-ml` Square exports to the
local Jiran FastAPI and Supabase stack without copying source or derived store
data into the public application repository.

## Data flow

```text
private jiran-ml/data/real/*.xlsx
        |
        v
import_jiran_ml_real_data.py
        |-- training/data/{products,stock,transactions}.csv
        |-- integration_data/ml_inventory.csv + manifest.json
        v
train.py -> saved_models/ (local generated artifacts)
        |
        +-> FastAPI :8001
        +-> Supabase ml_inventory -> watcher -> /recommend
```

The generated directories are ignored by Git. Model artifacts are also local
generated files because they can encode information from private store data.
No service-role key or source spreadsheet is committed.

## Rebuild locally

Clone the private model/data repository beside this repository, then run:

```bash
uv pip install --python .venv/bin/python -r ml_backend/requirements.txt
.venv/bin/python ml_backend/import_jiran_ml_real_data.py \
  --source-dir ../jiran-ml/data/real
.venv/bin/python ml_backend/train.py --data-dir ml_backend/training/data
npx supabase migration up --local
```

Load the live local `ml_inventory` table without writing credentials to disk:

```bash
eval "$(npx supabase status -o env)"
SUPABASE_URL="$API_URL" SUPABASE_SERVICE_KEY="$SERVICE_ROLE_KEY" \
  .venv/bin/python ml_backend/import_jiran_ml_real_data.py \
  --source-dir ../jiran-ml/data/real --push
```

Populate the retailer-facing demo tables and map the three research accounts to
Business Bay, Dubai Marina, and Jumeirah:

```bash
eval "$(npx supabase status -o env)"
.venv/bin/python ml_backend/storefront_demo.py \
  --data-dir ml_backend/training/data \
  --ml-outputs ml_backend/ml_outputs \
  --supabase-url "$API_URL" \
  --service-key "$SERVICE_ROLE_KEY"
```

The storefront command is idempotent: it replaces only the three mapped demo
retailers' POS connections, products, inventory, orders, ML predictions, and
transfer recommendations. It leaves the admin account and unrelated retailers
untouched.

Start the API with the Supabase watcher enabled:

```bash
cd ml_backend
eval "$(cd .. && npx supabase status -o env)"
export SUPABASE_URL="$API_URL"
export SUPABASE_KEY="$SERVICE_ROLE_KEY"
export ENABLE_SUPABASE_WATCHER=true
../.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8001
```

## Verification

```bash
.venv/bin/python -m unittest discover -s ml_backend/tests -v
curl -fsS http://127.0.0.1:8001/
```

The health response must contain `"ai_available": true`. To exercise the
watcher end to end, insert a pending `recommend` row into `ml_triggers`; it
reads `ml_inventory`, calls the live API, writes result files under
`ml_backend/ml_outputs/`, and marks the trigger `done`.

## Current source contract

- Catalog files: `jiran_square_catalog_store_*.xlsx`
- Order files: `orders_single_sheet_import_store_*.xlsx`
- Source repository is recorded in the generated manifest.
- Store IDs are stable slugs such as `STORE_STORE_ONE`.
- Reused store-exclusive SKUs with conflicting metadata are namespaced by store.
- The Supabase refresh replaces the complete snapshot atomically through a service-role-only RPC.
- Unknown order SKUs fail the import instead of being silently dropped.
- The dataset maximum order timestamp is used as the recent-sales cutoff so
  historical exports remain statistically meaningful.
