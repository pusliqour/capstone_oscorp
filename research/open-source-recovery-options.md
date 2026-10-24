# Recovery technology decision record

**Date:** 24 October 2026
**Decision:** Preserve Jiran's Supabase API contract through local/self-hosted Supabase; replace Square as a mandatory dependency with a source-neutral import boundary and tested ERPNext/Odoo CSV adapters.

## Hosted-state finding

The hostname configured in the tracked environment (`nbrhlujwzbfupsouylkg.supabase.co`) did not resolve during direct health and REST checks. This is evidence that the historical endpoint is currently unreachable, not proof that every historical backup has been destroyed. No historical rows were recovered.

The repository also tracked frontend and backend environment files, including a backend key. Those values must be considered exposed and rotated if the project is ever restored. The current branch removes them from tracking and replaces examples with local placeholders.

## Backend-as-a-service options

| Option | Open-source/self-hosted | Fit with current code | Migration cost | Decision |
|---|---|---:|---:|---|
| **Supabase self-hosted/local** | Yes; official Docker/CLI path | Exact JS SDK, Auth, REST, PostgreSQL and Storage contract | Lowest | **Selected** |
| Appwrite | Yes | Requires rewriting Supabase queries/auth/storage | Medium-high | Good future alternative, not minimal recovery |
| PocketBase | Yes | Simple local service but different query/auth model | Medium-high | Good small prototype alternative |
| Direct PostgreSQL + Keycloak/MinIO | Yes | Maximum control, several integration surfaces | High | Not appropriate for minor capstone recovery |

Official sources:

- Supabase self-hosting: https://supabase.com/docs/guides/self-hosting
- Supabase repository: https://github.com/supabase/supabase
- Appwrite repository: https://github.com/appwrite/appwrite
- PocketBase repository: https://github.com/pocketbase/pocketbase

## POS/resource-system options

Square is a proprietary hosted POS, not an open-source component. Replacing it with one project is not necessary for the paper contribution because Jiran is an allocation/intelligence layer rather than a POS.

| Option | Scope | Jiran integration approach | Decision |
|---|---|---|---|
| **ERPNext** | Open-source ERP, stock, warehouses, transactions | Normalize exported Stock Balance/Bin CSV | **Supported now** |
| **Odoo Community** | Open-source ERP framework and inventory modules | Normalize inventory export CSV | **Supported now** |
| uniCenta oPOS | Open-source POS | Future CSV/API adapter | Candidate |
| Existing spreadsheet | Source-neutral/manual | Jiran normalized CSV contract | Supported by design |

Official sources:

- ERPNext: https://github.com/frappe/erpnext
- Odoo: https://github.com/odoo/odoo
- uniCenta oPOS: https://github.com/unicenta/unicentaopos

## Why this is a minor upgrade rather than a derailment

- The React pages, Supabase client calls, tables, and exchange concepts remain intact.
- The database is moved from an expired hosted instance to the same open-source Supabase contract locally.
- Square becomes one optional source instead of the system boundary.
- ERP exports map into the same factual inventory fields used by the original application.
- AI remains downstream and null until data lineage and evaluation are restored.

## Implemented adapter

```bash
python3 tools/resource_import.py --source erpnext --input export.csv --output data/normalized/inventory.csv
python3 tools/resource_import.py --source odoo --input export.csv --output data/normalized/inventory.csv
```

The adapter performs schema validation and numeric validation and emits no predictions. Tests are in `tests/test_resource_import.py`.
