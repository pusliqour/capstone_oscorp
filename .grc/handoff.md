# Handoff from codex
_11 Nov 2026 01:17 · written by the agent itself_

## Done
Archive-to-app connection and atomic exchanges complete. Original team stores preserved; 50 synthetic storefronts, 5960 stock rows, 9100 daily orders and 500 listings added. Source 914ea7c and Pages a5448d5 pushed. Local integration and published-site archive/account browser checks passed. Import rerun inserts zero duplicates.

## Remaining
Stable hosting; verify original Excel origin; ML inactivity/OOD and independent outcome/forecast validation; usability study. ZIP contains no real retailer addresses/phones or historical exchanges. Private raw files/models remain local and must be supplied separately on another machine.

## Next step
Read AGENTS.md, DATA_SOURCES.json and docs/ARCHIVE_APP_CONNECTION.md. Continue hosting or ML/OOD tasks in REMAINING.md. Existing team accounts can browse /data-explorer now.

## Blocked on
No verified real retailer outcome/location/contact dataset. Hosting still depends on Mac/tunnel. Do not portray historical synthetic stock as live trading.

## Files that matter
- `AGENTS.md`
- `DATA_SOURCES.json`
- `docs/ARCHIVE_APP_CONNECTION.md`
- `scripts/connect_archive_storefront.py`
- `scripts/verify_archive_app.py`
- `tests/archive_app.cjs`
- `REMAINING.md`

Task: T13
