"""Concern A9: every ratio in the stock policy is defined at the edges (zero stock,
zero sales, zero days, empty history) and never divides by zero or returns NaN/inf.
Also C1: the stock-range width uses the ordering cadence, not days until the next order.

Guards being tested (symbols as in docs/mlp and the paper):
  coverage      = stock / (demand_30d + 1)            -> +1 units
  days of stock = stock / (demand_30d / 30 + 0.1)     -> +0.1 units/day
  in-stock rate = sold / max(in-stock days, min(7, days), 1)
  missing forecast -> demand_30d = max(recent_qty, 1), demand_7d = max(recent_qty / 4, 1)
"""
import math, sys, unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app  # noqa: E402
from forecasting import selected_forecast, uncensor  # noqa: E402
from inventory_policy import (donor_reserve, in_stock_rate, policy_metrics, receiver_target_stock,  # noqa: E402
                              runs_out_before_delivery, stock_policy_label, stock_policy_label_v2)
from stock_planning import stock_planning_matrix  # noqa: E402
from transfer_policy import plan_transfers  # noqa: E402


def finite(*xs):
    return all(math.isfinite(float(x)) for x in xs)


def label_row(stock, f30, f7, recent, since=0.0, vel=1.0, **extra):
    row = dict(stock_qty=stock, velocity_trend=vel, forecast_acceleration=(f7 / 7) / (f30 / 30 + 0.1),
               days_since_last_sale=since, **policy_metrics(stock_qty=stock, forecast_30d=f30, forecast_7d=f7, recent_qty=recent))
    row.update(extra)
    return row


class PolicyRatios(unittest.TestCase):
    def test_policy_metrics_finite_for_all_zero_inputs(self):
        for stock in (0, 1, 10_000):
            for f30, f7, recent in ((0, 0, 0), (0, 0, 5), (30, 7, 0), (1e-9, 1e-9, 0)):
                m = policy_metrics(stock_qty=stock, forecast_30d=f30, forecast_7d=f7, recent_qty=recent)
                self.assertTrue(finite(*m.values()), (stock, f30, f7, recent, m))

    def test_labels_defined_at_edges(self):
        for stock in (0, 5, 1e6):
            for f30 in (0, 30):
                lab = stock_policy_label(label_row(stock, f30, f30 / 4, 0))
                self.assertIn(lab, {"Dead", "Slow", "Low", "Excess", "Optimum"})
        self.assertEqual(stock_policy_label(label_row(0, 30, 7, 30)), "Low")        # empty shelf, selling item
        self.assertEqual(stock_policy_label(label_row(50, 0, 0, 0, since=200)), "Dead")  # never sells

    def test_v2_label_with_zero_rate_and_zero_lead_time(self):
        row = label_row(10, 0, 0, 0, daily_rate=0.0, lead_time_days=0.0, days_to_next_order=0.0, on_order=0.0, age_days=100)
        self.assertIn(stock_policy_label_v2(row), {"Dead", "Slow", "Low", "Excess", "Optimum"})
        self.assertFalse(runs_out_before_delivery(10, 0, 0.0, 0, 0))  # no demand -> cannot run out

    def test_in_stock_rate_never_divides_by_zero(self):
        self.assertEqual(in_stock_rate(0, 0, 0), 0.0)
        self.assertEqual(in_stock_rate(5, 0, 0), 5.0)          # denominator floors at 1 day
        self.assertEqual(in_stock_rate(70, 30, 30), 10.0)      # all days out of stock -> 7-day floor
        self.assertTrue(finite(in_stock_rate(3, 2, 5)))         # more stock-out days than days

    def test_sizing_helpers_nonnegative(self):
        self.assertEqual(receiver_target_stock(0, 0, 0), 0.0)
        self.assertEqual(receiver_target_stock(1, 3, 1000), 0.0)  # open orders exceed need -> 0, not negative
        self.assertEqual(donor_reserve(0, 0), 0.0)


class Forecasts(unittest.TestCase):
    def test_uncensor_all_zero_and_all_stockout(self):
        z = np.zeros(40)
        self.assertTrue(np.isfinite(uncensor(z, z)).all())
        self.assertTrue(np.isfinite(uncensor(np.ones(40), np.zeros(40))).all())

    def test_selected_forecast_short_and_zero_history(self):
        for n in (60, 14, 0):
            series = pd.Series(np.zeros(n), index=pd.date_range("2026-01-01", periods=n, freq="D"))
            fc = selected_forecast(series, 30, methods=("weekly_naive", "recent_mean"))["values"]
            self.assertEqual(len(fc), 30)
            self.assertTrue(np.isfinite(np.asarray(fc, float)).all())
            self.assertGreaterEqual(float(np.min(fc)), 0.0)


class StockRangesAndTransfers(unittest.TestCase):
    def test_stock_matrix_zero_forecast(self):
        p = stock_planning_matrix({}, 0, age_days=100, lead_time_days=0)
        self.assertTrue(all(r["recommended_min"] == 0 and r["recommended_max"] == 0 for r in p["rows"]))

    def test_transfers_with_zero_demand_everywhere(self):
        recs = [dict(store_id="A", product_id="P", product_name="p", stock_qty=0, demand_30d=0, label="Low"),
                dict(store_id="B", product_id="P", product_name="p", stock_qty=10, demand_30d=0, label="Dead")]
        transfers, restocks = plan_transfers(recs)
        self.assertEqual(transfers, []); self.assertEqual(restocks, [])  # no demand -> nothing to move

    def test_transfer_conserves_units_and_never_goes_negative(self):
        recs = [dict(store_id="A", product_id="P", product_name="p", stock_qty=0, demand_30d=30, label="Low"),
                dict(store_id="B", product_id="P", product_name="p", stock_qty=0.6, demand_30d=0, label="Dead"),
                dict(store_id="C", product_id="P", product_name="p", stock_qty=100, demand_30d=10, label="Excess")]
        transfers, _ = plan_transfers(recs)
        for t in transfers:
            self.assertGreaterEqual(t["from_stock_after"], 0); self.assertGreaterEqual(t["transfer_qty"], 1)
            self.assertAlmostEqual(t["from_stock_before"] - t["from_stock_after"], t["transfer_qty"], places=1)


class OrderCycle(unittest.TestCase):
    """C1: ordering tomorrow must not shrink the stock range to a 1-day review cycle."""
    def _plan(self, **kw):
        p = app.ProductInput(store_id="STORE_BUSINESS_BAY", product_id="JRN-0032", category="snacks", stock_qty=10,
                             retail_price=5, recent_qty=60, lead_time_days=2, age_days=100, **kw)
        return app._run_predictions([p])[0].stock_plan

    def test_days_to_next_order_does_not_set_review_cycle(self):
        self.assertEqual(self._plan(days_to_next_order=1)["assumptions"]["review_cycle_days"], 7)
        self.assertEqual(self._plan(days_to_next_order=1, order_cycle_days=14)["assumptions"]["review_cycle_days"], 14)


class Attribution(unittest.TestCase):
    """A1: the label names the component that set it; the ensemble never sets it."""
    def _pred(self, **kw):
        p = app.ProductInput(store_id="STORE_BUSINESS_BAY", product_id="JRN-0032", category="snacks", stock_qty=10,
                             retail_price=5, recent_qty=60, **kw)
        return app._run_predictions([p])[0]

    def test_sources(self):
        self.assertEqual(self._pred().decision_source, "stock_policy_v1")
        self.assertEqual(self._pred(lead_time_days=3, age_days=100).decision_source, "stock_policy_v2_delivery")
        new = self._pred(age_days=5)
        self.assertEqual((new.prediction, new.decision_source), ("New", "new_product_gate"))
        self.assertFalse(new.model_agrees)  # the ensemble has no "New" class


if __name__ == "__main__":
    unittest.main()
