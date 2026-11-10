"""Load validated archive research into a separate local-only PostgreSQL schema.

Raw CSVs and all derived files stay outside Git. No supplied SQL is executed.
"""
import argparse
import csv
import io
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SCHEMA='jiran_archive_lab'
def literal(value):return "'"+str(value).replace("'","''")+"'"

def load(lab):
    lab=Path(lab).resolve();manifest=json.loads((lab/'recovery.json').read_text())
    if manifest.get('data_origin')!='synthetic_generated' or any(manifest['validation'].values()):raise ValueError('Only the validated synthetic recovery is accepted')
    exports=lab/'postgres';exports.mkdir(exist_ok=True)
    tables=[('products','product_id,product_name,category,retail_price,wholesale_price,is_common,expiry_date,unit_quantity,source_store_id',lab/'products.csv'),('stock','store_id,product_id,stock_qty,updated_at',lab/'stock.csv'),('daily_sales','store_id,product_id,sales_date,quantity,transaction_count,quantity_squared_sum',lab/'daily_sales.csv')]
    if (lab/'models/stock_predictions.csv').exists():
        import pandas as pd
        pd.read_csv(lab/'models/stock_predictions.csv',usecols=['store_id','product_id','policy_prediction','model_prediction','model_support']).to_csv(exports/'stock_classifications.csv',index=False)
        # Explicit column ordering makes COPY independent of pandas source order.
        frame=pd.read_csv(exports/'stock_classifications.csv')
        frame[['store_id','product_id','policy_prediction','model_prediction','model_support']].to_csv(exports/'stock_classifications.csv',index=False)
        tables += [('stock_classifications','store_id,product_id,policy_prediction,model_prediction,model_support',exports/'stock_classifications.csv'),('forecasts','store_id,product_id,method,forecast_7d,forecast_14d,forecast_30d,forecast_60d',lab/'models/forecasts.csv')]
    log=lab/'postgres-load.log'
    with log.open('wb') as output:
        process=subprocess.Popen(['docker','exec','-i','supabase_db_ISDIA','psql','-X','-U','postgres','-d','postgres','-v','ON_ERROR_STOP=1'],stdin=subprocess.PIPE,stdout=output,stderr=subprocess.STDOUT)
        def send(text):process.stdin.write(text.encode())
        try:
            send('begin;\ntruncate '+','.join(SCHEMA+'.'+name for name in ('evaluations','forecasts','stock_classifications','daily_sales','stock','products','datasets'))+';\n')
            for table,columns,path in tables:
                send(f'copy {SCHEMA}.{table} ({columns}) from stdin with(format csv,header true);\n')
                last=b''
                with path.open('rb') as stream:
                    for line in stream:
                        last=line
                        if line.rstrip(b'\r\n')==b'\\.':raise ValueError('Unsafe standalone COPY terminator in derived CSV')
                        process.stdin.write(line)
                if last and not last.endswith(b'\n'):send('\n')
                send('\\.\n')
            send(f"insert into {SCHEMA}.datasets(id,source_label,data_origin,metadata) values('jiran-archive-20261110','Jiran.zip / nested ml:sample.zip','synthetic_generated',{literal(json.dumps(manifest))}::jsonb);\n")
            for name in ('classifier_metrics','forecast_metrics'):
                path=lab/'models'/(name+'.json')
                if path.exists():send(f"insert into {SCHEMA}.evaluations(name,metrics) values({literal(name)},{literal(path.read_text())}::jsonb);\n")
            send('commit;\n');process.stdin.close();code=process.wait()
        except Exception:
            try:process.stdin.close()
            except BrokenPipeError:pass
            process.wait();raise RuntimeError("Research import failed; inspect "+str(log))
    if code:raise RuntimeError('Research import rolled back; inspect '+str(log))
    print('Isolated synthetic research imported. Database log:',log)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--lab',type=Path,required=True)
    load(parser.parse_args().lab)
