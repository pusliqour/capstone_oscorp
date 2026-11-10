# Jiran agent entry point

Work in `/Users/zoro/Projects/Jiran`. Start with `START_HERE.md`, `HANDOFF.md`, `DATA_SOURCES.json` and `docs/ARCHIVE_APP_CONNECTION.md`. The `.grc` project and native GRC sidebar both use this folder. Call `grc_context` here when available, and leave an updated handoff before stopping.

## Data is already imported

The user explicitly requested connecting the supplied ZIP to the app on 10 November 2026. Do not repeat the earlier claim that the archive is only available in an isolated schema. The original three team stores remain intact; fifty labelled synthetic archive stores are additionally mapped into the public storefront. All signed-in retailers can browse the bounded read-only `/data-explorer` projection, which includes forecasts and daily source history. See `DATA_SOURCES.json` for counts and markers.

Private source files, DuckDB, manifests, models and credentials live under `Private/` (symlink to `.private/`) on this Mac. They are intentionally absent from Git and from GRC scans. Another computer must obtain the ZIP/private recovery separately and rerun the documented recovery/import; a Git clone alone cannot contain those private assets. Never infer source absence merely from a Git/GRC file listing. Do not push private data or keys.

## Keep records truthful

The ZIP is generated synthetic grocery research data. The three-store Excel authenticity remains unconfirmed. Real addresses, contact details, exchange history and human activity were not supplied. The user subsequently authorized fictional contact/address filler for the fifty synthetic archive stores: see migration 202611110001. Demo addresses are labelled FICTIONAL DEMO, phones use invalid +000, and emails use example.invalid. Do not portray these as recovered or real details. Preserve owner-entered information. Archive store names and demonstration listings are visibly synthetic. Daily orders are aggregated summaries; price-based totals are catalog-value estimates, not actual receipt revenue. Historical February snapshots must not be presented as current November stock or current forecasts.

## Runtime and changes

Local Supabase API: 54321; Studio: 54323; main ML: 8001; research API: 8003; frontend: 5173; authenticated gateway: 8787. `supabase/config.toml` keeps project_id `ISDIA` to preserve existing Docker volumes. The temporary Cloudflare tunnel depends on this Mac and running processes. See `docs/TEAM_DEMO.md`.

Never truncate/rebootstrap public tables or modify existing team accounts for a test. Use disposable accounts and clean them up. `connect_archive_storefront.py` uses deterministic inserts and preserves subsequent edits on rerun. Exchange transitions use `exchange_action` RPC, with row locks, authorization, reservations, two-party confirmation and atomic inventory settlement. Do not restore direct browser writes to request status.

Run relevant checks: `scripts/verify_archive_app.py`, `scripts/verify_demo.py`, `scripts/verify_gateway.py`, `tests/archive_app.cjs`, and `npm --prefix frontend run build`. Browser checks use the installed Playwright module indicated in HANDOFF.md. Destructive account tests use disposable fixtures only.

Source branch: `recovery/jiran-archive-20261110`, push to `fork` (pusliqour/capstone_oscorp). Pages compiled assets belong to the separate checkout `Deployment/pages` (pusliqour/jiran main). Never commit datasets, `.env`, passwords, model binaries or unreviewed unrelated changes from another agent.
