-- Reject missing names consistently for direct RPC callers.
create or replace function public.save_my_profile(full_name text, phone text, shop_name text)
returns void language plpgsql security definer set search_path=public as $$
declare uid uuid := auth.uid();
begin
 if uid is null then raise exception 'Sign in required'; end if;
 if length(trim(coalesce(full_name,''))) not between 1 and 100 then raise exception 'Enter a name between 1 and 100 characters'; end if;
 if length(coalesce(phone,''))>30 or (coalesce(phone,'')<>'' and phone !~ '^\+?[0-9 ()-]{6,30}$') then raise exception 'Enter a valid phone number'; end if;
 if exists(select 1 from retailer_profiles where id=uid) and length(trim(coalesce(shop_name,''))) not between 1 and 120 then raise exception 'Enter a store name between 1 and 120 characters'; end if;
 update profiles set full_name=trim(save_my_profile.full_name),phone=nullif(trim(save_my_profile.phone),'') where id=uid;
 update retailer_profiles set shop_name=trim(save_my_profile.shop_name) where id=uid;
 insert into account_activity(actor_id,action,target_id) values(uid,'profile_updated',uid);
end; $$;

