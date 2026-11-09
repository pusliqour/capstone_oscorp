"""Populate local demo accounts and business data; credentials stay outside Git."""
import json
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ml_backend'))
from supabase import create_client
from storefront_demo import STORE_LOGIN_EMAILS, STORE_NAMES, build_storefront_snapshot, push_storefront_snapshot
import pandas as pd

values = dict(line.split('=', 1) for line in (ROOT/'ml_backend/.env').read_text().splitlines() if '=' in line)
url = values['SUPABASE_URL']
if url not in ('http://127.0.0.1:54321', 'http://localhost:54321'):
    raise SystemExit('This bootstrap is restricted to local Supabase.')
client = create_client(url, values['SUPABASE_KEY'])
users = {u.email: u for u in client.auth.admin.list_users()}
credential_path = Path.home()/'Documents/Jiran/team-demo-credentials.json'
credential_path.parent.mkdir(parents=True, exist_ok=True)
credentials = json.loads(credential_path.read_text()) if credential_path.exists() else {}
for store, email in STORE_LOGIN_EMAILS.items():
    password = credentials.get(email, {}).get('password') or secrets.token_urlsafe(20)
    attrs = {'password': password, 'email_confirm': True, 'user_metadata': {'role': 'retailer', 'full_name': STORE_NAMES[store]+' Demo'}}
    if email in users:
        user = client.auth.admin.update_user_by_id(users[email].id, attrs).user
    else:
        user = client.auth.admin.create_user({'email': email, **attrs}).user
    client.table('profiles').upsert({'id': user.id, 'role': 'retailer', 'full_name': STORE_NAMES[store]+' Demo'}).execute()
    client.table('retailer_profiles').upsert({'id': user.id, 'user_id': user.id, 'shop_name': STORE_NAMES[store], 'store_id': store}).execute()
    credentials[email] = {'password': password, 'store': STORE_NAMES[store]}
# Open with owner-only permissions before writing passwords.
fd = os.open(credential_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
os.fchmod(fd, 0o600)
with os.fdopen(fd, 'w') as stream:
    json.dump(credentials, stream, indent=2)
data = ROOT/'ml_backend/training/data'
snapshot = build_storefront_snapshot(pd.read_csv(data/'transactions.csv'), pd.read_csv(data/'stock.csv'), pd.read_csv(data/'products.csv'))
print(json.dumps(push_storefront_snapshot(client, snapshot), indent=2))
print(f'Credentials saved to {credential_path}; valid on this local backend only.')
