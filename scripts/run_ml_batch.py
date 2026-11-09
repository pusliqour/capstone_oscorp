"""Run a local ML batch through the same watcher/publication path used by jobs."""
from pathlib import Path
import os
import sys
ROOT=Path(__file__).resolve().parents[1]
for line in (ROOT/'ml_backend/.env').read_text().splitlines():
    if '=' in line:
        key,value=line.split('=',1);os.environ[key]=value
sys.path.insert(0,str(ROOT/'ml_backend'))
from supabase_watcher import get_client, process_trigger
client=get_client()
job=client.table('ml_triggers').insert({'status':'pending','trigger_type':'recommend'}).execute().data[0]
process_trigger(job)
status=client.table('ml_triggers').select('id,status,error_msg').eq('id',job['id']).single().execute().data
print(status)
if status['status']!='done':raise SystemExit(1)
for table in ('ml_inventory_predictions','ml_inventory_transfer_recommendations'):
    print(table,client.table(table).select('id',count='exact',head=True).execute().count)
