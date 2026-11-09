-- Tenant isolation for authenticated retailer demos. ML inputs and jobs stay server-only.
alter table public.profiles enable row level security;
create policy "owner manages profiles" on public.profiles for all to authenticated using (id = (select auth.uid())) with check (id = (select auth.uid()));
alter table public.retailer_profiles enable row level security;
create policy "owner manages retailer_profiles" on public.retailer_profiles for all to authenticated using (id = (select auth.uid())) with check (id = (select auth.uid()));
alter table public.retailer_locations enable row level security;
create policy "owner manages retailer_locations" on public.retailer_locations for all to authenticated using (retailer_id = (select auth.uid())) with check (retailer_id = (select auth.uid()));
alter table public.pos_connections enable row level security;
create policy "owner manages pos_connections" on public.pos_connections for all to authenticated using (retailer_id = (select auth.uid())) with check (retailer_id = (select auth.uid()));
alter table public.products enable row level security;
create policy "owner manages products" on public.products for all to authenticated using (retailer_id = (select auth.uid())) with check (retailer_id = (select auth.uid()));
alter table public.orders enable row level security;
create policy "owner manages orders" on public.orders for all to authenticated using (retailer_id = (select auth.uid())) with check (retailer_id = (select auth.uid()));
alter table public.retailer_listings enable row level security;
create policy "owner manages retailer_listings" on public.retailer_listings for all to authenticated using (retailer_id = (select auth.uid())) with check (retailer_id = (select auth.uid()));
alter table public.exchange_request_dismissals enable row level security;
create policy "owner manages exchange_request_dismissals" on public.exchange_request_dismissals for all to authenticated using (retailer_id = (select auth.uid())) with check (retailer_id = (select auth.uid()));
alter table public.product_variations enable row level security;
create policy "owner manages product_variations" on public.product_variations for all to authenticated using (exists (select 1 from public.products p where p.id = product_id and p.retailer_id = (select auth.uid()))) with check (exists (select 1 from public.products p where p.id = product_id and p.retailer_id = (select auth.uid())));
alter table public.product_inventory enable row level security;
create policy "owner manages product_inventory" on public.product_inventory for all to authenticated using (exists (select 1 from public.pos_connections c where c.id = pos_connection_id and c.retailer_id = (select auth.uid()))) with check (exists (select 1 from public.pos_connections c where c.id = pos_connection_id and c.retailer_id = (select auth.uid())));
alter table public.order_items enable row level security;
create policy "owner manages order_items" on public.order_items for all to authenticated using (exists (select 1 from public.orders o where o.id = order_id and o.retailer_id = (select auth.uid()))) with check (exists (select 1 from public.orders o where o.id = order_id and o.retailer_id = (select auth.uid())));
alter table public.ml_inventory_predictions enable row level security;
create policy "owner reads ml_inventory_predictions" on public.ml_inventory_predictions for select to authenticated using (retailer_id = (select auth.uid()));
alter table public.ml_inventory_transfer_recommendations enable row level security;
create policy "owner reads ml_inventory_transfer_recommendations" on public.ml_inventory_transfer_recommendations for select to authenticated using ((select auth.uid()) in (from_retailer_id, to_retailer_id));
alter table public.connection_intelligence enable row level security;
create policy "owner reads connection_intelligence" on public.connection_intelligence for select to authenticated using (exists (select 1 from public.pos_connections c where c.id = pos_connection_id and c.retailer_id = (select auth.uid())));

alter table public.ml_triggers enable row level security;
alter table public.exchange_requests enable row level security;
create policy "retailers browse active listings" on public.retailer_listings for select to authenticated using (is_active);
create policy "retailers browse listed products" on public.products for select to authenticated using (
  exists (select 1 from public.retailer_listings l where l.product_id = products.id and l.is_active)
);
create policy "participants read exchange requests" on public.exchange_requests for select to authenticated
using ((select auth.uid()) in (from_retailer_id, to_retailer_id) or (request_kind = 'open' and status = 'requested'));
create policy "retailer creates exchange request" on public.exchange_requests for insert to authenticated
with check (from_retailer_id = (select auth.uid()));
create policy "participants update exchange request" on public.exchange_requests for update to authenticated
using ((select auth.uid()) in (from_retailer_id, to_retailer_id))
with check ((select auth.uid()) in (from_retailer_id, to_retailer_id));
revoke execute on function public.get_retailer_contact(uuid) from public, anon;
grant execute on function public.get_retailer_contact(uuid) to authenticated;
