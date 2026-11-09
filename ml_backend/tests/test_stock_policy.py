import sys
import unittest
from pathlib import Path

ML_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML_BACKEND))

from inventory_policy import policy_metrics, stock_policy_label  # noqa: E402


class StockPolicyTests(unittest.TestCase):
    def test_missing_forecast_uses_recent_demand(self):
        metrics = policy_metrics(
            stock_qty=20,
            forecast_30d=0,
            forecast_7d=0,
            recent_qty=20,
        )
        self.assertAlmostEqual(metrics["coverage_30d_feat"], 20 / 21)
        self.assertAlmostEqual(
            metrics["days_of_stock_30d_feat"], 20 / (20 / 30 + 0.1)
        )
        self.assertEqual(metrics["stockout_risk_7d"], 0)

    def label(self, **overrides):
        row = {
            "coverage_30d_feat": 1.2,
            "days_of_stock_30d_feat": 36.0,
            "velocity_trend": 1.0,
            "forecast_acceleration": 1.0,
            "days_since_last_sale": 2.0,
            "stockout_risk_7d": 0,
        }
        row.update(overrides)
        return stock_policy_label(row)

    def test_dead_business_rules(self):
        self.assertEqual(self.label(coverage_30d_feat=8.01), "Dead")
        self.assertEqual(self.label(days_since_last_sale=91), "Dead")

    def test_slow_boundary(self):
        self.assertEqual(self.label(coverage_30d_feat=4.05), "Slow")
        self.assertEqual(
            self.label(coverage_30d_feat=3.2, velocity_trend=0.4), "Slow"
        )

    def test_low_rules(self):
        self.assertEqual(self.label(coverage_30d_feat=0.59), "Low")
        self.assertEqual(self.label(stockout_risk_7d=1), "Low")

    def test_excess_requires_healthy_velocity(self):
        self.assertEqual(
            self.label(coverage_30d_feat=3.95, velocity_trend=1.1), "Excess"
        )

    def test_default_is_optimum(self):
        self.assertEqual(self.label(), "Optimum")


if __name__ == "__main__":
    unittest.main()
