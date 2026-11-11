"""Tests for the 12 Nov 2026 additions: new products, in-stock rate, delivery time, transfers."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from inventory_policy import (in_stock_rate, is_new_product, policy_metrics, runs_out_before_delivery,
                              stock_policy_label, stock_policy_label_v2)
from transfer_policy import plan_transfers


def row(stock, f30, recent=None, days_since=1, **extra):
    r = {"stock_qty": stock, "velocity_trend": 1.0, "forecast_acceleration": 1.0, "days_since_last_sale": days_since}
    r.update(policy_metrics(stock_qty=stock, forecast_30d=f30, forecast_7d=f30 / 30 * 7, recent_qty=recent or f30))
    r.update(extra)
    return r


class PolicyAdditions(unittest.TestCase):
    def test_v2_equals_v1_without_new_inputs(self):
        for stock, f30 in [(0, 10), (5, 30), (40, 30), (100, 30), (400, 30), (50, 0)]:
            r = row(stock, f30)
            self.assertEqual(stock_policy_label_v2(r), stock_policy_label(r))

    def test_new_product(self):
        self.assertTrue(is_new_product(27)); self.assertFalse(is_new_product(28)); self.assertFalse(is_new_product(None))
        self.assertEqual(stock_policy_label_v2(row(500, 1, age_days=10)), "New")

    def test_in_stock_rate(self):
        self.assertAlmostEqual(in_stock_rate(30, 30, 0), 1.0)
        self.assertAlmostEqual(in_stock_rate(30, 30, 15), 2.0)   # half the month empty -> true rate is double
        self.assertAlmostEqual(in_stock_rate(30, 30, 29), 30 / 7)  # at least 7 days in the divisor

    def test_delivery_time(self):
        # 10 units, 1/day: lasts 10 days. Next delivery in 7 + 5 = 12 days -> Low.
        self.assertTrue(runs_out_before_delivery(10, 0, 1.0, lead_time_days=5, days_to_next_order=7))
        # Same item with 10 more units already on order -> fine.
        self.assertFalse(runs_out_before_delivery(10, 10, 1.0, lead_time_days=5, days_to_next_order=7))
        # The old rule calls 10 days of stock Low (under 14) whatever the delivery time.
        self.assertEqual(stock_policy_label(row(10, 30)), "Low")
        self.assertEqual(stock_policy_label_v2(row(10, 30, lead_time_days=1, days_to_next_order=1, daily_rate=1.0)), "Optimum")


class Transfers(unittest.TestCase):
    def rec(self, store, stock, d30, label, **kw):
        return dict(store_id=store, product_id="P", product_name="p", stock_qty=stock, demand_30d=d30, label=label, **kw)

    def test_basic_transfer_and_no_negative_stock(self):
        t, r = plan_transfers([self.rec("A", 0, 30, "Low"), self.rec("B", 200, 30, "Excess")])
        self.assertEqual(len(t), 1); self.assertEqual(t[0]["transfer_qty"], 45)
        self.assertGreaterEqual(t[0]["from_stock_after"], 0.9 * 30 - 1e-9)
        self.assertEqual(r, [])

    def test_groups_block_cross_region(self):
        t, r = plan_transfers([self.rec("A", 0, 30, "Low", group="north"), self.rec("B", 200, 30, "Excess", group="south")])
        self.assertEqual(t, []); self.assertEqual(len(r), 1)

    def test_keep_and_target_overrides(self):
        t, _ = plan_transfers([self.rec("A", 0, 30, "Low", target_stock=10), self.rec("B", 20, 30, "Dead", keep_stock=15)])
        self.assertEqual(sum(x["transfer_qty"] for x in t), 5)

    def test_new_products_never_move(self):
        t, r = plan_transfers([self.rec("A", 0, 30, "New"), self.rec("B", 200, 30, "Excess")])
        self.assertEqual((t, r), ([], []))


if __name__ == "__main__":
    unittest.main()
