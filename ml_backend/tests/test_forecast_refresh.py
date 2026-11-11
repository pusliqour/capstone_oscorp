"""Forecast refresh ("unfrozen" forecasts) and stock-out correction."""
import os, sys, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app  # noqa: E402
from forecasting import uncensor  # noqa: E402


def product(**kw):
    base = dict(store_id="STORE_BUSINESS_BAY", product_id="JRN-0032", category="snacks", stock_qty=10, retail_price=5, recent_qty=60)
    base.update(kw)
    return app.ProductInput(**base)


class Refresh(unittest.TestCase):
    def test_stale_saved_forecast_is_replaced_by_live_rate(self):
        old = app.FORECAST_MAX_AGE_DAYS
        try:
            app.FORECAST_MAX_AGE_DAYS = -1  # every saved forecast counts as stale
            fc = app.get_forecast_features(product())
            self.assertEqual(fc["forecast_method"], "observed_recent_sales")
            self.assertAlmostEqual(fc["forecast_30d"], 60.0)
        finally:
            app.FORECAST_MAX_AGE_DAYS = old

    def test_stockout_days_raise_live_rate(self):
        app_old = app.FORECAST_MAX_AGE_DAYS
        try:
            app.FORECAST_MAX_AGE_DAYS = -1
            fc = app.get_forecast_features(product(stockout_days_30d=15))
            self.assertAlmostEqual(fc["forecast_30d"], 120.0)  # 60 units in 15 in-stock days
        finally:
            app.FORECAST_MAX_AGE_DAYS = app_old

    def test_daily_sales_give_fresh_forecast(self):
        fc = app.get_forecast_features(product(daily_sales=[2.0] * 60))
        self.assertTrue(fc["forecast_method"].startswith("live_"))
        self.assertAlmostEqual(fc["forecast_30d"], 60.0, places=6)


class Uncensor(unittest.TestCase):
    def test_stockout_days_filled_with_in_stock_mean(self):
        sales = np.array([2.0] * 20 + [0.0, 0.0]); stock = np.array([5] * 20 + [0, 0])
        np.testing.assert_allclose(uncensor(sales, stock)[-2:], [2.0, 2.0])

    def test_untouched_without_stockouts(self):
        sales = np.arange(10.0); np.testing.assert_array_equal(uncensor(sales, np.ones(10)), sales)


if __name__ == "__main__":
    unittest.main()
