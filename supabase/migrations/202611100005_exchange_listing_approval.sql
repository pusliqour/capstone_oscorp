-- Match the existing listing approval status while keeping transitions atomic.
create or replace function public.validate_new_exchange()
returns trigger language plpgsql security definer set search_path=public as $$
declare listing retailer_listings%rowtype;
begin
 if auth.uid() is null or new.from_retailer_id<>auth.uid() then raise exception 'Invalid buyer'; end if;
 if not exists(select 1 from retailer_profiles where id=auth.uid()) then raise exception 'Create a store first'; end if;
 if new.quantity is null or not(new.quantity>0 and new.quantity<=1000000000) or length(trim(new.product_name)) not between 1 and 160 then raise exception 'Enter a product and positive quantity'; end if;
 if new.status not in ('requested','pending_vendor_approval') or new.buyer_completed or new.seller_completed then raise exception 'New requests must start as requested'; end if;
 if new.request_kind not in ('open','listing') then raise exception 'Invalid request kind'; end if;
 if new.from_retailer_id=new.to_retailer_id then raise exception 'You cannot request your own stock'; end if;
 if new.request_kind='listing' then
  select * into listing from retailer_listings where id=new.listing_id for update;
  if not found or not listing.is_active then raise exception 'Listing unavailable'; end if;
  if new.to_retailer_id is distinct from listing.retailer_id then raise exception 'Invalid listing seller'; end if;
  if new.quantity>listing.stock then raise exception 'Requested quantity exceeds listing stock'; end if;
  select name into new.product_name from products where id=listing.product_id;
 else
  if new.to_retailer_id is not null or new.listing_id is not null then raise exception 'Open requests cannot preselect a seller or listing'; end if;
 end if;
 return new;
end; $$;
create or replace function public.exchange_action(request_id uuid, action text)
returns jsonb language plpgsql security definer set search_path=public as $$
declare uid uuid:=auth.uid(); r exchange_requests%rowtype; l retailer_listings%rowtype;
 reserved numeric; inventory_id uuid; available numeric; seller_product products%rowtype;
 buyer_connection uuid; buyer_product uuid; buyer_variation uuid; source_sku text;
begin
 if uid is null or not exists(select 1 from retailer_profiles where id=uid) then raise exception 'Retailer sign in required'; end if;
 select * into r from exchange_requests where id=request_id for update;
 if not found then raise exception 'Request not found'; end if;
 if action='cancel' then
  if r.from_retailer_id<>uid or r.status not in ('requested','pending_vendor_approval','accepted') then raise exception 'Only the buyer can cancel an active request'; end if;
  update exchange_requests set status='cancelled' where id=r.id;
 elsif action in ('accept','decline') then
  if r.status not in ('requested','pending_vendor_approval') or r.from_retailer_id=uid or (r.to_retailer_id is not null and r.to_retailer_id<>uid) then raise exception 'This request is not available to you'; end if;
  if action='decline' and r.request_kind='open' then
   insert into exchange_request_dismissals(request_id,retailer_id) values(r.id,uid) on conflict do nothing;
   return jsonb_build_object('status','dismissed');
  end if;
  if action='accept' and r.listing_id is not null then
   select * into l from retailer_listings where id=r.listing_id for update;
   if not found or l.retailer_id<>uid or not l.is_active then raise exception 'Listing unavailable'; end if;
   select coalesce(sum(quantity),0) into reserved from exchange_requests where listing_id=l.id and status='accepted';
   if l.stock-reserved<r.quantity then raise exception 'Insufficient unreserved listing stock'; end if;
  end if;
  update exchange_requests set to_retailer_id=uid,status=case when action='accept' then 'accepted' else 'declined' end where id=r.id;
 elsif action='complete' then
  if uid not in (r.from_retailer_id,r.to_retailer_id) or r.to_retailer_id is null then raise exception 'Only participants can confirm'; end if;
  if r.status='completed' then return jsonb_build_object('status','completed'); end if;
  if r.status<>'accepted' then raise exception 'Accept the request before completing'; end if;
  if uid=r.from_retailer_id then r.buyer_completed:=true; else r.seller_completed:=true; end if;
  if r.buyer_completed and r.seller_completed then
   -- Locate exactly one seller inventory row. No silent stock creation or clamping.
   if r.listing_id is not null then
    select * into l from retailer_listings where id=r.listing_id for update;
    select * into seller_product from products where id=l.product_id;
   else
    select * into seller_product from products where retailer_id=r.to_retailer_id and lower(name)=lower(r.product_name) and active order by id limit 1;
   end if;
   if seller_product.id is null then raise exception 'Seller must add this product to inventory before completion'; end if;
   select i.id,i.quantity into inventory_id,available from product_inventory i join product_variations v on v.id=i.product_variation_id
   where v.product_id=seller_product.id order by i.id limit 1 for update of i;
   if inventory_id is null or available<r.quantity then raise exception 'Insufficient seller inventory'; end if;
   if r.listing_id is not null and l.stock<r.quantity then raise exception 'Insufficient listing stock'; end if;
   -- Buyer store lock makes concurrent receipts deterministic.
   perform 1 from retailer_profiles where id=r.from_retailer_id for update;
   select id into buyer_connection from pos_connections where retailer_id=r.from_retailer_id and is_active order by created_at limit 1;
   if buyer_connection is null then
    insert into pos_connections(retailer_id,provider,status,is_active) values(r.from_retailer_id,'manual','connected',true) returning id into buyer_connection;
   end if;
   source_sku:=coalesce(seller_product.sku,'exchange-'||seller_product.id::text);
   select id into buyer_product from products where retailer_id=r.from_retailer_id and pos_connection_id=buyer_connection and sku=source_sku;
   if buyer_product is null then
    insert into products(retailer_id,pos_connection_id,sku,name,category,price,data_origin)
    values(r.from_retailer_id,buyer_connection,source_sku,seller_product.name,seller_product.category,seller_product.price,seller_product.data_origin) returning id into buyer_product;
   end if;
   select id into buyer_variation from product_variations where product_id=buyer_product and pos_connection_id=buyer_connection order by id limit 1;
   if buyer_variation is null then
    insert into product_variations(product_id,pos_connection_id,sku,name,price) values(buyer_product,buyer_connection,source_sku,'Exchange receipt',seller_product.price) returning id into buyer_variation;
   end if;
   update product_inventory set quantity=quantity-r.quantity,updated_at=now() where id=inventory_id;
   insert into product_inventory(product_variation_id,pos_connection_id,pos_location_id,quantity)
   values(buyer_variation,buyer_connection,'exchange',r.quantity)
   on conflict(product_variation_id,pos_location_id,pos_connection_id) do update set quantity=product_inventory.quantity+excluded.quantity,updated_at=now();
   if r.listing_id is not null then update retailer_listings set stock=stock-r.quantity,is_active=(stock-r.quantity>0),updated_at=now() where id=l.id; end if;
   r.status:='completed';
   insert into account_activity(actor_id,action,target_id) values(r.from_retailer_id,'exchange_stock_received',r.id),(r.to_retailer_id,'exchange_stock_sent',r.id);
  end if;
  update exchange_requests set buyer_completed=r.buyer_completed,seller_completed=r.seller_completed,status=r.status where id=r.id;
 else raise exception 'Unknown exchange action';
 end if;
 insert into account_activity(actor_id,action,target_id) values(uid,'exchange_'||action,r.id);
 return (select jsonb_build_object('id',id,'status',status,'buyer_completed',buyer_completed,'seller_completed',seller_completed) from exchange_requests where id=r.id);
end; $$;
