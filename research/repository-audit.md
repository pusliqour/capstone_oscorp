# Jiran repository and recovery audit

**Audit date:** 24 October 2026
**Repository:** `M4MD-M7SN/capstone_oscorp`, default branch `master`, inspected at `5bcfd97` before local recovery changes.

## Verified baseline

- Frontend: React 19 + Vite 7 + Supabase JS.
- Operational screens: authentication, dashboard, inventory, analytics, exchange, settings.
- Backend: FastAPI with serialized scikit-learn/XGBoost artifacts and a Supabase trigger watcher.
- Persistence contract: Supabase Auth, PostgreSQL/PostgREST, Storage, and RPC.
- External ingestion: Square-oriented UI plus manual CSV/Excel import code.
- Graduation evidence: final report, technical/marketing posters, presentation, code, and recorded demo link.

## Failure reproduction

| Check | Result | Interpretation |
|---|---|---|
| Original Supabase auth/rest endpoints | DNS resolution failure | Hosted project is unavailable; historical rows were not recoverable |
| `npm ci && npm run build` | Passed | Frontend source still compiles |
| `npm run lint` | Failed: 47 errors, 7 warnings | Existing code-quality debt; not a runtime proof |
| Legacy ML startup | Failed on missing `libomp`, then incompatible serialized `_loss` module | Model artifacts are not portable to the current Python/scikit-learn stack |
| Recovered ML API | Starts on `127.0.0.1:8001` | Operational API is active; AI status is explicitly `null` |
| Prediction endpoint while null | HTTP 503 | No fabricated fallback prediction is produced |
| Local Supabase start | Docker image startup still pending/blocked | Schema exists, but database activation is not yet verified |

## Security findings

- Frontend and backend `.env` files were tracked in Git.
- A backend service credential was present in repository history.
- The frontend printed its configured Supabase key to the browser console.
- The README contained reusable demo-account credentials.

Local recovery removes current tracked `.env` files, sanitizes examples, removes browser key logging, and removes the demo password. Historical credentials must be rotated because Git-history cleanup alone cannot make a published secret safe.

## Data state

No historical row count, dataset lineage, ground truth, model validation split, or reproducible performance report can currently be verified. Existing model files and generated JSON/CSV files are historical artifacts, not accepted paper evidence. `data/data-status.json` is the machine-readable source of truth.

## Minimal-change recovery decisions

1. Keep the existing Supabase SDK and table contracts; run Supabase locally/self-hosted.
2. Add a migration that recreates the operational table/RPC/storage contract.
3. Make the ML service start in an explicit null state when artifacts are incompatible.
4. Make the hosted Supabase watcher opt-in.
5. Treat Square as an optional connector, not a platform boundary.
6. Add tested ERPNext and Odoo CSV normalizers feeding Jiran's neutral inventory import contract.
7. Do not widen the paper's claims beyond inventory/resource-allocation workflows demonstrated by the code.

## Remaining Priority Alpha issues

1. Finish the first local Supabase container boot and verify schema migration.
2. Configure generated local keys and create a new local account.
3. Exercise inventory import, dashboard, exchange listing, and request workflows end to end.
4. Fix the highest-impact frontend runtime/lint defects one at a time.
5. Obtain a traceable dataset before retraining or evaluating AI.
6. Rotate every secret that ever appeared in public Git history.
