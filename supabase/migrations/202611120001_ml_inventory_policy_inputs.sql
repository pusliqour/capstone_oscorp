-- Optional stock-policy inputs (12 Nov 2026). All nullable: NULL means "unknown",
-- and the ML API then keeps its previous behaviour for that input.
--   region             transfers stay within one region
--   age_days           days since first sale in this store; under 28 = "New"
--   stockout_days_30d  days with zero stock in the last 30 (lost-sales correction)
--   on_order           units ordered from the supplier, not yet received
--   lead_time_days     supplier delivery time
--   days_to_next_order days until this store next orders from its supplier
alter table public.ml_inventory
  add column if not exists region text,
  add column if not exists age_days double precision,
  add column if not exists stockout_days_30d double precision,
  add column if not exists on_order double precision,
  add column if not exists lead_time_days double precision,
  add column if not exists days_to_next_order double precision;

create or replace function public.replace_ml_inventory(inventory_rows jsonb)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  inserted_count integer;
begin
  delete from public.ml_inventory where true;

  insert into public.ml_inventory (
    store_id, product_id, store_name, product_name, category, stock_qty,
    retail_price, recent_qty, recent_txns, recent_avg, recent_std,
    historical_qty, historical_txns, historical_avg, total_sold, num_sales,
    days_since_last_sale, store_total_txns, updated_at,
    region, age_days, stockout_days_30d, on_order, lead_time_days, days_to_next_order
  )
  select
    row.store_id, row.product_id, row.store_name, row.product_name, row.category,
    row.stock_qty, row.retail_price, row.recent_qty, row.recent_txns,
    row.recent_avg, row.recent_std, row.historical_qty, row.historical_txns,
    row.historical_avg, row.total_sold, row.num_sales,
    row.days_since_last_sale, row.store_total_txns, row.updated_at,
    row.region, row.age_days, row.stockout_days_30d, row.on_order,
    row.lead_time_days, row.days_to_next_order
  from jsonb_to_recordset(inventory_rows) as row (
    store_id text,
    product_id text,
    store_name text,
    product_name text,
    category text,
    stock_qty double precision,
    retail_price double precision,
    recent_qty double precision,
    recent_txns double precision,
    recent_avg double precision,
    recent_std double precision,
    historical_qty double precision,
    historical_txns double precision,
    historical_avg double precision,
    total_sold double precision,
    num_sales double precision,
    days_since_last_sale double precision,
    store_total_txns double precision,
    updated_at timestamptz,
    region text,
    age_days double precision,
    stockout_days_30d double precision,
    on_order double precision,
    lead_time_days double precision,
    days_to_next_order double precision
  );

  get diagnostics inserted_count = row_count;
  return inserted_count;
end;
$$;

revoke all on function public.replace_ml_inventory(jsonb) from public;
revoke all on function public.replace_ml_inventory(jsonb) from anon;
revoke all on function public.replace_ml_inventory(jsonb) from authenticated;
grant execute on function public.replace_ml_inventory(jsonb) to service_role;
