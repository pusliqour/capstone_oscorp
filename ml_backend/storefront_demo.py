"""Populate the retailer-facing Supabase tables from normalized Jiran data.

The ML bridge intentionally keeps raw features in ``ml_inventory``.  This module
creates the application records needed by Inventory and Analytics, while mapping
one existing research demo login to each real store.
"""

from __future__ import annotations

import argparse
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from supabase import Client, create_client


STORE_LOGIN_EMAILS = {
    "STORE_BUSINESS_BAY": "research01@jiran.test",
    "STORE_DUBAI_MARINA": "research02@jiran.test",
    "STORE_JUMEIRAH": "research03@jiran.test",
}

STORE_NAMES = {
    "STORE_BUSINESS_BAY": "Business Bay",
    "STORE_DUBAI_MARINA": "Dubai Marina",
    "STORE_JUMEIRAH": "Jumeirah",
}


def _number(value: Any) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Expected a finite numeric value, got {value!r}")
    return number


def _records_in_batches(rows: list[dict[str, Any]], size: int = 500) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def build_storefront_snapshot(
    transactions: pd.DataFrame,
    stock: pd.DataFrame,
    products: pd.DataFrame,
) -> dict[str, dict[str, Any]]:
    """Build deterministic, store-scoped products and orders for the UI tables."""
    store_ids = sorted(set(stock["store_id"].astype(str)))
    unmapped = [store_id for store_id in store_ids if store_id not in STORE_LOGIN_EMAILS]
    if unmapped:
        raise ValueError(f"No demo login mapping for store(s): {', '.join(unmapped)}")

    product_lookup = {
        str(row.product_id): {
            "product_id": str(row.product_id),
            "product_name": str(row.product_name),
            "category": str(row.category),
            "retail_price": _number(row.retail_price),
        }
        for row in products.itertuples(index=False)
    }

    snapshot: dict[str, dict[str, Any]] = {}
    for store_id in store_ids:
        store_stock = stock.loc[stock["store_id"].astype(str) == store_id].copy()
        product_rows = []
        for row in store_stock.sort_values("product_id").itertuples(index=False):
            product_id = str(row.product_id)
            product = product_lookup.get(product_id)
            if product is None:
                raise ValueError(f"Stock product {product_id} is missing from products")
            product_rows.append(
                {
                    **product,
                    "stock_qty": _number(row.stock_qty),
                    "updated_at": pd.Timestamp(row.updated_at).isoformat(),
                }
            )

        store_transactions = transactions.loc[
            transactions["store_id"].astype(str) == store_id
        ].copy()
        orders: list[dict[str, Any]] = []
        for transaction_id, group in store_transactions.groupby(
            "transaction_id", sort=True
        ):
            items = []
            order_times = pd.to_datetime(group["timestamp"], utc=True)
            for row in group.itertuples(index=False):
                product_id = str(row.product_id)
                product = product_lookup.get(product_id)
                if product is None:
                    raise ValueError(
                        f"Transaction product {product_id} is missing from products"
                    )
                quantity = _number(row.quantity)
                items.append(
                    {
                        "product_id": product_id,
                        "item_name": product["product_name"],
                        "quantity": quantity,
                        "total_amount": round(quantity * product["retail_price"], 2),
                    }
                )
            orders.append(
                {
                    "external_order_id": str(transaction_id),
                    "external_location_id": store_id,
                    "order_time": order_times.max().isoformat(),
                    "total_amount": round(sum(item["total_amount"] for item in items), 2),
                    "items": items,
                }
            )

        snapshot[store_id] = {
            "store_id": store_id,
            "store_name": STORE_NAMES.get(
                store_id, store_id.removeprefix("STORE_").replace("_", " ").title()
            ),
            "login_email": STORE_LOGIN_EMAILS[store_id],
            "products": product_rows,
            "orders": orders,
        }

    return snapshot


def _delete_existing_demo_rows(client: Client, retailer_ids: list[str]) -> None:
    connection_rows = (
        client.table("pos_connections")
        .select("id")
        .in_("retailer_id", retailer_ids)
        .execute()
        .data
        or []
    )
    connection_ids = [str(row["id"]) for row in connection_rows]

    client.table("ml_inventory_predictions").delete().in_(
        "retailer_id", retailer_ids
    ).execute()
    client.table("ml_inventory_transfer_recommendations").delete().or_(
        f"from_retailer_id.in.({','.join(retailer_ids)}),to_retailer_id.in.({','.join(retailer_ids)})"
    ).execute()

    if connection_ids:
        order_rows = (
            client.table("orders")
            .select("id")
            .in_("pos_connection_id", connection_ids)
            .execute()
            .data
            or []
        )
        order_ids = [str(row["id"]) for row in order_rows]
        for batch in _records_in_batches(
            [{"id": order_id} for order_id in order_ids], size=100
        ):
            client.table("order_items").delete().in_(
                "order_id", [row["id"] for row in batch]
            ).execute()
        client.table("orders").delete().in_("pos_connection_id", connection_ids).execute()

        variation_rows = (
            client.table("product_variations")
            .select("id")
            .in_("pos_connection_id", connection_ids)
            .execute()
            .data
            or []
        )
        variation_ids = [str(row["id"]) for row in variation_rows]
        if variation_ids:
            client.table("product_inventory").delete().in_(
                "product_variation_id", variation_ids
            ).execute()
        client.table("product_variations").delete().in_(
            "pos_connection_id", connection_ids
        ).execute()
        client.table("products").delete().in_(
            "pos_connection_id", connection_ids
        ).execute()
        client.table("connection_intelligence").delete().in_(
            "pos_connection_id", connection_ids
        ).execute()
        client.table("pos_connections").delete().in_(
            "id", connection_ids
        ).execute()


def _auth_users_by_email(client: Client) -> dict[str, str]:
    response = client.auth.admin.list_users()
    users = response if isinstance(response, list) else getattr(response, "users", [])
    return {
        str(user.email).lower(): str(user.id)
        for user in users
        if getattr(user, "email", None)
    }


def push_storefront_snapshot(
    client: Client,
    snapshot: dict[str, dict[str, Any]],
    predictions: pd.DataFrame | None = None,
    transfers: pd.DataFrame | None = None,
) -> dict[str, int]:
    """Replace demo-store application rows and return inserted row counts."""
    users_by_email = _auth_users_by_email(client)
    store_user_ids: dict[str, str] = {}
    for store_id, store in snapshot.items():
        email = store["login_email"].lower()
        user_id = users_by_email.get(email)
        if not user_id:
            raise ValueError(f"Demo auth user does not exist: {email}")
        store_user_ids[store_id] = user_id

    retailer_ids = list(store_user_ids.values())
    _delete_existing_demo_rows(client, retailer_ids)

    counts: defaultdict[str, int] = defaultdict(int)
    connection_ids: dict[str, str] = {}
    variation_ids: dict[tuple[str, str], str] = {}

    for store_id, store in snapshot.items():
        retailer_id = store_user_ids[store_id]
        client.table("retailer_profiles").update(
            {"shop_name": store["store_name"], "store_id": store_id}
        ).eq("id", retailer_id).execute()

        connection = (
            client.table("pos_connections")
            .insert(
                {
                    "retailer_id": retailer_id,
                    "provider": "jiran_square_import",
                    "status": "connected",
                    "is_active": True,
                    "last_synced_at": max(
                        product["updated_at"] for product in store["products"]
                    ),
                }
            )
            .execute()
            .data[0]
        )
        connection_id = str(connection["id"])
        connection_ids[store_id] = connection_id
        counts["pos_connections"] += 1

        product_payloads = [
            {
                "retailer_id": retailer_id,
                "pos_connection_id": connection_id,
                "sku": product["product_id"],
                "name": product["product_name"],
                "category": product["category"],
                "price": product["retail_price"],
                "active": True,
                "updated_at": product["updated_at"],
            }
            for product in store["products"]
        ]
        inserted_products: list[dict[str, Any]] = []
        for batch in _records_in_batches(product_payloads):
            inserted_products.extend(
                client.table("products").insert(batch).execute().data or []
            )
        counts["products"] += len(inserted_products)
        product_db_ids = {row["sku"]: str(row["id"]) for row in inserted_products}

        variation_payloads = [
            {
                "product_id": product_db_ids[product["product_id"]],
                "pos_connection_id": connection_id,
                "sku": product["product_id"],
                "name": "Regular",
                "price": product["retail_price"],
                "currency": "AED",
                "active": True,
                "updated_at": product["updated_at"],
            }
            for product in store["products"]
        ]
        inserted_variations: list[dict[str, Any]] = []
        for batch in _records_in_batches(variation_payloads):
            inserted_variations.extend(
                client.table("product_variations").insert(batch).execute().data or []
            )
        counts["product_variations"] += len(inserted_variations)
        for row in inserted_variations:
            variation_ids[(store_id, str(row["sku"]))] = str(row["id"])

        inventory_payloads = [
            {
                "product_variation_id": variation_ids[(store_id, product["product_id"])],
                "pos_connection_id": connection_id,
                "pos_location_id": store_id,
                "quantity": product["stock_qty"],
                "updated_at": product["updated_at"],
            }
            for product in store["products"]
        ]
        for batch in _records_in_batches(inventory_payloads):
            client.table("product_inventory").insert(batch).execute()
        counts["product_inventory"] += len(inventory_payloads)

        order_payloads = [
            {
                "retailer_id": retailer_id,
                "pos_connection_id": connection_id,
                "source": "jiran_square_import",
                "status": "completed",
                "order_time": order["order_time"],
                "total_amount": order["total_amount"],
                "currency": "AED",
                "external_order_id": order["external_order_id"],
                "external_location_id": store_id,
                "is_active": True,
            }
            for order in store["orders"]
        ]
        inserted_orders: list[dict[str, Any]] = []
        for batch in _records_in_batches(order_payloads):
            inserted_orders.extend(
                client.table("orders").insert(batch).execute().data or []
            )
        counts["orders"] += len(inserted_orders)
        order_db_ids = {
            str(row["external_order_id"]): str(row["id"])
            for row in inserted_orders
        }

        item_payloads = [
            {
                "order_id": order_db_ids[order["external_order_id"]],
                "item_name": item["item_name"],
                "quantity": item["quantity"],
                "total_amount": item["total_amount"],
                "currency": "AED",
                "is_active": True,
            }
            for order in store["orders"]
            for item in order["items"]
        ]
        for batch in _records_in_batches(item_payloads):
            client.table("order_items").insert(batch).execute()
        counts["order_items"] += len(item_payloads)

        client.table("connection_intelligence").insert(
            {
                "pos_connection_id": connection_id,
                "needs_more_data": False,
                "units_sold": sum(
                    item["quantity"]
                    for order in store["orders"]
                    for item in order["items"]
                ),
            }
        ).execute()
        counts["connection_intelligence"] += 1

    if predictions is not None and not predictions.empty:
        prediction_payloads = []
        for row in predictions.itertuples(index=False):
            key = (str(row.store_id), str(row.product_id))
            variation_id = variation_ids.get(key)
            if not variation_id:
                raise ValueError(f"Prediction has no storefront variation: {key}")
            prediction_payloads.append(
                {
                    "retailer_id": store_user_ids[key[0]],
                    "pos_connection_id": connection_ids[key[0]],
                    "product_variation_id": variation_id,
                    "product_name": str(row.product_name),
                    "prediction": str(row.prediction),
                    "confidence": _number(row.confidence),
                }
            )
        for batch in _records_in_batches(prediction_payloads):
            client.table("ml_inventory_predictions").insert(batch).execute()
        counts["ml_inventory_predictions"] += len(prediction_payloads)

    if transfers is not None and not transfers.empty:
        transfer_payloads = []
        for row in transfers.itertuples(index=False):
            from_store = str(row.from_store)
            to_store = str(row.to_store)
            product_id = str(row.product_id)
            transfer_payloads.append(
                {
                    "product_name": next(
                        product["product_name"]
                        for product in snapshot[from_store]["products"]
                        if product["product_id"] == product_id
                    ),
                    "transfer_qty": _number(row.transfer_qty),
                    "from_label": str(row.from_label),
                    "to_label": str(row.to_label),
                    "from_stock_before": _number(row.from_stock_before),
                    "from_stock_after": _number(row.from_stock_after),
                    "to_stock_before": _number(row.to_stock_before),
                    "to_stock_after": _number(row.to_stock_after),
                    "demand_30d": _number(row.demand_30d),
                    "from_coverage_after": _number(row.from_coverage_after),
                    "to_coverage_after": _number(row.to_coverage_after),
                    "from_retailer_id": store_user_ids[from_store],
                    "to_retailer_id": store_user_ids[to_store],
                    "from_pos_connection_id": connection_ids[from_store],
                    "to_pos_connection_id": connection_ids[to_store],
                    "from_product_variation_id": variation_ids[(from_store, product_id)],
                    "to_product_variation_id": variation_ids[(to_store, product_id)],
                }
            )
        client.table("ml_inventory_transfer_recommendations").insert(
            transfer_payloads
        ).execute()
        counts["ml_inventory_transfer_recommendations"] += len(transfer_payloads)

    return dict(counts)


def latest_output(ml_outputs: Path, suffix: str) -> Path | None:
    matches = sorted(ml_outputs.glob(f"*_{suffix}.csv"))
    return matches[-1] if matches else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("training/data"))
    parser.add_argument("--ml-outputs", type=Path, default=Path("ml_outputs"))
    parser.add_argument("--supabase-url", required=True)
    parser.add_argument("--service-key", required=True)
    args = parser.parse_args()

    transactions = pd.read_csv(args.data_dir / "transactions.csv")
    stock = pd.read_csv(args.data_dir / "stock.csv")
    products = pd.read_csv(args.data_dir / "products.csv")
    snapshot = build_storefront_snapshot(transactions, stock, products)

    predictions_path = latest_output(args.ml_outputs, "predictions")
    transfers_path = latest_output(args.ml_outputs, "transfers")
    predictions = pd.read_csv(predictions_path) if predictions_path else None
    transfers = pd.read_csv(transfers_path) if transfers_path else None

    client = create_client(args.supabase_url, args.service_key)
    counts = push_storefront_snapshot(client, snapshot, predictions, transfers)
    for table, count in sorted(counts.items()):
        print(f"{table}: {count}")


if __name__ == "__main__":
    main()
