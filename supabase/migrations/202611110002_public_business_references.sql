-- Public business facts are reference data, not retailer participation or stock provenance.
create table public.business_references (
 id uuid primary key,business_name text not null,brand text not null,address text not null,
 address_precision text not null,city text not null,country text not null,
 phone text not null,phone_scope text not null,contact_email text,email_scope text,
 map_link text,source_url text not null,contact_source_url text not null,
 checked_at timestamptz not null,source_hash text not null,
 origin text not null default 'public_official_listing' check(origin='public_official_listing')
);
alter table public.business_references enable row level security;
create policy "authenticated read public business references" on public.business_references for select to authenticated using(true);
revoke all on public.business_references from anon,authenticated;
grant select on public.business_references to authenticated;
grant all on public.business_references to service_role;
alter table public.retailer_profiles add column reference_business_id uuid references public.business_references(id);
comment on column public.retailer_profiles.reference_business_id is 'Public business used only as a location/contact demo reference; not an account owner, participant or source of synthetic inventory.';

drop function public.get_retailer_contact(uuid);
create function public.get_retailer_contact(target_user_id uuid)
returns table(id uuid,shop_name text,phone text,full_name text,contact_email text,location_label text,latitude double precision,longitude double precision,map_link text,
 reference_business_name text,reference_source_url text,reference_contact_source_url text,reference_checked_at timestamptz,phone_scope text,email_scope text,address_precision text)
language sql security definer set search_path=public as $$
 select r.id,r.shop_name,p.phone,coalesce(b.business_name,p.full_name),r.contact_email,l.location_label,l.latitude,l.longitude,l.map_link,
 b.business_name,b.source_url,b.contact_source_url,b.checked_at,b.phone_scope,b.email_scope,b.address_precision
 from retailer_profiles r left join profiles p on p.id=r.id left join business_references b on b.id=r.reference_business_id
 left join lateral(select * from retailer_locations loc where loc.retailer_id=r.id order by loc.is_primary desc,loc.created_at desc limit 1)l on true
 where r.id=target_user_id and auth.uid() is not null and (
 r.id=auth.uid() or r.data_origin='synthetic_generated' or exists(
 select 1 from exchange_requests e where e.status in ('accepted','completed') and
 ((e.from_retailer_id=auth.uid() and e.to_retailer_id=r.id) or (e.to_retailer_id=auth.uid() and e.from_retailer_id=r.id))));
$$;
revoke all on function public.get_retailer_contact(uuid) from public,anon;
grant execute on function public.get_retailer_contact(uuid) to authenticated;
