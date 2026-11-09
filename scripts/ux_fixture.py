"""Create/clean the disposable account used by browser management tests."""
import json
import os
from pathlib import Path
import secrets
import sys
from supabase import create_client
ROOT=Path(__file__).resolve().parents[1]
FILE=Path('/private/tmp/jiran-ux-fixture.json')
values=dict(line.split('=',1) for line in (ROOT/'ml_backend/.env').read_text().splitlines() if '=' in line)
assert values['SUPABASE_URL']=='http://127.0.0.1:54321','Local fixtures only'
client=create_client(values['SUPABASE_URL'],values['SUPABASE_KEY'])
if sys.argv[1]=='cleanup':
    if FILE.exists():
        fixture=json.loads(FILE.read_text());uid=fixture['id']
        users={u.id:u for u in client.auth.admin.list_users()}
        if uid in users:
            if not users[uid].email.startswith('uxbrowser-'):raise SystemExit('Not a browser-test account')
            stores=client.table('retailer_profiles').select('store_id').eq('id',uid).execute().data
            for store in stores:client.table('ml_inventory').delete().eq('store_id',store['store_id']).execute()
            client.table('ml_inventory_predictions').delete().eq('retailer_id',uid).execute()
            client.table('ml_inventory_transfer_recommendations').delete().or_(f'from_retailer_id.eq.{uid},to_retailer_id.eq.{uid}').execute()
            connections=client.table('pos_connections').select('id').eq('retailer_id',uid).execute().data
            for connection in connections:client.table('connection_intelligence').delete().eq('pos_connection_id',connection['id']).execute()
            client.auth.admin.delete_user(uid)
        FILE.unlink()
    print('Disposable browser fixture removed')
elif sys.argv[1]=='create':
    if FILE.exists():raise SystemExit('Clean the existing browser fixture before creating another')
    email='uxbrowser-'+secrets.token_hex(5)+'@jiran.test';password=secrets.token_urlsafe(18)
    user=client.auth.admin.create_user({'email':email,'password':password,'email_confirm':True,'user_metadata':{'role':'retailer','full_name':'Research Test User'}}).user
    fd=os.open(FILE,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as output:json.dump({'id':user.id,'email':email,'password':password},output)
    print('Disposable browser fixture created')
else:raise SystemExit('Use create or cleanup')
