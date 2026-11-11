# Improvements

## Implemented and verified

1. **Connected team demo:** GitHub Pages reaches the local Supabase application through an authenticated Python gateway and HTTPS tunnel.
2. **Working team logins:** Three retailer accounts have populated dashboards and account-scoped inventory access.
3. **Editable profiles:** Full name, phone number and store name can be saved and persist across reloads.
4. **Store lifecycle:** Accounts can create a store, delete it with exact-name confirmation, and create a replacement while retaining their login.
5. **Location management:** Set, edit and remove the primary store location, with address, city, country, valid coordinates and map links.
6. **Optional device location:** Browser permission is requested only when selected, with manual-entry fallback.
7. **Account security:** Current-password verification, confirmation, password visibility controls and saved/error feedback.
8. **Preferences:** Keyboard-accessible controls for inventory alerts and the top-sellers dashboard widget.
9. **Product management:** Visible create, edit and delete actions backed by complete transactional inventory writes.
10. **Guarded deletion:** Typed product/store names, cancellable accessible dialogs, focus handling and clear explanations of what will be removed.
11. **Historical integrity:** Product deletion retains historical orders and invalidates obsolete predictions and recommendations.
12. **Tenant isolation:** Owner checks, database policies and restricted gateway endpoints prevent one account from modifying another store's private records.
13. **Validation:** Nonnegative prices/stock, unique SKUs, required names, coordinate bounds, and rejection of invalid ML inputs.
14. **Usability feedback:** Loading states, useful empty states, inline errors, success notices and a responsive settings layout.
15. **Unsaved-edit protection:** Settings header navigation and reload/close warnings protect unfinished edits. Browser Back is a remaining limitation.
16. **SVG icon system:** Emoji graphics replaced with consistent Lucide icons; decorative icons are hidden from assistive technology and icon buttons have accessible names.
17. **Navigation:** Account widgets open Settings, and brand links respect the GitHub Pages base path.
18. **Traceable activity:** Account-scoped records of profile, location, store and product changes.
19. **Atomic ML publication:** Prediction jobs publish to the dashboard tables consistently; a failed batch retains the previous results.
20. **Forecast improvements:** Fill missing calendar days explicitly and select between weekly baseline, recent mean and regularized Prophet using historical validation.
21. **Classifier improvements:** Stronger tree regularization and training-fold-only simulations of stock, demand and inactivity edge cases.
22. **Evaluation:** Product-group validation, class metrics, temporal forecast backtests, baseline comparisons and reproducible synthetic stress tests. Development F1 measures policy agreement, not independently reviewed business outcomes.
23. **Version control:** Local Git checkpoints and a pushed recovery branch, with `updates.md` and `HANDOFF.md` recording progress. Secrets, source data and generated models remain outside Git.
24. **Database administration:** Local Supabase Studio is available at `http://127.0.0.1:54323/project/default/editor` while its container is running.

## Archive recovery completed

25. **Recover the supplied archive:** `/Users/zoro/Projects/Jiran/Private/archives/Jiran-user-20261110.zip` has been extracted safely and fingerprinted outside the source repository.
26. **Restore the missing large transaction history:** Its nested `ml:sample.zip` contains approximately 1 GB of transactions, alongside 2,555 catalog products and 5,960 stock records across 50 stores. The complete file contains 17,025,416 validated transaction lines; uniqueness, numeric values and product/store relationships passed checks.
27. **Separate data provenance:** The archive documentation explicitly describes the large dataset as generated. Keep it separate from the existing three-store dataset, whose original authenticity remains unconfirmed.
28. **Rebuild missing artifacts:** The archive contained no saved `.pkl` or `.joblib` files. New research artifacts were trained and tested in isolation; the live demo model was not replaced.
29. **Reconcile database contracts:** The archive's research `products` schema conflicts with the live application's product identifiers and relationships. Recovered tables now live in the isolated `jiran_archive_lab` schema, containing 2,555 products, 5,960 stock records, 1,013,393 daily sales rows, forecasts and classifications. The live public tables were not overwritten.

## Remaining improvements requiring further work or evidence

30. **Permanent team hosting:** Replace the temporary Mac-dependent tunnel with a stable hosted backend or named tunnel and domain.
31. **Independent business validation:** Confirm source authenticity, add independent stores and dated stock snapshots, and obtain retailer-reviewed outcomes.
32. **Forecast large-error reduction:** MAE improved in development tests, but RMSE worsened and sparse-demand errors remain high. More independent temporal evaluation is needed.
33. **Manual refresh:** Replace legacy POS sync calls with inventory reloads for imported/manual sources.
34. **Full navigation protection:** Extend unsaved-edit handling to browser Back navigation.
35. **Additional account features:** Owner-managed email changes, full account deletion, multiple stores and uploaded-document management require separate implementation.
36. **POS connectors:** Restore and test Square/Apideck only when their credentials and backend services are available.
37. **Research study:** Run participant usability testing and record task completion, errors and feedback. Functional checks are not substitutes for a user study.

## Additional recovery findings

38. **Future-data exclusion:** Found 80,369 transactions later than the stock snapshot. Snapshot features exclude those records, and automated tests verify the cutoff.
39. **Local research API:** Rebuilt archive models run separately at `http://127.0.0.1:8003/docs`; scenario requests do not write to production.
40. **Explicit candidate limits:** The archive classifier's high policy-agreement score does not make it production-ready. It failed the 365-day-inactivity stress scenario; policy/model disagreement is exposed for review.
41. **Research validation:** Classifier evaluation holds out complete stores, and forecast evaluation uses rolling future windows with series selection performed before the first test window. Generated data is never described as independently collected business evidence.


## Workspace and continuity

42. **One canonical project:** `/Users/zoro/Projects/Jiran` now contains the source, data, archives, evidence, historical copies and deployment checkout. Existing paths are compatibility links.
43. **GRC synchronized:** Updated the previously stale project identity/status, recorded completed milestones and added concrete remaining work with a current handoff.
44. **Clear entry points:** `START_HERE.md`, `REMAINING.md`, `Jiran.code-workspace` and `GRC_DASHBOARD.html` make the project easy to reopen and navigate.
45. **Private-data separation:** Credentials, raw data and nested repository history are local under `Private`; only source, docs, tests, migrations and safe GRC metadata are pushed.


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


## 12 November — restore temporary public demo

- Started replacement tunnel https://note-pick-regular-history.trycloudflare.com to the authenticated gateway only; rebuilt and published Pages b8bcb5f.
- Verified all three team accounts over HTTPS, isolation and session rotation; public browser checks passed login, four-horizon stock matrix, archive/source browsing, marketplace and archive-store dashboards. Existing credentials unchanged.
- Updated docs/TEAM_DEMO.md and handoff. Permanent hosting remains cancelled; MLP experiments remain queued pending concerns walkthrough.
