-- Isolated synthetic research recovery; never replaces public application tables.
create schema if not exists jiran_archive_lab;
revoke all on schema jiran_archive_lab from public,anon,authenticated;
create table jiran_archive_lab.datasets (
 id text primary key, source_label text not null, data_origin text not null check(data_origin='synthetic_generated'),
 metadata jsonb not null, imported_at timestamptz not null default now()
);
create table jiran_archive_lab.products (
 product_id text primary key,product_name text not null,category text not null,
 retail_price double precision not null check(retail_price>=0),wholesale_price double precision not null check(wholesale_price>=0)
);
create table jiran_archive_lab.stock (
 store_id text not null,product_id text not null references jiran_archive_lab.products(product_id),
 stock_qty double precision not null check(stock_qty>=0),updated_at timestamp not null,
 primary key(store_id,product_id)
);
create table jiran_archive_lab.daily_sales (
 store_id text not null,product_id text not null,sales_date date not null,
 quantity double precision not null check(quantity>0),transaction_count bigint not null check(transaction_count>0),quantity_squared_sum double precision not null,
 primary key(store_id,product_id,sales_date),foreign key(store_id,product_id) references jiran_archive_lab.stock(store_id,product_id)
);
create table jiran_archive_lab.forecasts (
 store_id text not null,product_id text not null,method text not null,
 forecast_7d double precision,forecast_14d double precision,forecast_30d double precision,forecast_60d double precision,
 primary key(store_id,product_id),foreign key(store_id,product_id) references jiran_archive_lab.stock(store_id,product_id)
);
create table jiran_archive_lab.stock_classifications (
 store_id text not null,product_id text not null,policy_prediction text not null,model_prediction text not null,model_support double precision not null,
 primary key(store_id,product_id),foreign key(store_id,product_id) references jiran_archive_lab.stock(store_id,product_id)
);
create table jiran_archive_lab.evaluations (
 name text primary key,data_origin text not null default 'synthetic_generated',metrics jsonb not null,created_at timestamptz not null default now()
);
revoke all on all tables in schema jiran_archive_lab from public,anon,authenticated;
comment on schema jiran_archive_lab is 'Synthetic research recovered from user-supplied Jiran.zip. Not live retailer data; not exposed by the team gateway.';
