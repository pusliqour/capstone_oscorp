# Jiran account and inventory experience updates

Status: account-management and SVG-icon implementation verified locally and through the public API gateway. Source is pushed to the recovery branch. The frontend build containing Settings and SVG icons was published to Pages in commit `9bbae93`; live SVG rendering and the password visibility toggle were verified.

## Implemented

1. Replaced the locked contact screen with editable full name, phone number and store name.
2. Added account-context refresh so saved names and preferences propagate without signing out.
3. Added store creation for accounts with no store, plus a usable state after store deletion.
4. Added location creation, editing and removal, including address, city, country, map preview and optional coordinates. Zero coordinates remain valid; missing values are no longer treated as zero.
5. Added explicit device-location permission flow with manual-entry fallback.
6. Added password changes with current-password verification, confirmation and visible feedback. Login email remains managed by the owner in this team demo.
7. Added notification and dashboard preferences with keyboard-accessible checkboxes and saved feedback.
8. Added visible product creation, editing and deletion actions. Product saves now write complete inventory records rather than silently creating marketplace listings.
9. Added typed-name confirmation for product and store deletion, with keyboard-accessible native dialogs, focus restoration and cancellation.
10. Added atomic, account-scoped backend operations for these workflows, input validation and recent-account activity.
11. Product deletion preserves historical orders, removes stale ML results and cancels affected listing requests. Store deletion removes store records but retains the login account and personal profile.
12. Added protection against leaving Settings via navigation with unsaved edits, plus browser reload/close warnings.
13. Added responsive account forms, loading feedback, inline errors, clear empty states and accessible labels.
14. Connected account widgets to Settings and corrected brand links for GitHub Pages paths.
15. Added database checks for valid coordinates, nonnegative stock/prices, ownership of stock connections, and RPC-only destructive deletion.

16. Replaced emoji graphics throughout landing, authentication, inventory, analytics, marketplace and access-denied screens with a shared Lucide SVG icon component. Icon-only controls retain accessible names; decorative icons are hidden from screen readers.
17. Preserved the source-only local Git checkpoint `08cf9b6`; final handoff and implementation changes are included in the next checkpoint.

## Verification

- Frontend production build: passed at implementation checkpoint.
- Disposable-account database integration: passed profile persistence, location create/edit/remove, zero-coordinate handling, product create/edit/delete, invalid-input rejection, cross-account denial, store delete/recreate and retained login.
- Browser end-to-end verification: passed profile persistence, zero coordinates, unsaved-edit cancellation, product create/edit/delete, location removal, current-password change, store deletion and mobile fit.
- Public HTTPS gateway integration: passed the account-management transactions and password update using disposable users.
- Tracked browser test: `tests/account_management.cjs`; fixture lifecycle: `scripts/ux_fixture.py`.
- The three team demo stores are not used for destructive testing.

## Research boundaries

These changes provide functional prototypes and test evidence. They are not results of a participant usability study. Source-data authenticity and independent ML validation remain unconfirmed, as documented in `docs/TEAM_DEMO.md` and `docs/ML_CHANGES.md`.

## Version control

The existing local Git repository is retained. Implementation and validation checkpoints record source, migrations, test scripts and this document. Passwords, environment files, raw/normalized store data, test credentials, reports derived from private data and generated model artifacts remain outside commits.

## Remaining work at handoff

- Pages build `9bbae93` now contains the new Settings and SVG icons. Live icon rendering and password visibility toggle passed; a full public-site management browser pass remains a useful follow-up. The full workflow already passed locally and through the public API gateway.
- Existing team login passwords remain unchanged (`team-demo-credentials.json` outside Git).
- Manual inventory refresh still uses the legacy POS sync handler; adapt it to a plain inventory reload for imported/manual sources.
- Settings guards unsaved edits through its header navigation and reload/close warnings; browser Back is not blocked.
- Login email remains owner-managed. Full account deletion, multiple stores per account, POS connector restoration and uploaded-document management are outside this update.
- The Mac, Docker, ML service, Python gateway and quick tunnel must stay running for the currently deployed demo.


## Archive recovery — 10 November 2026

- Inspected and fingerprinted `Jiran.zip`; safely recovered its nested large transaction archive outside Git.
- Added `improvements.md` with completed and remaining improvements, as requested.
- Validated 17,025,416 synthetic transaction lines, 2,555 products and 5,960 stock records across 50 stores.
- Added a disk-backed, memory-bounded recovery pipeline and preserved full catalog metadata.
- Identified 80,369 transactions after the stock snapshot and excluded future information from snapshot features.
- Rebuilt isolated classifier/forecast artifacts and measured store-group and temporal development performance.
- Restored separate Supabase research tables under `jiran_archive_lab`; preserved the public app's existing data.
- Added a read-only local research API on port 8003, with explicit provenance, separate policy/model outputs and disagreement review flags.
- Recorded the classifier's failure on 365-day-inactivity scenarios; the research candidate was not promoted to production.
- Added regression tests for duplicate IDs, cross-store product references, temporal leakage and forecast-series selection.
- Recovery details and reproduction commands are in `docs/ARCHIVE_RECOVERY.md`.

- Final verification: 22 unit/regression tests passed; research API scenario/invalid-input checks, Studio/API-doc rendering and existing demo account/isolation checks passed.


## Canonical workspace and GRC — 10 November 2026

- Consolidated known Jiran source, operator documents, credentials, ZIPs, recovered data, original ML checkout, preview/export history and Pages deployment under `/Users/zoro/Projects/Jiran`.
- Retained compatibility links at the old Projects, Documents, Downloads and Desktop locations. No content was deleted or merged destructively.
- Added visible `Private` and `Deployment` shortcuts to hidden local storage; private material and nested repositories remain excluded from source Git and GRC scans.
- Added `START_HERE.md`, `REMAINING.md`, `Jiran.code-workspace` and the local `GRC_DASHBOARD.html` launcher. Current docs point to the canonical locations.
- Refreshed GRC's project name, goal, completed milestones, remaining tasks and resume/handoff state. Historical October tasks remain intact.
- Updated credential/test helpers to use the canonical private operator folder.
- Kept Supabase's internal Docker project ID `ISDIA` and old virtual-environment launcher links so existing data volumes and processes remain intact.

- Consolidation verification passed: all five local services returned HTTP 200; 22 unit/regression tests, production build, full disposable-account browser workflow, demo isolation and gateway login/refresh/logout checks passed. Eleven compatibility links and private-data exclusions were verified.


## 10 November 2026 — archive application connection

- Connected the user-supplied generated archive to fifty labelled synthetic storefronts without replacing the three original team stores.
- Imported 5,960 inventory entries, 9,100 daily order summaries, 1,013,393 daily product sales entries, 5,960 policy/model results, fifty connection summaries and 500 labelled demo listings.
- Added authenticated Archive data navigation, source counts/dates, search, store filtering, pagination, daily sales history and visible model/source limitations.
- Fixed marketplace listings disappearing when sellers lack locations or their private profiles are correctly hidden.
- Replaced client-side exchange state writes with checked database transitions, reservations, two-party confirmation, atomic stock transfer, rollback and idempotence.
- Added real listing/request audit events and activity refresh/load-more; no fabricated historical exchanges or user activity.
- Fixed imported inventory Refresh to reload records without invoking an unavailable POS connector.
- Added AGENTS.md, DATA_SOURCES.json and docs/ARCHIVE_APP_CONNECTION.md so another agent can discover the data, reproduce imports and respect private-file exclusions.


## 11 November 2026 — requested fictional contact filler

- Filled missing addresses and phone/contact emails for the fifty synthetic archive stores; preserved original team accounts and owner-entered values.
- Addresses are explicitly marked FICTIONAL DEMO; phone numbers use invalid +000 and email uses example.invalid. No real business contacts were sourced. Coordinates remain unset.
- Fixed the contact RPC argument and returned address/name/email fields to match the dialog; real contacts require ownership or an accepted exchange.


## 11 November 2026 — official public-business reference contacts

- At the user’s explicit request, replaced fifty fictional demo contact/location placeholders with sourced public-business references: 45 Al Maya Group branches and five Choithrams branches.
- Scraped only official locator/contact pages; saved business names, branch/locality addresses, source map links, phone/email scope, source URLs, timestamps and source hashes in data/public-businesses.json and Supabase business_references.
- Al Maya phone numbers are branch numbers; its email is corporate. Choithrams phone/email are central store-support contacts, not asserted branch lines. Complete street/postal addresses and coordinates are not invented.
- Retained synthetic account/store names and stock provenance; source businesses are explicitly not participating retailers or suppliers of synthetic inventory. Original team accounts and owner-entered details are preserved.
- Added a browsable public-reference directory under Archive data and source attribution in archive account banners/contact dialogs. No messages or calls were sent.


## 12 November — multi-horizon stock planning

- Added per-product 7/14/30/60-day demand and recommended on-hand stock ranges, horizon-specific stock position, add-to-range amounts and surplus above maximum.
- Published matrix JSON atomically to Supabase and added expandable Analytics → Stock Metrics tables. Existing archive forecasts retain dated historical provenance.
- Exposed lead-time, three-day safety and seven-day review assumptions; no statistical-confidence or proven-optimality claim. New products collect own-store history before receiving bounds; unconfirmed open-order arrivals are not credited.
- Verified 41 backend tests, exact live API example, and all 6,135 stored matrices. Details: docs/STOCK_PLANNING.md.
