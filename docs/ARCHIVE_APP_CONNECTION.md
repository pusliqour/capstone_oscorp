# Supplied archive connected to the application

The original recovery loaded the archive into `jiran_archive_lab`, but the retailer UI queried `public`. That separation caused the user's incomplete-data report. On 10 November the user explicitly asked to populate and extend the functioning app using the supplied data.

## What is now connected

- Fifty archive retailers, labelled `Synthetic archive store_…`, with separate account IDs and a mapping in `jiran_archive_lab.store_accounts`.
- 5,960 products, variations and inventory rows, retaining source store/product IDs and February snapshot dates.
- 9,100 store/day order summaries containing all 1,013,393 daily product sales rows. They represent all 17,025,416 original transaction lines; the original CSV and DuckDB remain in Private. `orders.source = synthetic_archive_daily_aggregate` distinguishes summaries from receipts. Monetary totals use catalog prices and are estimates.
- 5,960 policy/model comparisons and historical demand forecasts, plus fifty connection-intelligence summaries derived from source sales.
- Five hundred explicitly synthetic demonstration listings, ten per archive store, limited to available source stock. Existing three-store inventory and account passwords are preserved.
- Authenticated **Archive data** navigation at `/data-explorer`: overall counts, dates, source gaps, store filter, product search, bounded pagination, source daily history and policy/model disagreements.
- Import actions appear as actual import events. Listing and request changes create audit events. Activity supports refresh and loading more records.

## Verification

- Full-history archive sales totals match the normalized source CSV, including records beyond the API response cap.
- Disposable-account checks cover source pagination, anonymous denial, private isolation, marketplace visibility, approvals, reservations, cancellation, dismissal, two-party completion, stock conservation, idempotence and rollback.
- Browser checks cover source search/history/mobile fit, populated marketplace names, and original account/profile/location/product workflows.
- Rerunning the importer inserts zero duplicates.

## Functional repairs

Marketplace queries no longer require a seller's private profile or a non-existent location. Business names are obtained through the narrow name RPC, and published store geography is optional. Personal profiles, documents and other stores' private inventory remain protected.

Exchange transitions now use `exchange_action` rather than separate browser mutations. Sellers can accept open or listing requests; buyers can cancel active requests; open requests can be dismissed for one store. Listing acceptances reserve stock with row locks. Both participants confirm completion; the database then deducts seller inventory, credits buyer inventory and decrements the listing atomically. Repeated completion does not transfer twice. Failure rolls back the final confirmation and quantities. The operational ML stock feature is updated where present; historical archive snapshots remain immutable. New inventory receipts still require the normal ML refresh before refreshed recommendations are available.

Sales/category/top-product calculations now aggregate in PostgreSQL so the 1,000-row REST limit cannot silently truncate larger archive stores. Archive account dashboards display a source/date notice, and policy-only confidence displays as not calibrated.

No historical exchanges, dismissals, real names, phones or locations were present in the ZIP. These tables fill through actual interactions. Location and profile forms already persist owner-entered details. A missing source address is shown as unavailable rather than fabricated.

## Repeat on this Mac

```bash
npx supabase migration up --local
.venv/bin/python scripts/connect_archive_storefront.py
.venv/bin/python scripts/verify_archive_app.py
.venv/bin/python scripts/verify_demo.py
.venv/bin/python scripts/verify_gateway.py
```

The importer is local-only, additive and rerunnable: deterministic IDs and `ON CONFLICT DO NOTHING` preserve edits, exchanges and original team records. It creates private per-store archive login credentials in `Private/operator/archive-demo-credentials.json` with owner-only permissions. Existing team logins can inspect the entire archive through the read-only explorer without switching accounts.

Prerequisite on another machine: recover the supplied ZIP, rebuild the isolated models and run `load_archive_lab.py` as described in `ARCHIVE_RECOVERY.md`. Apply migrations first. Private data is deliberately not distributed by Git or GRC. `DATA_SOURCES.json` and `AGENTS.md` provide portable discovery for other agents.

## Limits that remain

The dataset is synthetic, stock is historical, and model evaluation is development evidence. The learned classifier's long-inactivity failure is not fixed by this data bridge. Real retailer locations, real exchange outcomes, independent ML validation, permanent hosting, live POS integration, and participant usability evidence remain outstanding.
