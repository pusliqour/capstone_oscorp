-- Public business directory fields only. No phone, personal name or documents.
create or replace function public.retailer_directory()
returns table(id uuid,shop_name text,store_id text,data_origin text)
language sql security definer set search_path=public as $$
 select r.id,r.shop_name,r.store_id,r.data_origin from retailer_profiles r
 where auth.uid() is not null order by r.shop_name,r.id limit 1000;
$$;
revoke all on function public.retailer_directory() from public,anon;
grant execute on function public.retailer_directory() to authenticated;
