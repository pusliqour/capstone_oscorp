#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v docker >/dev/null || { echo "Docker is required" >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "Start Docker Desktop first" >&2; exit 1; }

if ! npx supabase status >/dev/null 2>&1; then
  npx supabase start --exclude studio,imgproxy,edge-runtime,logflare,vector,supavisor
fi
npx supabase migration up --local
python3 scripts/configure_local_supabase.py

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -r ml_backend/requirements.txt
fi
if [[ ! -d frontend/node_modules ]]; then
  npm --prefix frontend ci
fi

pids=()
cleanup() {
  for pid in "${pids[@]:-}"; do kill "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

(cd ml_backend && ../.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8001 --env-file .env) & pids+=("$!")
(cd frontend && npm run dev -- --host 127.0.0.1 --port 5173) & pids+=("$!")
python3 -m http.server 4174 --bind 127.0.0.1 & pids+=("$!")

echo "Jiran:     http://127.0.0.1:5173/"
echo "ML API:   http://127.0.0.1:8001/ (health reports model readiness)"
echo "Dashboard: http://127.0.0.1:4174/dashboard/"
echo "Press Ctrl-C to stop the three application processes. Supabase remains available."
wait
