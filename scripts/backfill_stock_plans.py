"""Populate archive stock matrices without changing historical labels/models."""
from pathlib import Path
import json
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ml_backend'))
from stock_planning import stock_planning_matrix

def sql(statement):
 r=subprocess.run(['docker','exec','-i','supabase_db_ISDIA','psql','-X','-U','postgres','-d','postgres','-v','ON_ERROR_STOP=1','-At'],input=statement,text=True,capture_output=True)
 if r.returncode:raise RuntimeError(r.stderr)
 return r.stdout

def main():
 rows=json.loads(sql("select coalesce(json_agg(t),'[]') from (select pr.id,s.stock_qty,s.updated_at,c.policy_prediction,f.forecast_7d,f.forecast_14d,f.forecast_30d,f.forecast_60d from jiran_archive_lab.store_accounts m join jiran_archive_lab.stock s using(store_id) join jiran_archive_lab.forecasts f using(store_id,product_id) join jiran_archive_lab.stock_classifications c using(store_id,product_id) join public.products p on p.retailer_id=m.retailer_id and p.sku=s.product_id join public.product_variations v on v.product_id=p.id join public.ml_inventory_predictions pr on pr.product_variation_id=v.id) t;"))
 updates=[]
 for row in rows:
  plan=stock_planning_matrix(row,row['stock_qty'],policy_label=row['policy_prediction'])
  plan['as_of']=row['updated_at'];plan['forecast_source']='historical_synthetic_archive'
  updates.append({'id':row['id'],'stock_plan':plan})
 payload=json.dumps(updates).replace("'","''")
 print(sql("begin; update public.ml_inventory_predictions p set stock_plan=x.stock_plan from jsonb_to_recordset('"+payload+"'::jsonb) as x(id uuid,stock_plan jsonb) where p.id=x.id; commit;"))
 print('Historical archive stock matrices:',len(updates))
if __name__=='__main__':main()
