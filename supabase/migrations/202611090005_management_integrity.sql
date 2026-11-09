-- Destructive management must use the transactional RPCs instead of bypassing cleanup.
revoke delete on public.retailer_profiles, public.products, public.product_variations from authenticated, anon;

-- Enforce coordinate validity even for direct owner-scoped updates.
alter table public.retailer_locations add constraint valid_location_coordinates check (
 (latitude is null and longitude is null) or
 (latitude is not null and longitude is not null and latitude between -90 and 90 and longitude between -180 and 180)
) not valid;
alter table public.product_inventory add constraint valid_inventory_quantity check (quantity between 0 and 1000000000) not valid;
alter table public.products add constraint valid_product_price check (price is null or price between 0 and 1000000000) not valid;

-- Owner IDs alone must not permit attaching records to a different store's connection.
drop policy "owner manages products" on public.products;
create policy "owner manages products" on public.products for all to authenticated using(retailer_id=(select auth.uid()))
with check(retailer_id=(select auth.uid()) and exists(select 1 from public.pos_connections c where c.id=pos_connection_id and c.retailer_id=(select auth.uid())));
drop policy "owner manages product_inventory" on public.product_inventory;
create policy "owner manages product_inventory" on public.product_inventory for all to authenticated
using(exists(select 1 from public.pos_connections c where c.id=pos_connection_id and c.retailer_id=(select auth.uid())))
with check(exists(select 1 from public.product_variations v join public.products p on p.id=v.product_id where v.id=product_variation_id and v.pos_connection_id=product_inventory.pos_connection_id and p.retailer_id=(select auth.uid())));
