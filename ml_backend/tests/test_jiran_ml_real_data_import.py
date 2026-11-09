import sys
import unittest
from pathlib import Path

import pandas as pd

ML_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML_BACKEND))

from import_jiran_ml_real_data import (  # noqa: E402
    build_ml_inventory,
    normalize_store_id,
    transform_exports,
)


class JiranMlImportTests(unittest.TestCase):
    def setUp(self):
        self.catalog = pd.DataFrame(
            [
                {
                    "Product": "Tea",
                    "SKU": "JRN-0001",
                    "Categories": "Beverages",
                    "Price": 12.5,
                    "Current Quantity Store One": 20,
                    "Location": "Store One",
                },
                {
                    "Product": "Bread",
                    "SKU": "JRN-0002",
                    "Categories": "Bakery",
                    "Price": 5.0,
                    "Current Quantity Store One": 4,
                    "Location": "Store One",
                },
            ]
        )
        self.orders = pd.DataFrame(
            [
                {
                    "external_order_id": "SA-1",
                    "order_time": "2025-09-01T10:00:00+00:00",
                    "external_location_id": "Store One",
                    "sku": "JRN-0001",
                    "quantity": 2,
                },
                {
                    "external_order_id": "SA-2",
                    "order_time": "2025-10-10T10:00:00+00:00",
                    "external_location_id": "Store One",
                    "sku": "JRN-0001",
                    "quantity": 3,
                },
            ]
        )

    def test_store_ids_are_stable_and_machine_safe(self):
        self.assertEqual(normalize_store_id("Store One"), "STORE_STORE_ONE")
        self.assertEqual(normalize_store_id(" Store / Two "), "STORE_STORE_TWO")

    def test_exports_become_training_contract(self):
        transactions, stock, products = transform_exports([self.catalog], [self.orders])

        self.assertEqual(
            list(transactions.columns),
            ["transaction_id", "store_id", "product_id", "quantity", "timestamp"],
        )
        self.assertEqual(
            list(stock.columns),
            ["store_id", "product_id", "stock_qty", "updated_at"],
        )
        self.assertEqual(
            list(products.columns),
            ["product_id", "product_name", "category", "retail_price"],
        )
        self.assertEqual(set(transactions["store_id"]), {"STORE_STORE_ONE"})
        self.assertEqual(products.set_index("product_id").loc["JRN-0001", "category"], "beverages")

    def test_inventory_uses_dataset_as_of_date_for_recent_sales(self):
        transactions, stock, products = transform_exports([self.catalog], [self.orders])
        inventory = build_ml_inventory(transactions, stock, products)
        tea = inventory.set_index(["store_id", "product_id"]).loc[
            ("STORE_STORE_ONE", "JRN-0001")
        ]

        self.assertEqual(tea["recent_qty"], 3)
        self.assertEqual(tea["historical_qty"], 2)
        self.assertEqual(tea["total_sold"], 5)
        self.assertEqual(tea["days_since_last_sale"], 0)
        self.assertEqual(tea["stock_qty"], 20)

    def test_conflicting_store_exclusive_skus_are_namespaced(self):
        second_catalog = pd.DataFrame(
            [
                {
                    "Product": "Different Item",
                    "SKU": "JRN-0001",
                    "Categories": "Household",
                    "Price": 99.0,
                    "Current Quantity Store Two": 8,
                    "Location": "Store Two",
                }
            ]
        )
        second_orders = pd.DataFrame(
            [
                {
                    "external_order_id": "SB-1",
                    "order_time": "2025-10-10T10:00:00+00:00",
                    "external_location_id": "Store Two",
                    "sku": "JRN-0001",
                    "quantity": 1,
                }
            ]
        )

        transactions, stock, products = transform_exports(
            [self.catalog, second_catalog], [self.orders, second_orders]
        )

        conflicting_ids = set(
            products.loc[
                products["product_name"].isin(["Tea", "Different Item"]),
                "product_id",
            ]
        )
        self.assertEqual(
            conflicting_ids,
            {"STORE_STORE_ONE::JRN-0001", "STORE_STORE_TWO::JRN-0001"},
        )
        self.assertEqual(
            set(
                transactions.loc[
                    transactions["transaction_id"].isin(["SA-1", "SA-2", "SB-1"]),
                    "product_id",
                ]
            ),
            conflicting_ids,
        )
        self.assertTrue(conflicting_ids.issubset(set(stock["product_id"])))


    def test_invalid_numeric_values_are_rejected(self):
        bad_catalog = self.catalog.copy()
        bad_catalog.loc[0, "Current Quantity Store One"] = -1
        with self.assertRaisesRegex(ValueError, "finite values at least 0"):
            transform_exports([bad_catalog], [self.orders])

        bad_orders = self.orders.copy()
        bad_orders.loc[0, "quantity"] = 0
        with self.assertRaisesRegex(ValueError, "finite values greater than 0"):
            transform_exports([self.catalog], [bad_orders])

    def test_unknown_order_sku_is_rejected(self):
        bad_orders = self.orders.copy()
        bad_orders.loc[0, "sku"] = "MISSING"
        with self.assertRaisesRegex(ValueError, "missing from catalogs"):
            transform_exports([self.catalog], [bad_orders])


if __name__ == "__main__":
    unittest.main()
