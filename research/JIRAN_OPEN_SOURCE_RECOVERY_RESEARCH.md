# Jiran recovery: open-source alternatives to hosted Supabase and Square

Research date: 2026-10-24

## Recommendation in one sentence

Run **Supabase locally with the official CLI and a Docker-compatible runtime**, keep the existing `@supabase/supabase-js` client and SQL schema, and use Jiran's **already-implemented manual CSV/XLSX inventory and order import** as the default POS adapter; keep Square as an optional demo integration (prefer its free Sandbox or a thin direct API adapter) rather than replacing it with an entire POS/ERP.

## Why this is the minimum-change path

The current code is coupled to Supabase's API surface, not merely PostgreSQL:

- `frontend/src/supaBase/Client.js` creates an `@supabase/supabase-js` client from only `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`.
- Authentication uses `supabase.auth` and auth-state listeners (`frontend/src/context/AuthContext.jsx`).
- Pages make extensive PostgREST-style calls such as `.from(...).select/insert/upsert` and invoke Edge Functions with `supabase.functions.invoke(...)`.
- Existing POS functions use Supabase service-role access and current Jiran tables (`frontend/Jiran@Supabase/supabase/functions/`).
- The UI already parses CSV/XLSX with Papa Parse and SheetJS, validates/maps inventory and order columns, and switches to a `manual` provider (`frontend/src/pages/Inventory.jsx`, especially lines 1060-1316 and 2060-2109).
- A local recovery migration already exists at `supabase/migrations/202610240001_local_recovery.sql`.

Changing only the local Supabase URL/key preserves the JavaScript API, auth semantics, PostgREST/RLS model, database, and Edge Function contract. Every other backend alternative requires rewriting the data layer and at least part of auth.

## Backend alternatives

| Option | License / deployment | Auth / DB / realtime / functions | Fit with current Supabase API | Setup burden | Verdict |
|---|---|---|---|---|---|
| **Official Supabase local CLI** | Supabase repository: Apache-2.0. Requires Supabase CLI plus Docker-compatible runtime; `supabase start` runs a local development stack. | Yes: GoTrue Auth, PostgreSQL/PostgREST, Realtime, Storage, Edge Functions, Studio. | **Native compatibility** with `supabase-js`, current RLS/SQL, and function invocation. | **Low** for a local capstone demo. Local CLI stack is explicitly not production-hardened. | **Best recovery choice.** |
| **Supabase self-hosted Docker** | Apache-2.0 components; official Docker Compose route. | Same core capabilities, but managed-only features such as branching, managed backups/PITR, and some analytics are absent. | **Native compatibility**. | Medium/high operational burden: security, upgrades, DB maintenance, backups, monitoring, HA are yours. | Best if Jiran must be reachable as a persistent deployment; unnecessary for a laptop demo. |
| **Appwrite self-hosted** | BSD-3-Clause; Docker or official Kubernetes Helm chart. | Auth, document databases, storage, functions, messaging/realtime. | **Incompatible SDK/data model.** Supabase query chains, PostgreSQL schema/RLS, auth calls, and Edge Functions must be adapted or rewritten. | Medium to deploy, **high migration effort**. | Good general BaaS, poor minimal-change recovery. |
| **PocketBase** | MIT; one small executable. | Embedded SQLite, built-in auth, files, realtime subscriptions, REST-ish API and admin UI. | No PostgreSQL/PostgREST/RLS compatibility; auth and function model differ. | Very low server setup, **high app rewrite**. Docs warn that pre-1.0 backward compatibility is not guaranteed and do not recommend it for production-critical apps without accepting manual migrations. | Excellent prototype backend, wrong migration target for Jiran. |
| **Directus + PostgreSQL** | Current `main` is **MSCL-1.0-GPL**, a source-available/non-compete license that becomes GPL-3.0 after four years; it should not be described as unconditionally OSI-open-source. | Auth, files, REST/GraphQL APIs, realtime/WebSockets, automations/flows over PostgreSQL. | Can retain PostgreSQL tables, but API, auth/roles, RLS assumptions, SDK, and Edge Functions are different. | Medium setup, medium/high rewrite. | Useful headless admin/API layer, not a drop-in Supabase replacement; license caveat. |
| **Plain PostgreSQL** | PostgreSQL License. | Database only; auth API, PostgREST, realtime, object storage, and Edge Functions are absent unless separately assembled. | SQL tables survive, but browser code cannot safely connect directly and almost all Supabase calls need a new FastAPI/data-access layer. | Low DB setup but **highest application plumbing burden**. | Only sensible for a deliberate backend redesign, not emergency recovery. |

### Backend conclusion

Use **CLI local Supabase for demo/development** or **official Supabase Docker self-hosting for a persistent server**. Appwrite, PocketBase, Directus, and plain PostgreSQL are alternatives in product category, but not protocol-compatible alternatives. They would increase risk and code churn without improving the capstone recovery.

## Square/POS options

| Option | License / nature | Integration/API fit | Setup and Jiran change | Verdict |
|---|---|---|---|---|
| **No replacement: Jiran manual CSV/XLSX adapter** | Existing Jiran feature; Papa Parse (MIT) and SheetJS Community Edition are already dependencies. | Already normalizes inventory and orders into Jiran's current Supabase tables and `manual` provider. Can ingest exports from nearly any POS. | **Lowest burden; almost no code change.** Use sample/demo exports and preserve current analytics/ML flow. | **Default recommendation.** |
| **Square Sandbox, optional** | Square is proprietary, but its Sandbox is a **free, isolated test environment** with test seller accounts/methods and a separate API base URL. | Closest behavior to the current Square mapping. Current implementation routes Square through hosted Apideck; a direct Square adapter can call Catalog, Inventory, and Orders APIs and emit the same internal records. | Low/moderate if credentials are available. Replace Apideck-specific OAuth/vault code or keep it disabled. | Best live-integration demo; a new POS is not required. |
| **Thin `PosAdapter` boundary** | Project code; can be MIT/Apache if published. | Define a normalized contract (`catalog`, `inventory counts`, `orders`) and implement `CsvAdapter` first, `SquareSandboxAdapter` second. | Small, contained refactor; current DB remains canonical. | Best architectural improvement without changing platforms. |
| **Medusa** | Core repository is MIT except explicitly identified Enterprise Edition material. Headless commerce backend, not a turnkey physical POS. | Strong product/order/inventory and sales-channel concepts, APIs, PostgreSQL ecosystem; but Jiran needs a new adapter and another service. It does not replace Supabase auth/data by itself. | Medium/high. | Consider only if the capstone needs headless commerce, not just POS data ingestion. |
| **ERPNext** | GPL-3.0. Full ERP with POS; Frappe auto-generates REST CRUD endpoints for DocTypes. | Rich products, stock, sales invoices/POS; adapter can poll REST or consume exports. Models do not match Square/Jiran directly. | High: substantial stack and ERP configuration. | Good real deployment candidate, excessive for recovery. |
| **Odoo Community** | Core Odoo repository is LGPL-3.0; bundled components can have other compatible licenses. Web-browser POS, inventory, products, reporting, temporary-offline operation. | Mature ERP/POS but requires XML-RPC/JSON-RPC/JSON-2 or custom module/export mapping. | High server/configuration burden and medium/high adapter effort. | Strong business suite, poor minimal-change path. |
| **uniCenta oPOS** | GPL-3.0 project distribution (with separately licensed bundled dependencies); Java desktop POS. | Retail/hospitality POS backed by a local DB, but no Square-compatible public API. Integration is likely DB/CSV export mapping. | Medium app installation, medium/high integration. Public GitHub copies are not clearly the canonical current distribution, so verify provenance/version before adoption. | Only if a real checkout terminal is required. |
| **Floreant POS** | MRPL 1.2 (Mozilla Public License 1.1 plus permitted attribution clause); Java restaurant POS. | Restaurant-focused; generally local DB/export rather than a modern Square-compatible API. | Medium/high integration; domain mismatch for general inventory/resource allocation. | Not recommended for Jiran recovery. |

### Does Square actually need replacement?

**No.** Jiran's essential value is inventory/resource allocation and ML insight, not card acquiring. A self-hosted POS cannot self-host the banking/payment rails anyway. For a capstone demonstration, use one of these modes:

1. **Offline/manual demo (recommended):** import deterministic CSV/XLSX inventory and orders using the existing UI.
2. **Live API demo:** use Square Sandbox, which Square documents as free and isolated. Point a direct adapter at `https://connect.squareupsandbox.com`, or retain the existing integration only when hosted Apideck/Square credentials are available.
3. **Future real POS:** map ERPNext/Odoo/Medusa exports or APIs through the adapter without changing Jiran's frontend or canonical database.

## Recommended minimal-change architecture

```text
React/Vite
  └─ existing @supabase/supabase-js API (unchanged)
       └─ local Supabase CLI stack on Docker-compatible runtime
            ├─ GoTrue Auth
            ├─ Postgres + PostgREST + RLS
            ├─ Realtime (available; use only where already needed)
            ├─ Edge Functions
            └─ current Jiran tables/migration

POS ingestion boundary
  ├─ CsvXlsxAdapter (default; already largely implemented)
  ├─ SquareSandboxAdapter (optional; direct API, no Apideck dependency)
  └─ future ERPNext/Odoo/Medusa adapter
       ↓ normalized products / inventory / orders
  current Supabase tables
       ↓
  React analytics + FastAPI ML service (unchanged)
```

### Activation order

1. Use the project-root `supabase/` directory as the canonical local project; ensure migrations and any needed functions are under that one directory (functions currently also appear under `frontend/Jiran@Supabase/supabase/functions`).
2. Install the Supabase CLI and a Docker-compatible runtime; run `supabase start` from the repository root.
3. Apply/reset the local migration and use the CLI's emitted API URL and anon key in `frontend/.env`.
4. Serve the existing FastAPI ML service independently; it does not depend on Supabase in the inspected `app.py`.
5. Make manual CSV/XLSX import the visible default and feature-flag/hide Square connection when credentials are absent.
6. If a live POS integration is required, add a direct Square Sandbox adapter that writes the same normalized records. Do **not** replace the backend or install a full ERP merely to unblock the demo.

### Small schema/code caveats

- Current imported order validation allows only `source` values `square` and `manual`. For zero change, external POS imports should be treated as `manual`; for a generalized adapter, expand the constraint/source enum in one migration.
- `pos-switch-provider` currently accepts only `manual` or `square`, which reinforces using `manual` as the generic recovery mode.
- Local CLI is for development/testing, not an internet-exposed production deployment. Use the official self-hosted Docker path plus hardening/backups if external access is required.

## Sources

### Supabase and backend alternatives

- Supabase local development/CLI: https://supabase.com/docs/guides/local-development
- Supabase self-hosting and operational responsibilities: https://supabase.com/docs/guides/self-hosting
- Supabase repository/license: https://github.com/supabase/supabase
- Appwrite self-hosting: https://appwrite.io/docs/advanced/self-hosting
- Appwrite repository/license: https://github.com/appwrite/appwrite
- PocketBase capabilities and pre-1.0 warning: https://pocketbase.io/docs/
- PocketBase repository/license: https://github.com/pocketbase/pocketbase
- Directus repository/current license: https://github.com/directus/directus/blob/main/license
- PostgreSQL license: https://www.postgresql.org/about/licence/

### POS/commerce

- Square Sandbox overview and free isolated environment: https://developer.squareup.com/docs/devtools/sandbox/overview
- Square Orders API: https://developer.squareup.com/reference/square/orders-api
- Square Catalog API: https://developer.squareup.com/reference/square/catalog-api
- Square Inventory API: https://developer.squareup.com/reference/square/inventory-api
- Medusa repository/license: https://github.com/medusajs/medusa/blob/develop/LICENSE
- Medusa product/inventory/sales-channel overview: https://medusajs.com/
- ERPNext repository/license: https://github.com/frappe/erpnext
- Frappe generated REST API: https://docs.frappe.io/framework/user/en/api/rest
- ERPNext POS documentation: https://docs.frappe.io/erpnext/user/manual/en/point-of-sale
- Odoo POS documentation: https://www.odoo.com/documentation/19.0/applications/sales/point_of_sale.html
- Odoo Community repository/license: https://github.com/odoo/odoo/blob/19.0/LICENSE
- uniCenta public source mirror and included GPL-3.0 text: https://github.com/DeanBeer/uniCenta-oPOS
- Floreant official site: https://floreant.org/
- Floreant repository/license: https://github.com/floreantpos/floreantpos/blob/floreantpos-2.0/LICENSE
