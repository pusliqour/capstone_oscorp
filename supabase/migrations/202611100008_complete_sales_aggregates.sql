-- Aggregate in PostgreSQL so the API's 1,000-row response cap cannot truncate sales.
create or replace function public.my_sales_summary(connection_id uuid, since_time timestamptz default null, until_time timestamptz default null)
returns jsonb language plpgsql security definer set search_path=public as $$
declare result jsonb;
begin
 if auth.uid() is null or not exists(select 1 from pos_connections c where c.id=connection_id and c.retailer_id=auth.uid()) then raise exception 'Connection not owned by this retailer'; end if;
 with selected_orders as materialized (
  select o.id,o.total_amount from orders o where o.retailer_id=auth.uid() and o.pos_connection_id=connection_id and o.is_active and o.status='completed'
  and (since_time is null or o.order_time>=since_time) and (until_time is null or o.order_time<=until_time)
 ), category_lookup as (
  select lower(trim(name)) as product_name,min(category) as category from products where retailer_id=auth.uid() and pos_connection_id=connection_id group by lower(trim(name))
 ), items as materialized (
  select i.order_id,i.item_name,i.quantity,i.total_amount,coalesce(c.category,'Uncategorized') as category
  from order_items i join selected_orders o on o.id=i.order_id left join category_lookup c on c.product_name=lower(trim(i.item_name)) where i.is_active
 ), top_sellers as (select item_name as name,sum(quantity) as sold from items group by item_name order by sum(quantity) desc,item_name limit 10),
 categories as (select category as label,sum(total_amount) as value from items group by category order by category),
 product_sales as (select item_name,sum(quantity) as quantity,sum(total_amount) as total_amount,count(distinct order_id) as order_count from items group by item_name order by item_name)
 select jsonb_build_object('total_orders',(select count(*) from selected_orders),'total_revenue',(select coalesce(sum(total_amount),0) from selected_orders),
 'product_sales',(select coalesce(jsonb_agg(p),'[]'::jsonb) from product_sales p),'top_sellers',(select coalesce(jsonb_agg(t),'[]'::jsonb) from top_sellers t),'categories',(select coalesce(jsonb_agg(c),'[]'::jsonb) from categories c)) into result;
 return result;
end; $$;
revoke all on function public.my_sales_summary(uuid,timestamptz,timestamptz) from public,anon;
grant execute on function public.my_sales_summary(uuid,timestamptz,timestamptz) to authenticated;
