#!/usr/bin/env bash
# Build a connected Pages artifact after a hosted Supabase endpoint is configured.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${JIRAN_PUBLIC_SUPABASE_URL:?Set the reachable HTTPS Supabase URL}"
: "${JIRAN_PUBLIC_SUPABASE_ANON_KEY:?Set its public anon or publishable key}"
case "$JIRAN_PUBLIC_SUPABASE_URL" in
  https://localhost*|https://127.*|https://example.invalid*) echo 'A real HTTPS backend is required' >&2; exit 1;;
  https://*) ;;
  *) echo 'GitHub Pages requires a reachable HTTPS backend' >&2; exit 1;;
esac
case "$JIRAN_PUBLIC_SUPABASE_ANON_KEY" in
  sb_secret_*) echo 'Use a publishable/anon key, never a service key' >&2; exit 1;;
esac
JIRAN_PUBLIC_SUPABASE_ANON_KEY="$JIRAN_PUBLIC_SUPABASE_ANON_KEY" python3 - <<'PY'
import base64,json,os
key=os.environ['JIRAN_PUBLIC_SUPABASE_ANON_KEY']
if key.count('.')==2:
    payload=key.split('.')[1]
    claims=json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))
    if claims.get('role')!='anon':raise SystemExit('Frontend key must have the anon role')
elif not key.startswith('sb_publishable_'):
    raise SystemExit('Expected a publishable key or anon JWT')
PY
VITE_PUBLIC_DEMO=false VITE_BASE_PATH=/jiran/ \
VITE_SUPABASE_URL="$JIRAN_PUBLIC_SUPABASE_URL" \
VITE_SUPABASE_ANON_KEY="$JIRAN_PUBLIC_SUPABASE_ANON_KEY" \
npm --prefix frontend run build
cp frontend/dist/index.html frontend/dist/404.html
touch frontend/dist/.nojekyll
printf 'Connected Pages artifact ready in frontend/dist/\n'
