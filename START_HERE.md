# Jiran — start here

**Everything for this project is now under `/Users/zoro/Projects/Jiran`.** Open `Jiran.code-workspace` in VS Code, or open this folder in Finder. `/Users/zoro/Projects/ISDIA` is a compatibility link to this same folder, not another project.

## Project map

| Location | What belongs here |
|---|---|
| `frontend/` | React app, SVG icons and account/inventory interface |
| `supabase/` | Database configuration and migrations |
| `ml_backend/` | Live ML pipeline and isolated archive-research code |
| `scripts/`, `tests/` | Startup, recovery, integration and browser checks |
| `docs/` | Current operational and evaluation explanations |
| `paper/`, `research/`, `architecture/`, `dashboard/` | Paper drafts, source research and presentation materials |
| `improvements.md`, `updates.md` | Improvement list and implementation record |
| `REMAINING.md`, `HANDOFF.md` | Prioritized remaining work and how to resume |
| `.grc/` | GRC project state, tasks, events and generated local dashboard |
| `Private/` | Local-only archives, data, operator credentials, reports, screenshots and historical checkouts |
| `Deployment/pages/` | Separate Git checkout that publishes the compiled Pages site |

`Private` and `Deployment` are visible shortcuts to hidden local storage inside this folder. Neither is included in the public source Git repository or scanned into GRC. Historical clones are retained under `Private/reference` and `Private/history`; they are not active source trees.

## Open the application and tools

| Tool | Address |
|---|---|
| Team application | https://pusliqour.github.io/jiran/ |
| Local frontend | http://127.0.0.1:5173 |
| Supabase Studio | http://127.0.0.1:54323/project/default/editor |
| Recovered research data | http://127.0.0.1:54323/project/default/editor?schema=jiran_archive_lab |
| Live ML health | http://127.0.0.1:8001/ |
| Synthetic research API | http://127.0.0.1:8003/docs |
| GRC dashboard | Open `GRC_DASHBOARD.html` locally |

The public site currently depends on this Mac, Docker, the Python gateway and the temporary Cloudflare tunnel staying online. It is not a hosted Supabase cloud project.

## Credentials and data

- Team login credentials: **`Private/operator/team-demo-credentials.json`**. This file is private and is not pushed to Git or GRC.
- Existing operational Excel source: `Private/reference/original-ml-repository/data/real/`. Its real-world authenticity is still unconfirmed.
- Received spreadsheet copies: `Private/sources/received-spreadsheets/`.
- Original user ZIP: `Private/archives/Jiran-user-20261110.zip`.
- Recovered raw data, manifests, DuckDB, artifacts and exact metrics: `Private/recovery/20261110/`.
- Original full transaction CSV: `Private/recovery/20261110/nested/data/transactions.csv`.
- Recovered synthetic research workspace: `Private/recovery/20261110/lab/`.
- Screenshots, earlier operator notes and evidence: `Private/operator/`.
- Source-only historical export snapshots: `Private/history/`; older archives: `Private/archives/`.

The recovered archive is explicitly generated data. Its 50-store research schema is separate from the three-store public demo. Its high policy-agreement F1 is not real-world validation, and the model still fails the inactivity stress scenario.

## Start or resume work

1. Read `REMAINING.md` and the latest `.grc` context before changing code.
2. Start Docker Desktop, then run `bash scripts/run-local.sh` from this folder for the local app and main ML service.
3. Studio is a separate existing container: `docker start jiran-studio-local` if needed.
4. The team gateway runs with `.venv/bin/uvicorn scripts.team_gateway:app --host 127.0.0.1 --port 8787`; tunnel instructions are in `docs/TEAM_DEMO.md`.
5. Research API:

```bash
ARCHIVE_LAB_DIR="$PWD/Private/recovery/20261110/lab" \
.venv/bin/uvicorn archive_lab_api:app --app-dir ml_backend \
  --host 127.0.0.1 --port 8003 --no-access-log
```

Old project, Downloads, Documents and Desktop paths have compatibility links. Existing processes, virtual-environment launchers and Docker setup continue to use them where necessary. Do not delete these links until startup paths have been migrated and tested. Nothing was deleted during consolidation.

## Git and GRC

- Main source remote: `fork` → `pusliqour/capstone_oscorp`.
- Current source branch: `recovery/jiran-archive-20261110`.
- Pages remote: `pusliqour/jiran`, branch `main`, in `Deployment/pages/`.
- GRC is attached to this canonical folder and contains completed milestones, remaining tasks and a current handoff.
- Commit source, documentation, tests, migrations and durable GRC metadata. Keep passwords, environment files, raw data, reports derived from private data, generated models and nested repositories local.
