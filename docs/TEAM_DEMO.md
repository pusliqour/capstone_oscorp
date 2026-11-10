# Jiran connected team demo

## Current access

- Team site: https://pusliqour.github.io/jiran/
- HTTPS gateway: https://navy-genre-bind-fleece.trycloudflare.com
- Pages commit: `666faccef60d9424cd070283bd601ddf92fb2a7b`
- Credentials: `Private/operator/team-demo-credentials.json` (owner-only; not in Git)
- Accounts: `research01@jiran.test`, `research02@jiran.test`, `research03@jiran.test`

The site has been tested in a browser: team login, populated Analytics and refresh/session persistence. Three-account isolation, refresh-token rotation, logout, anonymous denial and rejection of raw development JWTs were tested through the public HTTPS gateway.

This is a temporary team demo served from this Mac. Keep the Mac awake and connected, Docker/Supabase running, and the Python gateway and Cloudflare tunnel running. Closing the lid, stopping those processes, or losing internet can interrupt access. Recreating the quick tunnel changes its address and requires rebuilding/redeploying Pages.

## Architecture

GitHub Pages hosts the React frontend. HTTPS requests go through Cloudflare Tunnel to `scripts/team_gateway.py` on `127.0.0.1:8787`. The gateway signs in against local Supabase and exchanges its development tokens for private gateway sessions. It forwards only permitted application endpoints with the user's upstream session. The browser never receives the Supabase service role or development JWTs. Administrative endpoints and raw ML tables are not exposed. New account registration and POS connectors are not available through this team-demo gateway; use the provisioned accounts.

The database is on port 54321. The private FastAPI ML service is on port 8001. Its watcher processes jobs and atomically publishes results to the retailer-facing tables. Python inference is not exposed to the public tunnel.

The working source is `/Users/zoro/Projects/Jiran`; Pages deploys built files from `/Users/zoro/Projects/Jiran/Deployment/pages`. Raw spreadsheets and model artifacts are kept out of the Pages repository. Credentials are supplied separately.

## Restart instructions

1. Start Docker Desktop, then `bash scripts/run-local.sh` from the working source. This starts Supabase, applies migrations, and starts the frontend and ML service/watcher.
2. In another terminal: `.venv/bin/uvicorn scripts.team_gateway:app --host 127.0.0.1 --port 8787`.
3. In another terminal: `cloudflared tunnel --url http://127.0.0.1:8787 --no-autoupdate --protocol http2`.
4. If the tunnel hostname changed, set `JIRAN_PUBLIC_SUPABASE_URL` to its HTTPS address, set `JIRAN_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_jiran_team_gateway`, and run `VITE_TEAM_DEMO=true bash scripts/build-pages.sh`.
5. Copy only `frontend/dist/` into the Pages checkout, preserve its `.git` directory, review, commit and push. Never copy `.env`, model artifacts, spreadsheets or credentials.

Restarting the gateway invalidates its in-memory sessions; team members sign in again with the same account credentials. Permanent uptime requires a named tunnel/domain or hosted backend, rather than this temporary quick tunnel.

## Data origin — unconfirmed

The demo uses existing local files from `/Users/zoro/Projects/Jiran/Private/reference/original-ml-repository/data/real`, from repository `https://github.com/M4MD-M7SN/jiran-ml`, commit `4adc1ee6c939246a2306cee8f5b8ea5c720d6ffb`:

- `jiran_square_catalog_store_a.xlsx`, `_b.xlsx`, `_c.xlsx`
- `orders_single_sheet_import_store_a.xlsx`, `_b.xlsx`, `_c.xlsx`

The importer normalized these into 129 catalog products, 175 store/product inventory rows, 802 orders and 3,737 order lines. The dataset ends on 31 March 2026. Relative dashboard filters are anchored to the imported history, not today's live sales.

The source repository calls these real data, but that claim has not been independently verified. All six workbook metadata records identify `openpyxl` as creator and the same creation timestamp (`2026-04-12 14:10:22`). This is consistent with programmatically written workbooks; it does not prove whether their contents were synthesized or exported from actual shops. Original collection, consent and business authenticity remain unconfirmed. The user-facing team demo identifies the source as awaiting confirmation. No raw workbooks were uploaded to Pages.

The file hashes and workbook metadata are recorded in `Private/operator/DATA-PROVENANCE.json`. Confirm the source before claiming real business accuracy or adding more business data.

## Evaluation and maintenance

- Main evaluation: `ml_backend/evaluation/REPORT.md`
- Previous artifacts: `ml_backend/previous_models/` (private rollback copy)
- Current artifacts: `ml_backend/saved_models/` (private)
- Reproduce evaluation: `(cd ml_backend && ../.venv/bin/python evaluate.py)`
- Run a new ML batch: `.venv/bin/python scripts/run_ml_batch.py`
- Verify data isolation: `.venv/bin/python scripts/verify_demo.py`
- Verify public gateway: `JIRAN_GATEWAY_URL=https://navy-genre-bind-fleece.trycloudflare.com .venv/bin/python scripts/verify_gateway.py`

Do not run `bootstrap_demo.py` just to refresh predictions. It rebuilds the dedicated demo accounts' storefront rows and removes their previous prediction mappings. Use the batch runner for predictions.

Stock categories follow an explicit inventory policy. Ensemble support is shown separately and is not a calibrated probability of business success. Demand is derived from a historically selected weekly baseline, recent mean, Prophet, or observed-sales fallback. Empirical error bands are not calibrated confidence intervals. See `ML_CHANGES.md` for improvements and their limits.


## Archive connection update

Archive data is now available to every team login via **Archive data**. The marketplace has 500 labelled synthetic demonstration listings from fifty recovered archive stores. Existing team inventory is preserved. Source and imported daily summaries are described in `ARCHIVE_APP_CONNECTION.md` and `../DATA_SOURCES.json`. No real retailer addresses or historical exchanges were supplied. Exchange actions now use the checked atomic RPC rather than direct status writes.
