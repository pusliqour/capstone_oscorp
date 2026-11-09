alter table public.ml_inventory_predictions
  add column model_prediction text,
  add column decision_source text default 'stock_policy',
  add column demand_30d double precision,
  add column demand_source text;
-- Publish a prediction batch atomically; callers cannot partially erase results.
create or replace function public.publish_ml_results(prediction_rows jsonb, transfer_rows jsonb, replace_transfers boolean default true)
returns jsonb language plpgsql security definer set search_path = public as $$
declare variation_ids uuid[]; prediction_count integer; transfer_count integer := 0;
begin
  if jsonb_array_length(prediction_rows) = 0 then raise exception 'Empty prediction batch'; end if;
  select array_agg((r->>'product_variation_id')::uuid) into variation_ids from jsonb_array_elements(prediction_rows) r;
  delete from ml_inventory_predictions where product_variation_id = any(variation_ids);
  insert into ml_inventory_predictions (retailer_id,pos_connection_id,product_variation_id,product_name,prediction,confidence,model_prediction,decision_source,demand_30d,demand_source)
  select r.retailer_id,r.pos_connection_id,r.product_variation_id,r.product_name,r.prediction,r.confidence,r.model_prediction,r.decision_source,r.demand_30d,r.demand_source
  from jsonb_populate_recordset(null::ml_inventory_predictions,prediction_rows) r;
  get diagnostics prediction_count = row_count;
  if replace_transfers then
    delete from ml_inventory_transfer_recommendations where from_product_variation_id = any(variation_ids) or to_product_variation_id = any(variation_ids);
    insert into ml_inventory_transfer_recommendations (
      product_name,transfer_qty,from_label,to_label,from_stock_before,from_stock_after,to_stock_before,to_stock_after,demand_30d,from_coverage_after,to_coverage_after,
      from_retailer_id,to_retailer_id,from_pos_connection_id,to_pos_connection_id,from_product_variation_id,to_product_variation_id
    ) select product_name,transfer_qty,from_label,to_label,from_stock_before,from_stock_after,to_stock_before,to_stock_after,demand_30d,from_coverage_after,to_coverage_after,
      from_retailer_id,to_retailer_id,from_pos_connection_id,to_pos_connection_id,from_product_variation_id,to_product_variation_id
    from jsonb_populate_recordset(null::ml_inventory_transfer_recommendations,transfer_rows);
    get diagnostics transfer_count = row_count;
  end if;
  return jsonb_build_object('predictions',prediction_count,'transfers',transfer_count);
end; $$;
revoke all on function public.publish_ml_results(jsonb,jsonb,boolean) from public,anon,authenticated;
grant execute on function public.publish_ml_results(jsonb,jsonb,boolean) to service_role;

-- Expose only business names, never retailer documents or personal profiles.
create or replace function public.get_retailer_names(retailer_ids uuid[])
returns table(id uuid, shop_name text)
language sql security definer set search_path = public as $$
  select r.id,r.shop_name from public.retailer_profiles r
  where r.id=any(retailer_ids) and (select auth.uid()) is not null;
$$;
revoke all on function public.get_retailer_names(uuid[]) from public,anon;
grant execute on function public.get_retailer_names(uuid[]) to authenticated;
