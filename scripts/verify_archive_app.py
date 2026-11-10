"""Local integration checks: archive visibility, private isolation and atomic exchanges.

Creates three disposable retailers; never modifies supplied archive or team stores.
"""
import json
from pathlib import Path
import secrets
from supabase import create_client

ROOT=Path(__file__).resolve().parents[1]
def env(path):return dict(line.split('=',1) for line in path.read_text().splitlines() if '=' in line)
b=env(ROOT/'ml_backend/.env');f=env(ROOT/'frontend/.env.local');url=b['SUPABASE_URL']
assert url=='http://127.0.0.1:54321'
admin=create_client(url,b['SUPABASE_KEY']);created=[]
def fail(call):
    try:call()
    except Exception:return
    raise AssertionError('Forbidden operation succeeded')
def count(table,**filters):
    q=admin.table(table).select('id',count='exact',head=True)
    for key,value in filters.items():q=q.eq(key,value)
    return q.execute().count
try:
    archive_creds=json.loads((ROOT/'.private/operator/archive-demo-credentials.json').read_text())
    email,account=next(iter(archive_creds.items()))
    archive=create_client(url,f['VITE_SUPABASE_ANON_KEY']);archive.auth.sign_in_with_password({'email':email,'password':account['password']})
    connection=archive.table('pos_connections').select('id').eq('is_active',True).single().execute().data['id']
    summary=archive.rpc('my_sales_summary',{'connection_id':connection}).execute().data
    import csv
    expected=sum(float(row['quantity']) for row in csv.DictReader((ROOT/'.private/recovery/20261110/lab/daily_sales.csv').open()) if row['store_id']==account['store_id'])
    assert sum(float(row['quantity']) for row in summary['product_sales'])==expected
    assert summary['total_orders']==182 and len(summary['product_sales'])>50
    assert abs(sum(float(row['value']) for row in summary['categories'])-float(summary['total_revenue']))<1
    print('Archive full-history sales totals match source CSV beyond API row limit')
    clients=[]
    for role in ('buyer','seller','outsider'):
        email=f'archive-check-{role}-{secrets.token_hex(5)}@jiran.test';password=secrets.token_urlsafe(20)
        user=admin.auth.admin.create_user({'email':email,'password':password,'email_confirm':True}).user;created.append(user.id)
        c=create_client(url,f['VITE_SUPABASE_ANON_KEY']);c.auth.sign_in_with_password({'email':email,'password':password})
        c.rpc('create_my_store',{'shop_name':'Disposable '+role}).execute();clients.append(c)
    buyer,seller,outsider=clients;bid,sid,oid=created
    overview=buyer.rpc('archive_overview').execute().data
    assert overview['stores']==50 and overview['stock_rows']==5960 and overview['daily_rows']==1013393
    first=buyer.rpc('archive_inventory',{'page_number':0}).execute().data
    second=buyer.rpc('archive_inventory',{'page_number':1}).execute().data
    assert first['total']==5960 and len(first['rows'])==50
    assert {(r['store_id'],r['product_id']) for r in first['rows']}.isdisjoint({(r['store_id'],r['product_id']) for r in second['rows']})
    row=first['rows'][0]
    history=buyer.rpc('archive_sales',{'source_store':row['store_id'],'source_product':row['product_id']}).execute().data
    assert history
    fail(lambda:buyer.rpc('my_sales_summary',{'connection_id':connection}).execute())
    fail(lambda:buyer.rpc('archive_inventory',{'page_number':-1}).execute())
    anon=create_client(url,f['VITE_SUPABASE_ANON_KEY']);fail(lambda:anon.rpc('archive_overview').execute())
    assert not buyer.table('profiles').select('id').neq('id',bid).execute().data
    assert buyer.table('retailer_listings').select('id,product:products!inner(id,name)').eq('data_origin','synthetic_generated').limit(2).execute().data
    assert not buyer.table('pos_connections').select('id').neq('retailer_id',bid).execute().data
    print('Archive pagination, source history, anonymous denial, private profile isolation and marketplace visibility passed')
    seller.rpc('save_my_product',{'variation_id':None,'product_name':'Atomic test rice','sku':'ATOMIC-TEST','category':'Research','price':12,'quantity':20}).execute()
    buyer.rpc('save_my_product',{'variation_id':None,'product_name':'Atomic test rice','sku':'ATOMIC-TEST','category':'Research','price':12,'quantity':3}).execute()
    product=seller.table('products').select('id').eq('retailer_id',sid).single().execute().data
    listing=seller.table('retailer_listings').insert({'retailer_id':sid,'product_id':product['id'],'price':12,'stock':10}).execute().data[0]
    def request(qty=4):
        return buyer.table('exchange_requests').insert({'from_retailer_id':bid,'to_retailer_id':sid,'product_name':'Atomic test rice','quantity':qty,'status':'pending_vendor_approval','request_kind':'listing','listing_id':listing['id']}).execute().data[0]
    def act(c,r,action):return c.rpc('exchange_action',{'request_id':r['id'],'action':action}).execute().data
    r=request()
    fail(lambda:act(buyer,r,'accept'));fail(lambda:act(outsider,r,'accept'))
    fail(lambda:buyer.table('exchange_requests').update({'status':'completed'}).eq('id',r['id']).execute())
    assert act(seller,r,'accept')['status']=='accepted'
    too_large=request(7);fail(lambda:act(seller,too_large,'accept'))
    assert act(buyer,too_large,'cancel')['status']=='cancelled'
    assert act(buyer,r,'complete')['status']=='accepted'
    fail(lambda:act(outsider,r,'complete'))
    assert act(seller,r,'complete')['status']=='completed'
    assert act(seller,r,'complete')['status']=='completed'
    seller_stock=seller.table('product_inventory').select('quantity').execute().data
    buyer_stock=buyer.table('product_inventory').select('quantity').execute().data
    assert sum(float(x['quantity']) for x in seller_stock)==16
    assert sum(float(x['quantity']) for x in buyer_stock)==7
    assert len(buyer_stock)==1, 'Receipt must update the existing row'
    assert seller.table('retailer_listings').select('stock').eq('id',listing['id']).single().execute().data['stock']==6
    open_req=buyer.table('exchange_requests').insert({'from_retailer_id':bid,'product_name':'Atomic test rice','quantity':1,'request_kind':'open'}).execute().data[0]
    outsider.table('exchange_request_dismissals').upsert({'request_id':open_req['id'],'retailer_id':oid}).execute()
    assert act(seller,open_req,'accept')['status']=='accepted'
    assert act(buyer,open_req,'cancel')['status']=='cancelled'
    # Failure on final settlement rolls back the final confirmation and stock movement.
    rollback=request(2);act(seller,rollback,'accept');act(buyer,rollback,'complete')
    inventory=seller.table('product_inventory').select('id,quantity').single().execute().data
    admin.table('product_inventory').update({'quantity':0}).eq('id',inventory['id']).execute()
    fail(lambda:act(seller,rollback,'complete'))
    fresh=buyer.table('exchange_requests').select('status,seller_completed').eq('id',rollback['id']).single().execute().data
    assert fresh=={'status':'accepted','seller_completed':False}
    act(buyer,rollback,'cancel')
    assert buyer.table('account_activity').select('id',count='exact',head=True).execute().count>=5
    print('Exchange accept, approval, reservation, cancellation, dismissal, two-party completion, stock conservation, idempotence, rollback and audit passed')
finally:
    for uid in reversed(created):
        admin.table('ml_inventory').delete().eq('store_id','STORE_'+uid.replace('-','')).execute()
        admin.auth.admin.delete_user(uid)
    print('Disposable accounts removed')
