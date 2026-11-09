# Resume Jiran here

## Checkpoint

Working source: `/Users/zoro/Projects/ISDIA`, branch `recovery/isdia-paper`.
User's source fork: `https://github.com/pusliqour/capstone_oscorp` (public; source only).
Pages checkout: `/Users/zoro/Projects/jiran-pages-live`, branch `main`.
The user requested that all current work be committed/pushed so the next session can resume.

## Completed and verified

- Connected Pages frontend to local Supabase through a Python session-wrapping gateway and HTTPS tunnel.
- Three team accounts loaded with 175 inventory rows, 802 orders and 3,737 order lines; private credentials remain in `~/Documents/Jiran/team-demo-credentials.json`.
- ML and forecast improvements, development evaluation and limitations: `docs/ML_CHANGES.md`.
- New account/store Settings screen, editable full name/phone/store name, create/delete store, create/edit/remove primary location, current-password changes and preferences.
- Transactional, authenticated RPCs for account and product management; typed-name deletion confirmation; historical orders retained when deleting products.
- Product create/edit/delete UI, accessible dialogs, contextual success/error states and recent-account activity.
- Emoji graphics replaced with Lucide SVG icons through `frontend/src/components/Icon.jsx`.
- Account-management SQL migrations through `202611090006_profile_name_validation.sql` applied locally.
- Backend disposable-account integration passed directly and through the public HTTPS gateway, including password change and cross-account denial.
- Browser workflow passed creation/editing/deletion, location 0/0, unsaved cancellation, password change, store deletion and mobile layout.
- Production frontend build passed. Existing ML suite has 18 passing tests from the preceding phase.
- Full changes: `updates.md`.

## Immediate next step

The Settings/SVG frontend was published to Pages as `9bbae93`. The live landing page shows 33 SVG icons with no emoji text, and the password toggle was verified. Run the public-site management browser pass; the local browser and public API integration checks already passed. The commands below reproduce the deployment.

```bash
cd /Users/zoro/Projects/ISDIA
JIRAN_PUBLIC_SUPABASE_URL=https://navy-genre-bind-fleece.trycloudflare.com \
JIRAN_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_jiran_team_gateway \
VITE_TEAM_DEMO=true bash scripts/build-pages.sh
```

Copy only `frontend/dist/` into the Pages checkout, retaining `.git` and old hashed assets for cached clients. Review, commit and push `main`. Do not copy environment files, credentials, model artifacts or spreadsheets. Verify live Settings, CRUD and SVG icons with a disposable account.

## Running services at handoff

- Supabase local API: `http://127.0.0.1:54321` (Docker)
- Frontend dev: `http://127.0.0.1:5173`
- Private ML API and watcher: `http://127.0.0.1:8001`
- Python gateway: `http://127.0.0.1:8787` (`scripts/team_gateway.py`)
- HTTPS tunnel: `https://navy-genre-bind-fleece.trycloudflare.com`
- Team site: `https://pusliqour.github.io/jiran/`

The gateway was restarted for account endpoints; old browser sessions may need a fresh sign-in. Keep the Mac awake and all services running. A recreated quick tunnel gets a different URL and requires a frontend rebuild/deployment. Gateway sessions are held in memory.

## Repeat checks

```bash
.venv/bin/python scripts/verify_account_management.py
JIRAN_MANAGEMENT_URL=https://navy-genre-bind-fleece.trycloudflare.com .venv/bin/python scripts/verify_account_management.py
PLAYWRIGHT_MODULE=/Users/zoro/.cache/uv/archive-v0/QM3HCTxcuiJa0OVA/playwright/driver/package node tests/account_management.cjs
.venv/bin/python scripts/verify_demo.py
npm --prefix frontend run build
```

Browser tests create and clean `uxbrowser-*` accounts, using an owner-only temporary credential file. Never run destructive tests against the three team stores. If interrupted, run `.venv/bin/python scripts/ux_fixture.py cleanup`.

## Important limits

- Raw source data is unconfirmed. Six existing Excel files came from `../jiran-ml/data/real`, repo `M4MD-M7SN/jiran-ml`, commit `4adc1ee`. All identify openpyxl as workbook creator. The user will confirm their authenticity later. No raw data belongs in this public source fork.
- Perfect development F1 is agreement with known policy labels after training-only simulations, not independent business accuracy. Forecast MAE improved, but RMSE worsened. More independent stores/periods and reviewed labels are still needed.
- Manual/imported inventory refresh still invokes the old POS sync handler; change it to a local reload. POS connection restoration is separate.
- Unsaved edits are guarded through Settings header links and browser reload/close, not browser Back navigation.
- Email changes, full login-account deletion, multiple stores and uploaded-document management remain outside this update.
- No passwords, service keys, `.env` files, raw data, private evaluation outputs or trained models should be committed or pushed.
