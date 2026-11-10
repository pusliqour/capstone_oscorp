# Resume Jiran here

**Canonical folder:** `/Users/zoro/Projects/Jiran`.
**Branch:** `recovery/jiran-archive-20261110`.
**Entry point:** `START_HERE.md`.
**Current priorities:** `REMAINING.md` and the `.grc` task board.

## Completed

- Working GitHub Pages team app, local Supabase and authenticated Python gateway through a temporary HTTPS tunnel.
- Three account-scoped demo stores with 175 inventory entries, 802 orders and 3,737 order lines.
- Account/store profiles, location and product CRUD, typed-name deletion, password changes, preferences, accessible dialogs, mobile forms and consistent SVG icons.
- Live main ML pipeline with atomic publication to the dashboard and honest evaluation limits.
- Supabase Studio at `http://127.0.0.1:54323/project/default/editor`.
- Recovery of the user-supplied ZIP: 2,555 products, 50 stores, 5,960 stock rows and 17,025,416 generated transaction lines. Separate `jiran_archive_lab` schema has the catalog, stock, 1,013,393 daily aggregates, forecasts, classifications and metrics.
- Rebuilt isolated research models/API, future-data cutoff tests, complete-store classifier holdout, rolling temporal forecast evaluation and explicit model-disagreement flags.
- Consolidated current source, private material, historical checkouts and deployment into one folder. Old paths are compatibility links. Private material is excluded from source Git and GRC scans.

## Important limits

- Data provenance remains a gate: original three-store Excel authenticity is unconfirmed; the 50-store archive is generated data.
- The research model fails the 365-day-inactivity scenario. High policy-agreement F1 is not independent business accuracy. It was not promoted into the live main model.
- The temporary tunnel requires the Mac and services to remain running. Its hostname changes if recreated.
- Historical paper/research material is preserved; it is draft evidence, not publication acceptance or a participant study.

## Where material lives now

- Credentials and screenshots: `Private/operator/`.
- Original ZIPs: `Private/archives/`.
- Research recovery and exact metrics: `Private/recovery/20261110/`.
- Original ML checkout and operational Excel source: `Private/reference/original-ml-repository/`.
- Older preview and export snapshots: `Private/reference/` and `Private/history/`.
- Active Pages checkout: `Deployment/pages/`.
- Current operational docs: `docs/`; all-improvements list: `improvements.md`; change record: `updates.md`.

The private consolidation journal is `Private/consolidation-manifest.json`. No content was deleted.

## Repeat checks

```bash
cd /Users/zoro/Projects/Jiran
.venv/bin/python -m unittest discover -s ml_backend/tests -v
.venv/bin/python scripts/verify_demo.py
.venv/bin/python scripts/verify_account_management.py
npm --prefix frontend run build
```

Browser workflow:

```bash
PLAYWRIGHT_MODULE=/Users/zoro/.cache/uv/archive-v0/QM3HCTxcuiJa0OVA/playwright/driver/package \
node tests/account_management.cjs
```

Run destructive checks only on disposable accounts. Their helper is `scripts/ux_fixture.py`; never delete the three team stores as a smoke test.

The default Supabase Docker `project_id` remains `ISDIA` to preserve existing containers and volumes; this is an internal identifier, not a second workspace. Existing `.venv` launcher paths remain valid through the old source-path symlink.

## Next action

Use GRC at this canonical folder, review the first outstanding task in `REMAINING.md`, and choose the stable-hosting/data-validation work before claiming production readiness. Commit source/docs/tests/GRC metadata and push `fork`; publish only compiled assets from `Deployment/pages` when changing the live frontend. Never push `Private`, `.env` files, datasets or models.
