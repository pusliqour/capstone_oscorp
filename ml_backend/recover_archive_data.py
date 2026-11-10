"""Validate recovered CSVs and build an isolated, disk-backed research dataset.

The archive explicitly identifies this as generated data. Nothing is published to
production and no supplied SQL or Python is executed by this importer.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import duckdb


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        while block:=stream.read(1024*1024):value.update(block)
    return value.hexdigest()


def catalog_sql(db):
    columns=set(db.table('source_products').columns)
    optional={
      'is_common':"try_cast(is_common as boolean) is_common",
      'expiry_date':"try_cast(expiry_date as date) expiry_date",
      'unit_quantity':"unit_quantity",
      'store_id':"nullif(trim(store_id),'') source_store_id",
    }
    types={'is_common':'boolean','expiry_date':'date','unit_quantity':'varchar','store_id':'varchar'}
    additions=[value if name in columns else f"null::{types[name]} {('source_store_id' if name=='store_id' else name)}" for name,value in optional.items()]
    return "create or replace table products as select trim(product_id) product_id,product_name,lower(trim(category)) category,try_cast(retail_price as double) retail_price,try_cast(wholesale_price as double) wholesale_price,"+','.join(additions)+" from source_products"


def recover(source, output):
    source=Path(source);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    required={
        'products.csv':{'product_id','product_name','category','retail_price','wholesale_price'},
        'stock.csv':{'store_id','product_id','stock_qty','updated_at'},
        'transactions.csv':{'transaction_id','store_id','product_id','quantity','timestamp'},
    }
    hashes={}
    for name,columns in required.items():
        with (source/name).open() as stream:headers=next(csv.reader(stream))
        if not columns.issubset(headers):raise ValueError(f'{name} is missing required columns')
        hashes[name]=digest(source/name)
    db=duckdb.connect(str(output/'archive.duckdb'))
    db.execute("set memory_limit='1GB'");db.execute('set threads=2')
    db.execute("set temp_directory=?",[str(output/'spill')])
    for name in required:
        db.read_csv(str(source/name),all_varchar=True).create_view('source_'+name[:-4],replace=True)
    db.execute(catalog_sql(db))
    db.execute('''create or replace table stock as select trim(store_id) store_id,trim(product_id) product_id,
      try_cast(stock_qty as double) stock_qty,try_cast(updated_at as timestamp) updated_at from source_stock''')
    db.execute('''create or replace table transactions as select trim(transaction_id) transaction_id,
      trim(store_id) store_id,trim(product_id) product_id,try_cast(quantity as double) quantity,
      try_cast("timestamp" as timestamp) event_time from source_transactions''')
    checks={
      'invalid_products':"select count(*) from products where product_id is null or product_id='' or product_name is null or category is null or retail_price is null or not isfinite(retail_price) or retail_price<0 or wholesale_price is null or not isfinite(wholesale_price) or wholesale_price<0",
      'duplicate_products':'select count(*)-count(distinct product_id) from products',
      'invalid_stock':"select count(*) from stock where store_id is null or store_id='' or product_id is null or stock_qty is null or not isfinite(stock_qty) or stock_qty<0 or updated_at is null",
      'duplicate_stock_pairs':'select count(*)-count(distinct (store_id,product_id)) from stock',
      'orphan_stock_products':'select count(*) from stock s left join products p using(product_id) where p.product_id is null',
      'invalid_transactions':"select count(*) from transactions where transaction_id is null or transaction_id='' or store_id is null or store_id='' or product_id is null or quantity is null or not isfinite(quantity) or quantity<=0 or event_time is null",
      'duplicate_transaction_ids':'select count(*)-count(distinct transaction_id) from transactions',
      'orphan_transaction_products':'select count(*) from transactions t left join products p using(product_id) where p.product_id is null',
      'orphan_transaction_pairs':'select count(*) from transactions t left join stock s using(store_id,product_id) where s.product_id is null',
      'unknown_transaction_stores':'select count(*) from transactions t where store_id not in(select distinct store_id from stock)',
    }
    quality={}
    for name,sql in checks.items():
        quality[name]=db.execute(sql).fetchone()[0];print(name,quality[name],flush=True)
    if any(quality.values()):
        (output/'validation-failed.json').write_text(json.dumps(quality,indent=2))
        raise ValueError('Recovered CSV integrity failed; see validation-failed.json')
    db.execute('''create or replace table daily_sales as select store_id,product_id,
      cast(event_time as date) sales_date,sum(quantity) quantity,count(*) transaction_count,
      sum(quantity*quantity) quantity_squared_sum from transactions group by all''')
    summary=db.execute('''select count(*) transaction_lines,count(distinct store_id) stores,
      count(distinct product_id) sold_products,min(event_time) first_sale,max(event_time) last_sale,
      sum(quantity) units_sold from transactions''').fetchdf().iloc[0].to_dict()
    summary={k:str(v) if k in ('first_sale','last_sale') else float(v) if k=='units_sold' else int(v) for k,v in summary.items()}
    summary.update(products=db.execute('select count(*) from products').fetchone()[0],stock_rows=db.execute('select count(*) from stock').fetchone()[0],daily_rows=db.execute('select count(*) from daily_sales').fetchone()[0])
    summary['transactions_after_stock_snapshot']=db.execute('select count(*) from transactions t join stock s using(store_id,product_id) where t.event_time>s.updated_at').fetchone()[0]
    summary['stock_pairs_without_sales']=db.execute('select count(*) from stock s where not exists(select 1 from transactions t where s.store_id=t.store_id and s.product_id=t.product_id)').fetchone()[0]
    for table in ('products','stock','daily_sales'):
        dest=str(output/(table+'.csv')).replace("'","''")
        db.execute(f"copy (select * from {table} order by 1,2) to '{dest}' (header,delimiter ',')")
    manifest={'data_origin':'synthetic_generated','source':'user-provided Jiran.zip -> ml:sample.zip -> data/*.csv','source_hashes':hashes,'validation':quality,'summary':summary,'limitations':['Generated data, not independently collected retail outcomes','Stock is a single dated snapshot','Daily zero fill assumes complete transaction capture'],'production_changed':False}
    (output/'recovery.json').write_text(json.dumps(manifest,indent=2))
    db.execute('checkpoint');db.close()
    print(json.dumps(manifest,indent=2));return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();recover(args.source,args.output)
