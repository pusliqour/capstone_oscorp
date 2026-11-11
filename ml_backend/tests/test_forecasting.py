import sys
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from forecasting import daily_series, forecast_daily, selected_forecast
from augmentation import simulate
from inventory_policy import stock_policy_label

class ForecastingTests(unittest.TestCase):
    def test_calendar_gaps_and_stale_tail_are_zero_filled(self):
        frame=pd.DataFrame({'ds':pd.to_datetime(['2026-01-01','2026-01-03']),'y':[2,4]})
        result=daily_series(frame,pd.Timestamp('2026-01-05'))
        self.assertEqual(result.tolist(),[2,0,4,0,0])
    def test_weekly_forecast_uses_latest_week(self):
        series=pd.Series(np.arange(42),index=pd.date_range('2026-01-01',periods=42))
        self.assertEqual(forecast_daily(series,9,'weekly_naive').tolist(),[35,36,37,38,39,40,41,35,36])
    def test_selection_never_fits_on_its_validation_days(self):
        series=pd.Series(np.ones(56),index=pd.date_range('2026-01-01',periods=56))
        calls=[]
        def fake(history,horizon,method):
            calls.append((len(history),history.index.max(),method))
            return np.ones(horizon) if method=='weekly_naive' else np.full(horizon,10)
        with patch('forecasting.forecast_daily',side_effect=fake):
            selected=selected_forecast(series,7)
        self.assertEqual(selected['method'],'weekly_naive')
        self.assertTrue(all(n==28 and stamp==series.index[27] for n,stamp,_ in calls[:-1]))
        self.assertEqual(calls[-1][0],56)
    def test_policy_simulation_updates_recency_and_preserves_source(self):
        row={'stock_qty':100,'retail_price':5,'recent_avg':2,'historical_avg':2,'recent_std':1,'recent_qty':30,'forecast_30d':30,'forecast_7d':7,'days_since_last_sale':1,'forecast_acceleration':1}
        variant=simulate(row,{'days_since_last_sale':365,'recent_qty':0,'recent_avg':0})
        self.assertEqual(stock_policy_label(variant),'Dead')
        self.assertEqual(variant['is_active'],0)
        self.assertEqual(variant['days_since_over_90'],1)
        self.assertEqual(row['days_since_last_sale'],1)

    def test_short_history_falls_back_to_recent_mean(self):
        series=pd.Series(np.ones(55),index=pd.date_range('2026-01-01',periods=55))
        self.assertEqual(selected_forecast(series,7)['method'],'recent_mean')

if __name__=='__main__':unittest.main()
