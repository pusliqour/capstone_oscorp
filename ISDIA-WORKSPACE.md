# ISDIA / Jiran workspace map

This directory is both the recovered graduation-project repository and the working ISDIA-2027 paper package.

## Open first

- **Project dashboard:** `dashboard/index.html` (served at `http://127.0.0.1:4174/dashboard/` while the local server is running)
- **Paper PDF:** `paper/jiran_isdia_2027.pdf`
- **Editable paper source:** `paper/jiran_isdia_2027.tex`
- **Venue brief:** `research/ISDIA-venue-paper-brief.md`
- **Evidence register:** `research/ISDIA-source-register.md`
- **Verification:** `research/verification-report.md`
- **High-level architecture:** `architecture/jiran-high-level-architecture.html`
- **GRC:** `.grc/dashboard.html`

## Runtime

- Jiran frontend: `http://127.0.0.1:5173/`
- ML API: `http://127.0.0.1:8001/` — operational with AI explicitly null
- Supabase API: `http://127.0.0.1:54321/`
- Supabase Studio can be restored by restarting without the current exclusions if needed.

## Reproduce locally

```bash
./scripts/run-local.sh
```

Manual equivalent:

```bash
npx supabase start
python3 scripts/configure_local_supabase.py
python3 -m venv .venv
.venv/bin/pip install -r ml_backend/requirements.txt
(cd ml_backend && ../.venv/bin/uvicorn app:app --port 8001)
(cd frontend && npm ci && npm run dev)
python3 -m http.server 4174
```

The existing `start.sh` remains from the capstone and should be simplified in a later cleanup. Do not enable model predictions until a traceable dataset and compatible artifacts pass the evaluation gates in the paper.

## Submission-critical decisions

1. Confirm author order, corresponding author, and contact email.
2. Confirm with the organizer whether the supplied `svmult` package is the intended class for this LNNS paper.
3. Resolve the official website's venue inconsistency (Sofitel vs UOWD campus).
4. Obtain/approve a provenance-controlled dataset.
5. Run temporal and location holdouts; add results only after validation.
6. Ask the organizers directly for a historical best-paper list; none was publicly verifiable in this research pass.
