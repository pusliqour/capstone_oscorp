"""Integration checks against the populated local demo without exposing credentials."""
import json
from pathlib import Path
from supabase import create_client

ROOT=Path(__file__).resolve().parents[1]
def env(path):return dict(line.split('=',1) for line in path.read_text().splitlines() if '=' in line)
backend=env(ROOT/'ml_backend/.env');frontend=env(ROOT/'frontend/.env.local')
url=backend['SUPABASE_URL']
assert url=='http://127.0.0.1:54321','Local integration test only'
admin=create_client(url,backend['SUPABASE_KEY']);anon=create_client(url,frontend['VITE_SUPABASE_ANON_KEY'])
credentials=json.loads((ROOT/'.private/operator/team-demo-credentials.json').read_text())
all_products=admin.table('products').select('id,retailer_id,price').execute().data
for email,account in credentials.items():
    client=create_client(url,frontend['VITE_SUPABASE_ANON_KEY'])
    user=client.auth.sign_in_with_password({'email':email,'password':account['password']}).user
    products=client.table('products').select('id,retailer_id').eq('retailer_id',user.id).execute().data
    assert products and all(p['retailer_id']==user.id for p in products)
    foreign=next(p for p in all_products if p['retailer_id']!=user.id)
    assert client.table('products').update({'price':foreign['price']}).eq('id',foreign['id']).execute().data==[]
    predictions=client.table('ml_inventory_predictions').select('id,retailer_id').execute().data
    assert len(predictions)==len(products) and all(p['retailer_id']==user.id for p in predictions)
    assert client.table('ml_inventory').select('*').execute().data==[]
    assert client.table('ml_triggers').select('*').execute().data==[]
    try:
        client.rpc('publish_ml_results',{'prediction_rows':[],'transfer_rows':[]}).execute()
    except Exception:pass
    else:raise AssertionError('Retailer can invoke privileged publication RPC')
    print(email,': login, own inventory and predictions, cross-store write protection passed')
for table in ('profiles','orders','products','ml_inventory_predictions','ml_inventory','ml_triggers'):
    assert anon.table(table).select('*').execute().data==[],f'Anonymous access to {table}'
row=admin.table('ml_inventory_predictions').select('*').limit(1).execute().data[0]
before=admin.table('ml_inventory_predictions').select('id',count='exact',head=True).execute().count
try:
    admin.rpc('publish_ml_results',{'prediction_rows':[{**row,'confidence':'invalid'}],'transfer_rows':[]}).execute()
except Exception:pass
else:raise AssertionError('Malformed prediction accepted')
assert admin.table('ml_inventory_predictions').select('id',count='exact',head=True).execute().count==before
assert admin.table('ml_inventory_predictions').select('id').eq('id',row['id']).execute().data
print('Anonymous isolation, privileged RPC denial and transaction rollback passed')
