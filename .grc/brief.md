# Jiran — current project brief

Updated 11 November 2026. Read AGENTS.md and DATA_SOURCES.json before assuming data is absent.

The canonical source is /Users/zoro/Projects/Jiran. The user supplied Jiran.zip and explicitly authorized using its generated data in the app. The original three team stores are preserved. Fifty labelled synthetic archive storefronts now add 5,960 inventory records, 9,100 daily aggregate orders, 1,013,393 daily sales details and 500 demonstration listings. Source research tables remain in jiran_archive_lab. Signed-in users can browse them through /data-explorer; this is no longer isolated-only recovery.

Exchange transitions use the checked exchange_action RPC. Seller acceptance reserves listing stock; two-party completion atomically moves inventory, updates listing stock, logs actions and is replay-safe. Database aggregation prevents sales/category charts truncating at the REST row limit. Private retailer profiles stay isolated; a separate business directory exposes only store fields.

Full-history sales totals match source CSV. Integration checks cover isolation, approvals, reservations, cancellation, dismissals, stock conservation, repeated completion and rollback. Browser checks cover archive search/history/pagination/mobile fit, marketplace names, archive account analytics/inventory and account-management workflows. Repeat instructions are in docs/ARCHIVE_APP_CONNECTION.md.

Private files are at Private/ locally and intentionally excluded from Git and GRC scans. Another computer needs those assets separately. Data-origin flags and file locations are in DATA_SOURCES.json. Never invent real addresses, phones, retailer identities, exchange history or account activity: they were not in the ZIP.

Outstanding: stable hosting instead of the Mac/temporary tunnel; original Excel provenance; archive classifier inactivity/OOD failure; independent forecasting and business outcome validation; usability participants and paper evidence. Historical synthetic results are not current trading activity or independent business accuracy.


Latest contact update: user requested web scraping instead of fictional filler. Fifty public business references from official Al Maya/Choithrams pages now supply demo location/contact fields. Source links, dates, hashes, real business names and phone/email scope are retained in data/public-businesses.json and Supabase business_references. This is reference data only: the businesses did not supply generated inventory and are not verified participants. Full postal addresses/coordinates are not inferred from locality labels. Original team accounts and owner edits were preserved. See DATA_SOURCES.json and docs/ARCHIVE_APP_CONNECTION.md.
