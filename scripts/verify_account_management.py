"""Exercise account-management transactions using disposable users only."""
import json
import os
from pathlib import Path
import secrets
import sys
from supabase import create_client
ROOT=Path(__file__).resolve().parents[1]
def env(path):return dict(line.split('=',1) for line in path.read_text().splitlines() if '=' in line)
back=env(ROOT/'ml_backend/.env');front=env(ROOT/'frontend/.env.local')
admin=create_client(back['SUPABASE_URL'],back['SUPABASE_KEY'])
user=None
try:
    email='uxcheck-'+secrets.token_hex(5)+'@jiran.test';password=secrets.token_urlsafe(18)
    user=admin.auth.admin.create_user({'email':email,'password':password,'email_confirm':True,'user_metadata':{'role':'retailer','full_name':'UX Test'}}).user
    gateway=os.getenv('JIRAN_MANAGEMENT_URL',back['SUPABASE_URL'])
    key=front['VITE_SUPABASE_ANON_KEY'] if gateway==back['SUPABASE_URL'] else 'sb_publishable_jiran_team_gateway'
    client=create_client(gateway,key);client.auth.sign_in_with_password({'email':email,'password':password})
    def rpc(name,args=None):return client.rpc(name,args or {}).execute().data
    def denied(name,args):
        try:rpc(name,args)
        except Exception:return
        raise AssertionError('Expected rejection: '+name)
    rpc('create_my_store',{'shop_name':'Disposable UX Store'})
    denied('save_my_profile',{'full_name':None,'phone':'','shop_name':'Disposable UX Store'})
    rpc('save_my_profile',{'full_name':'Updated UX Name','phone':'+971 50 123 4567','shop_name':'Renamed UX Store'})
    assert client.table('profiles').select('full_name').eq('id',user.id).single().execute().data['full_name']=='Updated UX Name'
    assert client.table('retailer_profiles').select('shop_name').eq('id',user.id).single().execute().data['shop_name']=='Renamed UX Store'
    rpc('save_my_location',{'location_label':'Test Address','latitude':0,'longitude':0,'city':'Dubai','country':'UAE'})
    denied('save_my_location',{'location_label':'Invalid','latitude':91,'longitude':0})
    location=client.table('retailer_locations').select('*').single().execute().data
    assert location['latitude']==0 and location['location_label']=='Test Address'
    rpc('save_my_location',{'location_label':'New Address','latitude':25.2,'longitude':55.3})
    assert client.table('retailer_locations').select('id',count='exact').execute().count==1
    params={'variation_id':None,'product_name':'Disposable Product','sku':'UX-001','category':'Test','price':0,'quantity':0}
    vid=rpc('save_my_product',params)
    rpc('save_my_product',{**params,'variation_id':vid,'product_name':'Edited Product','price':12.5,'quantity':20})
    assert client.table('product_inventory').select('quantity').single().execute().data['quantity']==20
    denied('save_my_product',{**params,'sku':'UX-001'})
    denied('save_my_product',{**params,'sku':'UX-NEG','quantity':-1})
    foreign=admin.table('product_variations').select('id,product_id').neq('id',vid).limit(1).execute().data[0]
    denied('save_my_product',{**params,'variation_id':foreign['id']})
    denied('delete_my_product',{'variation_id':foreign['id'],'confirmation':'anything'})
    denied('delete_my_product',{'variation_id':vid,'confirmation':'wrong name'})
    rpc('delete_my_product',{'variation_id':vid,'confirmation':'Edited Product'})
    assert client.table('products').select('id').execute().data==[]
    rpc('remove_my_location')
    assert client.table('retailer_locations').select('id').execute().data==[]
    next_password=secrets.token_urlsafe(18)
    client.auth.update_user({'password':next_password})
    client.auth.sign_in_with_password({'email':email,'password':next_password})
    denied('delete_my_store',{'confirmation':'wrong store'})
    rpc('delete_my_store',{'confirmation':'Renamed UX Store'})
    assert client.table('retailer_profiles').select('id').execute().data==[]
    assert client.auth.get_user().user.id==user.id
    rpc('create_my_store',{'shop_name':'Recreated UX Store'})
    rpc('delete_my_store',{'confirmation':'Recreated UX Store'})
    assert client.table('account_activity').select('id').execute().data
    print('Profile/name persistence, location create/edit/remove, zero values, product CRUD, validation, cross-account denial, store delete/recreate and retained login: PASSED')
finally:
    if user:
        store=admin.table('retailer_profiles').select('store_id').eq('id',user.id).execute().data
        for row in store:admin.table('ml_inventory').delete().eq('store_id',row['store_id']).execute()
        admin.auth.admin.delete_user(user.id)
        print('Disposable test account removed; demo stores untouched')
