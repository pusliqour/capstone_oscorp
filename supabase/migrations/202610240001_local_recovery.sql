-- Jiran local recovery schema.
-- Purpose: restore the graduation project's core non-AI workflows on self-hosted Supabase.
-- ML tables are intentionally created empty; no historical predictions or results are fabricated.

create extension if not exists pgcrypto;

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  role text not null default 'retailer',
  phone text,
  created_at timestamptz not null default now()
);

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, full_name, role, phone)
  values (
    new.id,
    new.raw_user_meta_data ->> 'full_name',
    coalesce(new.raw_user_meta_data ->> 'role', 'retailer'),
    new.raw_user_meta_data ->> 'phone'
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_user();

create table public.retailer_profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  user_id uuid unique references auth.users(id) on delete cascade,
  shop_name text not null,
  store_id text,
  document_url text,
  low_stock_notifications boolean not null default true,
  oos_notifications boolean not null default true,
  show_top_products_widget boolean not null default true,
  created_at timestamptz not null default now()
);

create table public.retailer_locations (
  id uuid primary key default gen_random_uuid(),
  retailer_id uuid not null references public.retailer_profiles(id) on delete cascade,
  location_label text,
  latitude double precision,
  longitude double precision,
  map_link text,
  city text,
  state text,
  country text,
  is_primary boolean not null default false,
  created_at timestamptz not null default now()
);

create table public.pos_connections (
  id uuid primary key default gen_random_uuid(),
  retailer_id uuid not null references public.retailer_profiles(id) on delete cascade,
  provider text not null default 'local_import',
  status text not null default 'connected',
  is_active boolean not null default true,
  last_error text,
  last_synced_at timestamptz,
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create table public.products (
  id uuid primary key default gen_random_uuid(),
  retailer_id uuid references public.retailer_profiles(id) on delete cascade,
  pos_connection_id uuid references public.pos_connections(id) on delete cascade,
  sku text,
  name text not null,
  category text,
  price numeric(14,2),
  active boolean not null default true,
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique(retailer_id, pos_connection_id, sku)
);

create table public.product_variations (
  id uuid primary key default gen_random_uuid(),
  product_id uuid not null references public.products(id) on delete cascade,
  pos_connection_id uuid references public.pos_connections(id) on delete cascade,
  sku text,
  name text,
  price numeric(14,2),
  currency text default 'AED',
  active boolean not null default true,
  updated_at timestamptz not null default now(),
  unique(product_id, sku, pos_connection_id)
);

create table public.product_inventory (
  id uuid primary key default gen_random_uuid(),
  product_variation_id uuid not null references public.product_variations(id) on delete cascade,
  pos_connection_id uuid references public.pos_connections(id) on delete cascade,
  pos_location_id text not null default 'local',
  quantity numeric not null default 0,
  updated_at timestamptz not null default now(),
  unique(product_variation_id, pos_location_id, pos_connection_id)
);

create table public.orders (
  id uuid primary key default gen_random_uuid(),
  retailer_id uuid not null references public.retailer_profiles(id) on delete cascade,
  pos_connection_id uuid references public.pos_connections(id) on delete cascade,
  source text default 'local_import',
  status text default 'completed',
  order_time timestamptz not null default now(),
  total_amount numeric(14,2) default 0,
  currency text default 'AED',
  external_order_id text,
  external_location_id text,
  is_active boolean not null default true,
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique(retailer_id, pos_connection_id, external_order_id)
);

create table public.order_items (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id) on delete cascade,
  item_name text not null,
  quantity numeric not null default 1,
  total_amount numeric(14,2) default 0,
  currency text default 'AED',
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

create table public.retailer_listings (
  id uuid primary key default gen_random_uuid(),
  retailer_id uuid not null references public.retailer_profiles(id) on delete cascade,
  product_id uuid not null references public.products(id) on delete cascade,
  price numeric(14,2) not null default 0,
  stock numeric not null default 0,
  customer_note text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(retailer_id, product_id)
);

create table public.exchange_requests (
  id uuid primary key default gen_random_uuid(),
  from_retailer_id uuid not null references public.retailer_profiles(id) on delete cascade,
  to_retailer_id uuid references public.retailer_profiles(id) on delete set null,
  product_name text not null,
  quantity numeric not null,
  max_price numeric(14,2),
  note text,
  status text not null default 'requested',
  request_kind text not null default 'open',
  listing_id uuid references public.retailer_listings(id) on delete set null,
  buyer_completed boolean not null default false,
  seller_completed boolean not null default false,
  created_at timestamptz not null default now()
);

create table public.exchange_request_dismissals (
  request_id uuid not null references public.exchange_requests(id) on delete cascade,
  retailer_id uuid not null references public.retailer_profiles(id) on delete cascade,
  primary key(request_id, retailer_id)
);

-- AI/ML result tables intentionally stay empty until a traceable dataset is reintroduced.
create table public.ml_inventory_predictions (
  id uuid primary key default gen_random_uuid(), retailer_id uuid, pos_connection_id uuid,
  product_variation_id uuid, product_name text, prediction text, confidence double precision,
  created_at timestamptz not null default now()
);
create table public.ml_inventory_transfer_recommendations (
  id uuid primary key default gen_random_uuid(), product_name text, transfer_qty numeric,
  from_label text, to_label text, from_stock_before numeric, from_stock_after numeric,
  to_stock_before numeric, to_stock_after numeric, demand_30d numeric,
  from_coverage_after numeric, to_coverage_after numeric,
  from_retailer_id uuid, to_retailer_id uuid, from_pos_connection_id uuid,
  to_pos_connection_id uuid, from_product_variation_id uuid, to_product_variation_id uuid,
  created_at timestamptz not null default now()
);
create table public.connection_intelligence (
  id uuid primary key default gen_random_uuid(), pos_connection_id uuid,
  needs_more_data boolean not null default true, units_sold numeric,
  created_at timestamptz not null default now()
);
create table public.ml_triggers (
  id uuid primary key default gen_random_uuid(), status text default 'pending', trigger_type text,
  filter_store text, filter_product text, created_at timestamptz default now(),
  completed_at timestamptz, error_msg text, result_file text
);

create or replace function public.get_retailer_contact(retailer_id uuid)
returns table(id uuid, shop_name text, phone text)
language sql security definer set search_path = public as $$
  select rp.id, rp.shop_name, p.phone
  from public.retailer_profiles rp left join public.profiles p on p.id = rp.id
  where rp.id = retailer_id;
$$;

insert into storage.buckets (id, name, public)
values ('retailer-docs', 'retailer-docs', false)
on conflict (id) do nothing;

create policy "authenticated users upload own retailer documents"
on storage.objects for insert to authenticated
with check (bucket_id = 'retailer-docs' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "authenticated users read own retailer documents"
on storage.objects for select to authenticated
using (bucket_id = 'retailer-docs' and (storage.foldername(name))[1] = auth.uid()::text);

-- Local recovery is single-machine development. Production RLS must be designed before deployment.
alter table public.profiles disable row level security;
alter table public.retailer_profiles disable row level security;
alter table public.retailer_locations disable row level security;
alter table public.pos_connections disable row level security;
alter table public.products disable row level security;
alter table public.product_variations disable row level security;
alter table public.product_inventory disable row level security;
alter table public.orders disable row level security;
alter table public.order_items disable row level security;
alter table public.retailer_listings disable row level security;
alter table public.exchange_requests disable row level security;
alter table public.exchange_request_dismissals disable row level security;
alter table public.ml_inventory_predictions disable row level security;
alter table public.ml_inventory_transfer_recommendations disable row level security;
alter table public.connection_intelligence disable row level security;
alter table public.ml_triggers disable row level security;
