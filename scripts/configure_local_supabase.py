#!/usr/bin/env python3
"""Write ignored local environment files from a running Supabase stack."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
result = subprocess.run(
    ["npx", "supabase", "status", "-o", "env"],
    cwd=ROOT,
    text=True,
    capture_output=True,
    check=True,
)
values = {}
for line in result.stdout.splitlines():
    match = re.match(r"^([A-Z_]+)=(.*)$", line.strip())
    if match:
        values[match.group(1)] = match.group(2).strip().strip('"')

api_url = values.get("API_URL") or values.get("SUPABASE_URL")
anon = values.get("ANON_KEY") or values.get("PUBLISHABLE_KEY")
service = values.get("SERVICE_ROLE_KEY") or values.get("SECRET_KEY")
if not all((api_url, anon, service)):
    raise SystemExit("Could not obtain API_URL, ANON_KEY, and SERVICE_ROLE_KEY from local Supabase")

files = {
    ROOT / "frontend/.env.local": (
        f"VITE_SUPABASE_URL={api_url}\n"
        f"VITE_SUPABASE_ANON_KEY={anon}\n"
        "VITE_ML_API_URL=http://127.0.0.1:8001\n"
    ),
    ROOT / "ml_backend/.env": (
        f"SUPABASE_URL={api_url}\n"
        f"SUPABASE_KEY={service}\n"
        "ML_API_URL=http://127.0.0.1:8001\nOUTPUT_DIR=./ml_outputs\nPOLL_INTERVAL=10\n"
    ),
}
for path, content in files.items():
    path.write_text(content, encoding="utf-8")
    os.chmod(path, 0o600)
print("Configured ignored owner-only local environment files.")
