#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/uvicorn scripts.team_gateway:app --host 127.0.0.1 --port 8787 &
gateway_pid=$!
trap 'kill "$gateway_pid" 2>/dev/null || true' EXIT INT TERM
cloudflared tunnel --url http://127.0.0.1:8787 --no-autoupdate --protocol http2
