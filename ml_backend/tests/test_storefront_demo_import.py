import sys
import unittest
from pathlib import Path

import pandas as pd

ML_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML_BACKEND))

from storefront_demo import STORE_LOGIN_EMAILS, build_storefront_snapshot  # noqa: E402


class StorefrontDemoImportTests(unittest.TestCase):
    def test_builds_store_scoped_products_orders_and_totals(self):
        products = pd.DataFrame(
            [
                {
                    "product_id": "SKU-1",
                    "product_name": "Tea",
                    "category": "beverages",
                    "retail_price": 12.5,
                },
                {
                    "product_id": "SKU-2",
                    "product_name": "Bread",
                    "category": "bakery",
                    "retail_price": 5.0,
                },
            ]
        )
        stock = pd.DataFrame(
            [
                {
                    "store_id": "STORE_BUSINESS_BAY",
                    "product_id": "SKU-1",
                    "stock_qty": 20,
                    "updated_at": "2026-03-31T20:36:12Z",
                },
                {
                    "store_id": "STORE_BUSINESS_BAY",
                    "product_id": "SKU-2",
                    "stock_qty": 4,
                    "updated_at": "2026-03-31T20:36:12Z",
                },
            ]
        )
        transactions = pd.DataFrame(
            [
                {
                    "transaction_id": "ORDER-1",
                    "store_id": "STORE_BUSINESS_BAY",
                    "product_id": "SKU-1",
                    "quantity": 2,
                    "timestamp": "2026-03-31T18:00:00Z",
                },
                {
                    "transaction_id": "ORDER-1",
                    "store_id": "STORE_BUSINESS_BAY",
                    "product_id": "SKU-2",
                    "quantity": 1,
                    "timestamp": "2026-03-31T18:00:00Z",
                },
            ]
        )

        snapshot = build_storefront_snapshot(transactions, stock, products)
        store = snapshot["STORE_BUSINESS_BAY"]

        self.assertEqual(STORE_LOGIN_EMAILS["STORE_BUSINESS_BAY"], "research01@jiran.test")
        self.assertEqual(store["store_name"], "Business Bay")
        self.assertEqual(len(store["products"]), 2)
        self.assertEqual(store["products"][0]["stock_qty"], 20)
        self.assertEqual(len(store["orders"]), 1)
        self.assertEqual(store["orders"][0]["external_order_id"], "ORDER-1")
        self.assertEqual(store["orders"][0]["total_amount"], 30.0)
        self.assertEqual(len(store["orders"][0]["items"]), 2)

    def test_rejects_store_without_demo_login_mapping(self):
        products = pd.DataFrame(
            [{"product_id": "SKU-1", "product_name": "Tea", "category": "beverages", "retail_price": 1.0}]
        )
        stock = pd.DataFrame(
            [{"store_id": "STORE_UNKNOWN", "product_id": "SKU-1", "stock_qty": 1, "updated_at": "2026-01-01T00:00:00Z"}]
        )
        transactions = pd.DataFrame(
            [{"transaction_id": "O-1", "store_id": "STORE_UNKNOWN", "product_id": "SKU-1", "quantity": 1, "timestamp": "2026-01-01T00:00:00Z"}]
        )

        with self.assertRaisesRegex(ValueError, "No demo login mapping"):
            build_storefront_snapshot(transactions, stock, products)


if __name__ == "__main__":
    unittest.main()
