"""Add the supplied synthetic archive to the app without replacing existing stores.

Idempotent inserts preserve subsequent retailer edits. Source dates remain historical.
Run after migrations and load_archive_lab.py. Credentials are owner-only and never in Git.
"""
import json
import os
from pathlib import Path
import secrets
import subprocess
import uuid
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / '.private/recovery/20261110/lab'

def stable(value):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'jiran-archive-20261110/' + value))

def run_sql(sql):
    result = subprocess.run(['docker','exec','-i','supabase_db_ISDIA','psql','-X','-U','postgres','-d','postgres','-v','ON_ERROR_STOP=1'],input=sql,text=True,capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout

def main():
    manifest = json.loads((LAB/'recovery.json').read_text())
    if manifest.get('data_origin') != 'synthetic_generated' or any(manifest['validation'].values()):
        raise ValueError('Validated synthetic archive required')
    env = dict(line.split('=',1) for line in (ROOT/'ml_backend/.env').read_text().splitlines() if '=' in line)
    if env['SUPABASE_URL'] not in ('http://127.0.0.1:54321','http://localhost:54321'):
        raise ValueError('Local Supabase only')
    client = create_client(env['SUPABASE_URL'],env['SUPABASE_KEY'])
    import csv
    stores = sorted({r['store_id'] for r in csv.DictReader((LAB/'stock.csv').open())})
    existing = {u.email:u for u in client.auth.admin.list_users(per_page=1000)}
    path = ROOT/'.private/operator/archive-demo-credentials.json'
    credentials = json.loads(path.read_text()) if path.exists() else {}
    mapping=[]
    for index,store in enumerate(stores,1):
        email=f'archive{index:02d}@jiran.test'
        if email not in existing:
            password=secrets.token_urlsafe(15)
            user=client.auth.admin.create_user({'email':email,'password':password,'email_confirm':True,'user_metadata':{'full_name':f'Synthetic archive {store}','role':'retailer','data_origin':'synthetic_generated'}}).user
            credentials[email]={'password':password,'store_id':store,'data_origin':'synthetic_generated'}
        else:
            user=existing[email]
        mapping.append({'store_id':store,'retailer_id':str(user.id),'connection_id':stable('connection/'+store)})
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    os.fchmod(fd,0o600)
    with os.fdopen(fd,'w') as stream:json.dump(credentials,stream,indent=2)
    payload=json.dumps(mapping).replace("'","''")
    sql="""
begin;
select pg_advisory_xact_lock(hashtext('jiran-archive-storefront'));
create temp table mapping as select * from jsonb_to_recordset('PAYLOAD'::jsonb) as t(store_id text,retailer_id uuid,connection_id uuid);
insert into public.retailer_profiles(id,user_id,shop_name,store_id,data_origin)
select retailer_id,retailer_id,'Synthetic archive '||store_id,store_id,'synthetic_generated' from mapping on conflict(id) do nothing;
insert into public.pos_connections(id,retailer_id,provider,status,is_active,last_synced_at)
select connection_id,retailer_id,'archive_daily_import','connected',true,(select max(updated_at) from jiran_archive_lab.stock) from mapping on conflict(id) do nothing;
insert into jiran_archive_lab.store_accounts select store_id,retailer_id,connection_id from mapping on conflict(store_id) do nothing;
create temp table pairs as
select s.*,m.retailer_id,m.connection_id,p.product_name,p.category,p.retail_price,
md5('jiran-archive-product/'||s.store_id||'/'||s.product_id)::uuid as pid,
md5('jiran-archive-variation/'||s.store_id||'/'||s.product_id)::uuid as vid
from jiran_archive_lab.stock s join mapping m using(store_id) join jiran_archive_lab.products p using(product_id);
insert into public.products(id,retailer_id,pos_connection_id,sku,name,category,price,updated_at,data_origin)
select pid,retailer_id,connection_id,product_id,product_name,category,retail_price,updated_at,'synthetic_generated' from pairs on conflict do nothing;
insert into public.product_variations(id,product_id,pos_connection_id,sku,name,price,updated_at)
select vid,pid,connection_id,product_id,'Archive snapshot',retail_price,updated_at from pairs on conflict do nothing;
insert into public.product_inventory(id,product_variation_id,pos_connection_id,pos_location_id,quantity,updated_at)
select md5('jiran-archive-stock/'||store_id||'/'||product_id)::uuid,vid,connection_id,store_id,stock_qty,updated_at from pairs on conflict do nothing;
-- Daily aggregates are explicitly labelled; they are not original receipts.
create temp table daily as select m.store_id,m.retailer_id,m.connection_id,d.sales_date,
md5('jiran-archive-day/'||m.store_id||'/'||d.sales_date)::uuid as oid,
sum(d.quantity*p.retail_price)::numeric(14,2) as estimated_value
from jiran_archive_lab.daily_sales d join mapping m using(store_id) join jiran_archive_lab.products p using(product_id)
group by m.store_id,m.retailer_id,m.connection_id,d.sales_date;
insert into public.orders(id,retailer_id,pos_connection_id,source,status,order_time,total_amount,external_order_id,external_location_id)
select oid,retailer_id,connection_id,'synthetic_archive_daily_aggregate','completed',sales_date::timestamp at time zone 'UTC',estimated_value,'archive-day/'||store_id||'/'||sales_date,store_id from daily on conflict do nothing;
insert into public.order_items(id,order_id,item_name,quantity,total_amount)
select md5('jiran-archive-item/'||d.store_id||'/'||d.product_id||'/'||d.sales_date)::uuid,dy.oid,p.product_name,d.quantity,(d.quantity*p.retail_price)::numeric(14,2)
from jiran_archive_lab.daily_sales d join daily dy using(store_id,sales_date) join jiran_archive_lab.products p using(product_id) on conflict do nothing;
insert into public.connection_intelligence(id,pos_connection_id,needs_more_data,units_sold)
select md5('jiran-archive-intelligence/'||m.store_id)::uuid,m.connection_id,count(d.*)<28,coalesce(sum(d.quantity),0)
from mapping m left join jiran_archive_lab.daily_sales d using(store_id) group by m.store_id,m.connection_id on conflict do nothing;
-- Policy decision and learned output stay distinct; no claim of independent accuracy.
insert into public.ml_inventory_predictions(id,retailer_id,pos_connection_id,product_variation_id,product_name,prediction,confidence,model_prediction,decision_source,demand_30d,demand_source)
select md5('jiran-archive-prediction/'||p.store_id||'/'||p.product_id)::uuid,p.retailer_id,p.connection_id,p.vid,p.product_name,c.policy_prediction,null,c.model_prediction,'synthetic_archive_policy',f.forecast_30d,'historical_archive_'||f.method
from pairs p join jiran_archive_lab.stock_classifications c using(store_id,product_id) left join jiran_archive_lab.forecasts f using(store_id,product_id) on conflict do nothing;
-- Up to ten explicitly labelled demonstration listings per archive store.
insert into public.retailer_listings(id,retailer_id,product_id,price,stock,customer_note,data_origin)
select md5('jiran-archive-listing/'||store_id||'/'||product_id)::uuid,retailer_id,pid,retail_price,least(stock_qty,50),
'Synthetic archive demonstration listing; historical 25 February 2026 stock, not a real seller offer.','synthetic_generated'
from (select p.*,row_number() over(partition by store_id order by stock_qty desc,product_id) rn from pairs p where stock_qty>0) ranked where rn<=10 on conflict do nothing;
insert into public.account_activity(id,actor_id,action)
select md5('jiran-archive-import/'||store_id)::uuid,retailer_id,'synthetic_archive_imported' from mapping on conflict do nothing;
-- Log the actual import for existing team accounts, rather than fabricate past actions.
insert into public.account_activity(id,actor_id,action)
select md5('jiran-archive-available/'||id)::uuid,id,'synthetic_archive_available_in_data_explorer' from public.retailer_profiles where data_origin<>'synthetic_generated' on conflict do nothing;
analyze public.orders; analyze public.order_items;
commit;
select json_build_object('archive_stores',(select count(*) from jiran_archive_lab.store_accounts),'archive_products',(select count(*) from public.products where data_origin='synthetic_generated'),'archive_orders',(select count(*) from public.orders where source='synthetic_archive_daily_aggregate'),'archive_items',(select count(*) from public.order_items i join public.orders o on o.id=i.order_id where o.source='synthetic_archive_daily_aggregate'),'archive_listings',(select count(*) from public.retailer_listings where data_origin='synthetic_generated'));
""".replace('PAYLOAD',payload)
    print(run_sql(sql))
    print('Private archive credentials:',path)

if __name__=='__main__':main()
