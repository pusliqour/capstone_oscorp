-- User-authorized synthetic archive demonstration; preserve original team stores.
alter table public.retailer_profiles add column data_origin text not null default 'user_managed';
alter table public.products add column data_origin text not null default 'user_managed';
alter table public.retailer_listings add column data_origin text not null default 'user_managed';
create table jiran_archive_lab.store_accounts (
 store_id text primary key, retailer_id uuid unique not null references public.retailer_profiles(id) on delete cascade,
 pos_connection_id uuid unique not null references public.pos_connections(id) on delete cascade
);
revoke all on jiran_archive_lab.store_accounts from public,anon,authenticated;
create index if not exists archive_daily_store_date on jiran_archive_lab.daily_sales(store_id,sales_date);
create index if not exists orders_retailer_time on public.orders(retailer_id,order_time);
create index if not exists order_items_order on public.order_items(order_id);

-- A bounded, read-only shared research projection; never exposes auth, phone or documents.
create or replace function public.archive_overview()
returns jsonb language plpgsql security definer set search_path=public as $$
begin
 if auth.uid() is null then raise exception 'Sign in required'; end if;
 return jsonb_build_object(
  'origin','synthetic_generated','source','User supplied Jiran.zip / ml:sample.zip',
  'products',(select count(*) from jiran_archive_lab.products),
  'stores',(select count(distinct store_id) from jiran_archive_lab.stock),
  'stock_rows',(select count(*) from jiran_archive_lab.stock),
  'daily_rows',(select count(*) from jiran_archive_lab.daily_sales),
  'transaction_lines',(select sum(transaction_count) from jiran_archive_lab.daily_sales),
  'first_date',(select min(sales_date) from jiran_archive_lab.daily_sales),
  'last_date',(select max(sales_date) from jiran_archive_lab.daily_sales),
  'snapshot_date',(select max(updated_at) from jiran_archive_lab.stock),
  'stores_available',(select jsonb_agg(t order by t.store_id) from (select s.store_id,count(*) as products,sum(stock_qty) as units from jiran_archive_lab.stock s group by s.store_id)t),
  'missing_fields',jsonb_build_array('Real retailer names and contact details','Verified geographic locations','Historical exchange requests and dismissals'),
  'model_limit','Policy labels are synthetic; learned classifier fails long-inactivity scenarios. Forecasts are historical snapshot estimates, not current November demand.'
 );
end; $$;
create or replace function public.archive_inventory(source_store text default null, search_text text default '', page_number integer default 0)
returns jsonb language plpgsql security definer set search_path=public as $$
declare result jsonb; total bigint;
begin
 if auth.uid() is null then raise exception 'Sign in required'; end if;
 if page_number < 0 or page_number > 10000 or length(coalesce(search_text,''))>120 then raise exception 'Invalid search or page'; end if;
 select count(*) into total from jiran_archive_lab.stock s join jiran_archive_lab.products p using(product_id)
 where (source_store is null or s.store_id=source_store) and (p.product_name ilike '%'||coalesce(search_text,'')||'%' or p.product_id ilike '%'||coalesce(search_text,'')||'%');
 select coalesce(jsonb_agg(t),'[]'::jsonb) into result from (
 select s.store_id,s.product_id,p.product_name,p.category,p.retail_price,s.stock_qty,s.updated_at,
 c.policy_prediction,c.model_prediction,(c.policy_prediction<>c.model_prediction) as review_required,
 f.method,f.forecast_7d,f.forecast_30d,f.forecast_60d
 from jiran_archive_lab.stock s join jiran_archive_lab.products p using(product_id)
 left join jiran_archive_lab.stock_classifications c using(store_id,product_id)
 left join jiran_archive_lab.forecasts f using(store_id,product_id)
 where (source_store is null or s.store_id=source_store) and (p.product_name ilike '%'||coalesce(search_text,'')||'%' or p.product_id ilike '%'||coalesce(search_text,'')||'%')
 order by s.store_id,s.product_id limit 50 offset page_number*50)t;
 return jsonb_build_object('total',total,'rows',result,'page',page_number,'page_size',50);
end; $$;
create or replace function public.archive_sales(source_store text, source_product text)
returns jsonb language plpgsql security definer set search_path=public as $$
begin
 if auth.uid() is null then raise exception 'Sign in required'; end if;
 return (select coalesce(jsonb_agg(t order by t.sales_date),'[]'::jsonb) from (
 select sales_date,quantity,transaction_count from jiran_archive_lab.daily_sales
 where store_id=source_store and product_id=source_product order by sales_date desc limit 366)t);
end; $$;
revoke all on function public.archive_overview(),public.archive_inventory(text,text,integer),public.archive_sales(text,text) from public,anon;
grant execute on function public.archive_overview(),public.archive_inventory(text,text,integer),public.archive_sales(text,text) to authenticated;

-- Marketplace locations disclose only published store geography, not personal profiles.
create policy "marketplace reads published store locations" on public.retailer_locations for select to authenticated
using (exists(select 1 from public.retailer_listings l where l.retailer_id=retailer_locations.retailer_id and l.is_active));
