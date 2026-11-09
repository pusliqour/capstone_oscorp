-- Account-scoped management operations. Caller identity always comes from auth.uid().
create table public.account_activity (
 id uuid primary key default gen_random_uuid(), actor_id uuid not null references auth.users(id) on delete cascade,
 action text not null, target_id uuid, created_at timestamptz not null default now()
);
alter table public.account_activity enable row level security;
create policy "owner reads activity" on public.account_activity for select to authenticated using (actor_id=(select auth.uid()));

create or replace function public.save_my_profile(full_name text, phone text, shop_name text)
returns void language plpgsql security definer set search_path=public as $$
declare uid uuid := auth.uid();
begin
 if uid is null then raise exception 'Sign in required'; end if;
 if length(trim(full_name)) not between 1 and 100 then raise exception 'Enter a name between 1 and 100 characters'; end if;
 if length(coalesce(phone,''))>30 or (coalesce(phone,'')<>'' and phone !~ '^\+?[0-9 ()-]{6,30}$') then raise exception 'Enter a valid phone number'; end if;
 if exists(select 1 from retailer_profiles where id=uid) and length(trim(coalesce(shop_name,''))) not between 1 and 120 then raise exception 'Enter a store name between 1 and 120 characters'; end if;
 update profiles set full_name=trim(save_my_profile.full_name),phone=nullif(trim(save_my_profile.phone),'') where id=uid;
 update retailer_profiles set shop_name=trim(save_my_profile.shop_name) where id=uid;
 insert into account_activity(actor_id,action,target_id) values(uid,'profile_updated',uid);
end; $$;

create or replace function public.create_my_store(shop_name text)
returns uuid language plpgsql security definer set search_path=public as $$
declare uid uuid:=auth.uid();
begin
 if uid is null then raise exception 'Sign in required'; end if;
 if length(trim(coalesce(shop_name,''))) not between 1 and 120 then raise exception 'Enter a store name between 1 and 120 characters'; end if;
 if exists(select 1 from retailer_profiles where id=uid) then raise exception 'This account already has a store'; end if;
 insert into retailer_profiles(id,user_id,shop_name,store_id) values(uid,uid,trim(shop_name),'STORE_'||replace(uid::text,'-',''));
 insert into pos_connections(retailer_id,provider,status,is_active) values(uid,'manual','connected',true);
 insert into account_activity(actor_id,action,target_id) values(uid,'store_created',uid);
 return uid;
end; $$;

create or replace function public.save_my_location(location_label text, latitude double precision, longitude double precision, city text default null, country text default null)
returns uuid language plpgsql security definer set search_path=public as $$
declare uid uuid:=auth.uid(); loc uuid;
begin
 if uid is null or not exists(select 1 from retailer_profiles where id=uid) then raise exception 'Create a store before setting its location'; end if;
 if length(trim(coalesce(location_label,''))) not between 1 and 160 then raise exception 'Enter a location name between 1 and 160 characters'; end if;
 if (latitude is null)<>(longitude is null) then raise exception 'Provide both latitude and longitude, or leave both blank'; end if;
 if latitude is not null and not(latitude between -90 and 90 and longitude between -180 and 180) then raise exception 'Coordinates are outside the valid range'; end if;
 if length(coalesce(city,''))>100 or length(coalesce(country,''))>100 then raise exception 'City and country must be under 100 characters'; end if;
 perform 1 from retailer_profiles where id=uid for update;
 select id into loc from retailer_locations where retailer_id=uid and is_primary order by created_at limit 1;
 if loc is null then
   insert into retailer_locations(retailer_id,is_primary) values(uid,true) returning id into loc;
 end if;
 update retailer_locations set location_label=trim(save_my_location.location_label),latitude=save_my_location.latitude,longitude=save_my_location.longitude,
   city=nullif(trim(save_my_location.city),''),country=nullif(trim(save_my_location.country),''),
   map_link=case when save_my_location.latitude is not null then 'https://www.google.com/maps?q='||save_my_location.latitude||','||save_my_location.longitude else null end
 where id=loc and retailer_id=uid;
 insert into account_activity(actor_id,action,target_id) values(uid,'location_saved',loc);
 return loc;
end; $$;

create or replace function public.remove_my_location()
returns void language plpgsql security definer set search_path=public as $$
declare uid uuid:=auth.uid();
begin
 if uid is null then raise exception 'Sign in required'; end if;
 delete from retailer_locations where retailer_id=uid and is_primary;
 insert into account_activity(actor_id,action,target_id) values(uid,'location_removed',uid);
end; $$;

create or replace function public.delete_my_store(confirmation text)
returns void language plpgsql security definer set search_path=public as $$
declare uid uuid:=auth.uid(); shop retailer_profiles%rowtype;
begin
 select * into shop from retailer_profiles where id=uid for update;
 if uid is null or not found then raise exception 'Store not found'; end if;
 if confirmation is distinct from shop.shop_name then raise exception 'Type the exact store name to confirm deletion'; end if;
 update exchange_requests set status='cancelled' where from_retailer_id=uid or to_retailer_id=uid;
 delete from ml_inventory_predictions where retailer_id=uid;
 delete from ml_inventory_transfer_recommendations where from_retailer_id=uid or to_retailer_id=uid;
 delete from connection_intelligence where pos_connection_id in (select id from pos_connections where retailer_id=uid);
 delete from ml_inventory where store_id=shop.store_id;
 delete from retailer_profiles where id=uid;
 insert into account_activity(actor_id,action,target_id) values(uid,'store_deleted',uid);
end; $$;

create or replace function public.save_my_product(variation_id uuid, product_name text, sku text, category text, price numeric, quantity numeric)
returns uuid language plpgsql security definer set search_path=public as $$
declare uid uuid:=auth.uid(); pid uuid; vid uuid:=variation_id; cid uuid; sid text; old_sku text; stock_id uuid;
begin
 if uid is null then raise exception 'Sign in required'; end if;
 if length(trim(coalesce(product_name,''))) not between 1 and 160 then raise exception 'Enter a product name between 1 and 160 characters'; end if;
 if length(trim(coalesce(sku,''))) not between 1 and 120 or sku !~ '^[A-Za-z0-9_:.-]+$' then raise exception 'SKU may contain letters, numbers, underscores, colons, dots and hyphens'; end if;
 if length(trim(coalesce(category,''))) not between 1 and 80 then raise exception 'Enter a category between 1 and 80 characters'; end if;
 if price is null or not(price between 0 and 1000000000) or quantity is null or not(quantity between 0 and 1000000000) then raise exception 'Price and quantity must be finite numbers from 0 to 1 billion'; end if;
 select store_id into sid from retailer_profiles where id=uid for update;
 if not found then raise exception 'Create a store before adding products'; end if;
 if vid is not null then
  select p.id,v.pos_connection_id,v.sku into pid,cid,old_sku from product_variations v join products p on p.id=v.product_id
  where v.id=vid and p.retailer_id=uid for update of p,v;
  if not found then raise exception 'Product not found or access denied'; end if;
 else
  select id into cid from pos_connections where retailer_id=uid and is_active order by created_at limit 1;
  if cid is null then insert into pos_connections(retailer_id,provider,status,is_active) values(uid,'manual','connected',true) returning id into cid; end if;
 end if;
 if exists(select 1 from product_variations v join products p on p.id=v.product_id where p.retailer_id=uid and v.pos_connection_id=cid and lower(v.sku)=lower(trim(save_my_product.sku)) and v.id is distinct from vid) then raise exception 'This SKU is already used by another product'; end if;
 if pid is null then
  insert into products(retailer_id,pos_connection_id,sku,name,category,price) values(uid,cid,trim(sku),trim(product_name),trim(category),price) returning id into pid;
  insert into product_variations(product_id,pos_connection_id,sku,name,price,currency) values(pid,cid,trim(sku),'Regular',price,'AED') returning id into vid;
 else
  update products set name=trim(product_name),category=trim(save_my_product.category),price=save_my_product.price,sku=trim(save_my_product.sku),updated_at=now() where id=pid;
  update product_variations set sku=trim(save_my_product.sku),price=save_my_product.price,updated_at=now() where id=vid;
 end if;
 if (select count(*) from product_inventory where product_variation_id=vid and pos_connection_id=cid)>1 then raise exception 'This product has multiple stock locations; update each location separately'; end if;
 select id into stock_id from product_inventory where product_variation_id=vid and pos_connection_id=cid limit 1;
 if stock_id is null then insert into product_inventory(product_variation_id,pos_connection_id,pos_location_id,quantity) values(vid,cid,'manual',quantity);
 else update product_inventory set quantity=save_my_product.quantity,updated_at=now() where id=stock_id; end if;
 -- Previously published advice is invalid after a stock/product edit.
 delete from ml_inventory_predictions where product_variation_id=vid;
 delete from ml_inventory_transfer_recommendations where from_product_variation_id=vid or to_product_variation_id=vid;
 if old_sku is not null then delete from ml_inventory where store_id=sid and product_id=old_sku and old_sku<>trim(save_my_product.sku); end if;
 insert into ml_inventory(store_id,product_id,product_name,category,stock_qty,retail_price)
 values(sid,trim(sku),trim(product_name),trim(category),quantity,price)
 on conflict(store_id,product_id) do update set product_name=excluded.product_name,category=excluded.category,stock_qty=excluded.stock_qty,retail_price=excluded.retail_price,updated_at=now();
 insert into ml_triggers(status,trigger_type) values('pending','recommend');
 insert into account_activity(actor_id,action,target_id) values(uid,case when variation_id is null then 'product_created' else 'product_updated' end,pid);
 return vid;
end; $$;

create or replace function public.delete_my_product(variation_id uuid, confirmation text)
returns void language plpgsql security definer set search_path=public as $$
declare uid uuid:=auth.uid(); pid uuid; product_sku text; product_label text; sid text;
begin
 select p.id,p.name,v.sku into pid,product_label,product_sku from product_variations v join products p on p.id=v.product_id
 where v.id=variation_id and p.retailer_id=uid for update of p,v;
 if uid is null or not found then raise exception 'Product not found or access denied'; end if;
 if confirmation is distinct from product_label then raise exception 'Type the exact product name to confirm deletion'; end if;
 select store_id into sid from retailer_profiles where id=uid;
 update exchange_requests set status='cancelled' where listing_id in(select id from retailer_listings where product_id=pid);
 delete from ml_inventory_predictions where product_variation_id=variation_id;
 delete from ml_inventory_transfer_recommendations where from_product_variation_id=variation_id or to_product_variation_id=variation_id;
 delete from ml_inventory where store_id=sid and product_id=product_sku;
 delete from product_variations where id=variation_id;
 if not exists(select 1 from product_variations where product_id=pid) then delete from products where id=pid; end if;
 insert into account_activity(actor_id,action,target_id) values(uid,'product_deleted',pid);
end; $$;

revoke all on function public.save_my_profile(text,text,text), public.create_my_store(text), public.save_my_location(text,double precision,double precision,text,text), public.remove_my_location(), public.delete_my_store(text), public.save_my_product(uuid,text,text,text,numeric,numeric), public.delete_my_product(uuid,text) from public,anon;
grant execute on function public.save_my_profile(text,text,text), public.create_my_store(text), public.save_my_location(text,double precision,double precision,text,text), public.remove_my_location(), public.delete_my_store(text), public.save_my_product(uuid,text,text,text,numeric,numeric), public.delete_my_product(uuid,text) to authenticated;
