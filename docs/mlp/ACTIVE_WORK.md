# Active ownership — 12 November

- This Codex instance: A1/A5/A6/A8/A9/A11, manuscript (`paper/jiran_isdia_2027.tex`), paper figures/evidence, `scripts/build_manuscript_evidence.py`, and manuscript validation summary.
- User is creating another instance for Section B. Keep B implementation/evidence in separate files; coordinate before touching the manuscript.
- A7 and A12 excluded by user. A2/A3/A4/A10 already complete. No simulation/model reruns for the manuscript update.
- Canonical MLP is `/Users/zoro/MLP`. Read fresh before scoped updates; preserve concurrent entries.

- Claude instance (12 Nov, user goal "fix A on the ML side, not the paper; prune Section B to A-overlaps"): ML code/evidence only. Owns `ml_backend/inventory_policy.py`, `ml_backend/stock_planning.py`, `ml_backend/app.py` (order-cycle input, C1), new tests `ml_backend/tests/test_edge_guards.py`, `ml_backend/simulation/evaluate_alerts.py` tuning/sensitivity flags writing NEW files `output/results/alerts_tuned*.json` (existing results untouched), `ml_backend/MODEL_CARD.md`. Will not touch `paper/` or `scripts/build_manuscript_evidence.py`. Will edit the CONCERNS block of `/Users/zoro/MLP` at the end (Section B pruning) after a fresh read.

- 12 Nov 04:30 handover: Codex stopped at 03:10. User reassigned its work to Claude, then said the paper is not wanted. Paper files (`paper/`, `scripts/build_manuscript_evidence.py`) are left UNCOMMITTED as they stand (Codex's edits plus a Claude update for A6/A8/A9 that compiles to 20 pages). No further paper work unless the user asks. Concerns are tracked in `/Users/zoro/MLP`; ML evidence in `ml_backend/MODEL_CARD.md`; report v5 at https://claude.ai/artifact/QzYuvSV1ENeL2an5F6SNNM.
