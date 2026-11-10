-- Explicitly requested fictional filler, not recovered source data. Preserve owner edits.
alter table public.retailer_profiles add column if not exists contact_email text;
with numbered as (
 select m.retailer_id,row_number() over(order by m.store_id)::integer as n
 from jiran_archive_lab.store_accounts m join public.retailer_profiles r on r.id=m.retailer_id
 where r.data_origin='synthetic_generated'
)
update public.profiles p set phone='+000 000 000 '||lpad(n.n::text,4,'0') from numbered n
where p.id=n.retailer_id and nullif(trim(p.phone),'') is null;
with numbered as (
 select m.retailer_id,row_number() over(order by m.store_id)::integer as n from jiran_archive_lab.store_accounts m
 join public.retailer_profiles r on r.id=m.retailer_id where r.data_origin='synthetic_generated'
)
update public.retailer_profiles r set contact_email='demo-store-'||lpad(n.n::text,2,'0')||'@example.invalid'
from numbered n where r.id=n.retailer_id and nullif(trim(r.contact_email),'') is null;
with numbered as (
 select m.retailer_id,row_number() over(order by m.store_id)::integer as n from jiran_archive_lab.store_accounts m
 join public.retailer_profiles r on r.id=m.retailer_id where r.data_origin='synthetic_generated'
)
insert into public.retailer_locations(retailer_id,location_label,city,state,country,is_primary)
select n.retailer_id,'[FICTIONAL DEMO] Unit '||lpad(n.n::text,2,'0')||', '||(100+n.n)||' Sample Market Lane',
 (array['Demo Harbour','Demo Gardens','Demo Marina','Demo Central','Demo Heights'])[1+(n.n-1)%5],
 'Demo District '||(1+(n.n-1)%5),'Demo Country',true
from numbered n where not exists(select 1 from public.retailer_locations l where l.retailer_id=n.retailer_id);

-- Align the RPC argument/returned fields with the existing contact dialog.
drop function public.get_retailer_contact(uuid);
create function public.get_retailer_contact(target_user_id uuid)
returns table(id uuid,shop_name text,phone text,full_name text,contact_email text,location_label text,latitude double precision,longitude double precision,map_link text)
language sql security definer set search_path=public as $$
 select r.id,r.shop_name,p.phone,p.full_name,r.contact_email,l.location_label,l.latitude,l.longitude,l.map_link
 from retailer_profiles r left join profiles p on p.id=r.id
 left join lateral(select * from retailer_locations loc where loc.retailer_id=r.id order by loc.is_primary desc,loc.created_at desc limit 1)l on true
 where r.id=target_user_id and auth.uid() is not null and (
 r.id=auth.uid() or r.data_origin='synthetic_generated' or exists(
 select 1 from exchange_requests e where e.status in ('accepted','completed') and
 ((e.from_retailer_id=auth.uid() and e.to_retailer_id=r.id) or (e.to_retailer_id=auth.uid() and e.from_retailer_id=r.id))));
$$;
revoke all on function public.get_retailer_contact(uuid) from public,anon;
grant execute on function public.get_retailer_contact(uuid) to authenticated;
comment on column public.retailer_profiles.contact_email is 'Archive demo fillers use example.invalid, not deliverable real contact details.';
