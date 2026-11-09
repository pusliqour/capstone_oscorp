-- Jiran ML real-data bridge.
-- The service-role-only table is populated by ml_backend/import_jiran_ml_real_data.py
-- and consumed by the FastAPI Supabase watcher.

create table if not exists public.ml_inventory (
  store_id text not null,
  product_id text not null,
  store_name text,
  product_name text not null,
  category text not null default 'general',
  stock_qty double precision not null default 0,
  retail_price double precision not null default 0,
  recent_qty double precision not null default 0,
  recent_txns double precision not null default 0,
  recent_avg double precision not null default 0,
  recent_std double precision not null default 0,
  historical_qty double precision not null default 0,
  historical_txns double precision not null default 0,
  historical_avg double precision not null default 0,
  total_sold double precision not null default 0,
  num_sales double precision not null default 0,
  days_since_last_sale double precision not null default 0,
  store_total_txns double precision not null default 0,
  updated_at timestamptz not null default now(),
  primary key (store_id, product_id)
);

-- Converge older recovery databases where ml_inventory may already exist with
-- only a subset of the watcher contract. A duplicate composite key causes the
-- unique-index step to fail loudly instead of making upsert behavior ambiguous.
alter table public.ml_inventory
  add column if not exists store_id text,
  add column if not exists product_id text,
  add column if not exists store_name text,
  add column if not exists product_name text,
  add column if not exists category text default 'general',
  add column if not exists stock_qty double precision default 0,
  add column if not exists retail_price double precision default 0,
  add column if not exists recent_qty double precision default 0,
  add column if not exists recent_txns double precision default 0,
  add column if not exists recent_avg double precision default 0,
  add column if not exists recent_std double precision default 0,
  add column if not exists historical_qty double precision default 0,
  add column if not exists historical_txns double precision default 0,
  add column if not exists historical_avg double precision default 0,
  add column if not exists total_sold double precision default 0,
  add column if not exists num_sales double precision default 0,
  add column if not exists days_since_last_sale double precision default 0,
  add column if not exists store_total_txns double precision default 0,
  add column if not exists updated_at timestamptz default now();

create unique index if not exists ml_inventory_store_product_uidx
  on public.ml_inventory (store_id, product_id);

create index if not exists ml_inventory_product_id_idx
  on public.ml_inventory (product_id);

-- Replace the full watcher snapshot in one transaction. The service role is the
-- only API role allowed to execute this function.
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
    days_since_last_sale, store_total_txns, updated_at
  )
  select
    row.store_id, row.product_id, row.store_name, row.product_name, row.category,
    row.stock_qty, row.retail_price, row.recent_qty, row.recent_txns,
    row.recent_avg, row.recent_std, row.historical_qty, row.historical_txns,
    row.historical_avg, row.total_sold, row.num_sales,
    row.days_since_last_sale, row.store_total_txns, row.updated_at
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
    updated_at timestamptz
  );

  get diagnostics inserted_count = row_count;
  return inserted_count;
end;
$$;

revoke all on function public.replace_ml_inventory(jsonb) from public;
revoke all on function public.replace_ml_inventory(jsonb) from anon;
revoke all on function public.replace_ml_inventory(jsonb) from authenticated;
grant execute on function public.replace_ml_inventory(jsonb) to service_role;

alter table public.ml_inventory enable row level security;
comment on table public.ml_inventory is
  'Normalized Square inventory and sales features from M4MD-M7SN/jiran-ml; service-role access only.';
