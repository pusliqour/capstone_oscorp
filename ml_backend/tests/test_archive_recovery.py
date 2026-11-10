import csv
import sys
import tempfile
import unittest
from pathlib import Path
import duckdb
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from recover_archive_data import recover
from train_archive_lab import load_features, forecast_experiments
from unittest.mock import patch
import numpy as np
import pandas as pd

class ArchiveRecoveryTests(unittest.TestCase):
    def fixture(self,root,duplicate=False,orphan=False):
        root.mkdir()
        data={
            'products.csv':[['product_id','product_name','category','retail_price','wholesale_price'],['P1','Test Product','pantry',2,1],['P2','Other Product','pantry',3,1]],
            'stock.csv':[['store_id','product_id','stock_qty','updated_at'],['A','P1',100,'2026-01-31'],['B','P2',5,'2026-01-31']],
            'transactions.csv':[['transaction_id','store_id','product_id','quantity','timestamp'],['T1','A','P1',2,'2026-01-29'],['T1' if duplicate else 'T2','A','P2' if orphan else 'P1',3,'2026-01-30'],['T3','A','P1',1000,'2026-02-01']],
        }
        for name,rows in data.items():
            with (root/name).open('w',newline='') as stream:csv.writer(stream).writerows(rows)
    def test_recovers_and_flags_future_data_without_using_it_in_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);self.fixture(base/'source')
            report=recover(base/'source',base/'out')
            self.assertEqual(report['data_origin'],'synthetic_generated')
            self.assertEqual(report['summary']['transactions_after_stock_snapshot'],1)
            db=duckdb.connect(str(base/'out/archive.duckdb'),read_only=True)
            frame,cutoff=load_features(db);db.close()
            observed=frame.loc[frame.store_id=='A'].iloc[0]
            self.assertEqual(observed.recent_qty,5)
            self.assertEqual(observed.num_sales,2)
            self.assertEqual(observed.recent_avg,2.5)
            self.assertAlmostEqual(observed.recent_std,0.70710678)
            self.assertEqual(str(cutoff.date()),'2026-01-31')
    def test_forecast_series_selection_does_not_use_future_volume(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)
            db=duckdb.connect()
            db.execute("create table stock(store_id varchar,product_id varchar,stock_qty double,updated_at timestamp)")
            db.execute("insert into stock values ('A','P1',10,'2026-04-01'),('A','P2',10,'2026-04-01')")
            db.execute("create table products(product_id varchar,product_name varchar,category varchar,retail_price double)")
            db.execute("insert into products values ('P1','Early seller','pantry',2),('P2','Late surge','pantry',2)")
            db.execute("create table daily_sales(store_id varchar,product_id varchar,sales_date date,quantity double,transaction_count bigint,quantity_squared_sum double)")
            db.execute("insert into daily_sales select 'A','P1',cast(d as date),1,1,1 from generate_series(timestamp '2026-01-01',timestamp '2026-03-31',interval '1 day') t(d)")
            db.execute("insert into daily_sales select 'A','P2',cast(d as date),1000,1000,1000 from generate_series(timestamp '2026-03-15',timestamp '2026-03-31',interval '1 day') t(d)")
            frame,cutoff=load_features(db)
            self.assertGreater(frame.loc[frame.product_id=='P2','total_sold'].iloc[0],frame.loc[frame.product_id=='P1','total_sold'].iloc[0])
            with patch('train_archive_lab.selected_forecast',side_effect=lambda series,horizon:{'method':'weekly_naive','values':np.ones(horizon),'validation_mae':0,'daily_error':0}):
                result,metrics=forecast_experiments(db,frame,cutoff,output)
            selected=result.loc[result.forecast_method=='weekly_naive','product_id'].tolist()
            self.assertEqual(selected,['P1'])
            self.assertEqual(metrics['folds'],2)
            db.close()
    def test_duplicate_transaction_ids_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);self.fixture(base/'source',duplicate=True)
            with self.assertRaisesRegex(ValueError,'integrity failed'):recover(base/'source',base/'out')
    def test_cross_store_product_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);self.fixture(base/'source',orphan=True)
            with self.assertRaisesRegex(ValueError,'integrity failed'):recover(base/'source',base/'out')

if __name__=='__main__':unittest.main()
