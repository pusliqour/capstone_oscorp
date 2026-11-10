create function public.business_reference_directory()
returns setof public.business_references language sql security definer set search_path=public as $$
 select b.* from public.business_references b where auth.uid() is not null order by b.business_name limit 100;
$$;
revoke all on function public.business_reference_directory() from public,anon;
grant execute on function public.business_reference_directory() to authenticated;
