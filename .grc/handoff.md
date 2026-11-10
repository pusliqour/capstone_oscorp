# Handoff from codex
_11 Nov 2026 03:43 · written by the agent itself_

## Done
Replaced 50 fictional fillers with official public business references: 45 Al Maya branches, 5 Choithrams branches. Stored source URLs, dates, hashes and branch/corporate contact scope. Added source directory and attribution UI. Verified 50 contacts, original account isolation, browser flows and build. Pages release b855f93.

## Remaining
Stable hosting and ML OOD/independent validation remain. Public addresses are official branch/locality labels, not verified full postal addresses. Coordinates remain unset. Companies are reference businesses, not project participants or sources of synthetic stock.

## Next step
Read DATA_SOURCES.json, data/public-businesses.json and docs/ARCHIVE_APP_CONNECTION.md. Treat public-contact reference data separately from generated stock. Do not restore fictional filler or invent branch-specific emails/phone numbers.

## Blocked on
No verified real retailer outcome dataset. Mac/tunnel hosting remains temporary.

## Files that matter
- `scripts/import_public_businesses.py`
- `data/public-businesses.json`
- `DATA_SOURCES.json`
- `AGENTS.md`
- `docs/ARCHIVE_APP_CONNECTION.md`
- `supabase/migrations/202611110002_public_business_references.sql`
- `supabase/migrations/202611110003_public_business_directory.sql`

Task: T13
