import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stock_planning import stock_planning_matrix
class StockPlanningTests(unittest.TestCase):
 def test_distinct_horizons_and_stock_actions(self):
  plan=stock_planning_matrix({f'forecast_{h}d':2*h for h in (7,14,30,60)},10,age_days=90,lead_time_days=0)
  self.assertEqual([(r['recommended_min'],r['recommended_max']) for r in plan['rows']],[(20,34),(34,48),(66,80),(126,140)])
  self.assertEqual(plan['rows'][0]['add_to_min'],10)
 def test_forecast_shape_not_linear_projection(self):
  p=stock_planning_matrix({'forecast_7d':5,'forecast_14d':9,'forecast_30d':30,'forecast_60d':100},40,lead_time_days=2)
  self.assertEqual([r['recommended_min'] for r in p['rows']],[10,14,35,105])
  self.assertEqual(p['rows'][0]['above_max'],23)
 def test_cold_start_does_not_claim_optimum(self):
  p=stock_planning_matrix({f'forecast_{h}d':h for h in (7,14,30,60)},2,age_days=10)
  self.assertFalse(p['eligible']);self.assertTrue(all(r['recommended_min'] is None for r in p['rows']))
 def test_no_double_counting_open_orders_or_fake_confidence(self):
  p=stock_planning_matrix({'forecast_30d':30},0,on_order=100)
  self.assertFalse(p['assumptions']['open_orders_credited']);self.assertFalse(p['assumptions']['lead_time_known'])
  self.assertNotIn('confidence',p)
 def test_invalid_inputs(self):
  for value in (float('nan'),float('inf'),-1):
   with self.assertRaises(ValueError):stock_planning_matrix({'forecast_7d':value},10)
if __name__=='__main__':unittest.main()
