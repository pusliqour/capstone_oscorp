# Verification report

**Date:** 24 October 2026
**Scope:** local recovery, paper artifact, progress dashboard, and secret hygiene.

## Passing checks

- `python3 -m unittest tests.test_resource_import -v`: 2/2 passed.
- `python3 -m py_compile ml_backend/app.py tools/resource_import.py scripts/configure_local_supabase.py`: passed.
- `npm --prefix frontend run build`: passed; Vite transformed 118 modules and produced the production bundle.
- FastAPI `GET /`: HTTP 200 with `ai_available=false`, `ai_status="null"`.
- FastAPI `POST /predict-stock`: HTTP 503 while AI artifacts remain invalid, preventing unsupported output.
- Local Supabase Auth health: HTTP 200.
- Local PostgREST root: HTTP 200.
- Local Supabase reset/migration: passed.
- Auth/profile trigger + retailer + location + POS + product + variation + inventory round trip: passed; test fixture removed afterward.
- `ml_predictions` row count after smoke test: 0.
- `tectonic jiran_isdia_2027.tex`: passed.
- `paper/jiran_isdia_2027.pdf`: 10 pages.
- Dashboard JavaScript syntax: passed.
- Playwright desktop/mobile QA: dashboard four tabs, architecture view present, no horizontal overflow, no browser console/page errors.
- Playwright Jiran landing QA: recovered landing loads from local Vite server, evidence-safe recovery badge present, no desktop/mobile overflow, no browser console/page errors.
- Tracked working-tree JWT/Square-token scan: no matches.
- `git diff --check`: passed.

## Known debt / intentionally incomplete

- Historical hosted Supabase data were not recovered because the old project hostname does not resolve.
- Legacy serialized ML artifacts cannot load under the recovered stack (`ModuleNotFoundError: _loss`); the API now abstains instead of guessing.
- Square/Apideck edge functions remain optional legacy connectors and have not been reactivated. The tested open recovery path is source-neutral CSV with ERPNext and Odoo mappings.
- The existing repository lint baseline contains numerous errors and warnings. Runtime/build recovery was prioritized; this debt should be handled separately without mixing it with the paper evidence pass.
- Vite reports a JavaScript bundle larger than 500 kB. Code splitting is future optimization work.
- The paper still needs professor/team decisions on author order, corresponding author, contact details, organizer template clarification, and the experimental dataset.
