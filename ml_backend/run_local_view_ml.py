import argparse
import json
import os
import sys
from typing import Dict, List

import pandas as pd


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INVENTORY = "/Users/muhammadabdulmohsin/Downloads/v_inventory_snapshot.json"
DEFAULT_PRODUCTS = "/Users/muhammadabdulmohsin/Downloads/v_store_products.json"
DEFAULT_TRANSACTIONS = "/Users/muhammadabdulmohsin/Downloads/v_store_transactions.json"
DEFAULT_OUTPUT = os.path.join(BASE_DIR, "local_view_ml_output.json")


def load_json_frame(path: str) -> pd.DataFrame:
    with open(path) as f:
        data = json.load(f)
    return pd.DataFrame(data)


def normalize_products(products: pd.DataFrame) -> pd.DataFrame:
    products = products.copy()
    products["store_id"]   = products["store_id"].astype(str)
    products["product_id"] = products["product_id"].astype(str)
    products["category"] = (
        products["category"].fillna("unknown").astype(str).str.strip().str.lower()
    )
    products["product_name"] = products["product_name"].fillna("").astype(str)
    products["retail_price"] = pd.to_numeric(
        products["retail_price"], errors="coerce"
    ).fillna(0.0)
    products["wholesale_price"] = pd.to_numeric(
        products.get("wholesale_price", 0), errors="coerce"
    ).fillna(0.0)
    products["unit_quantity"] = pd.to_numeric(
        products.get("unit_quantity", 0), errors="coerce"
    ).fillna(0.0)
    products = (
        products.sort_values(["store_id", "product_id"])
        .drop_duplicates(subset=["store_id", "product_id"], keep="last")
        .reset_index(drop=True)
    )
    return products


def normalize_inventory(inventory: pd.DataFrame) -> pd.DataFrame:
    inventory = inventory.copy()
    inventory["store_id"]   = inventory["store_id"].astype(str)
    inventory["product_id"] = inventory["product_id"].astype(str)
    inventory["stock_qty"] = pd.to_numeric(inventory["stock_qty"], errors="coerce").fillna(0.0)
    inventory["updated_at"] = pd.to_datetime(inventory["updated_at"], utc=True, errors="coerce")
    inventory = inventory.sort_values(["store_id", "product_id", "updated_at"])
    inventory = inventory.drop_duplicates(subset=["store_id", "product_id"], keep="last")
    return inventory.reset_index(drop=True)


def aggregate_transactions(transactions: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    transactions = transactions.copy()
    transactions["store_id"]       = transactions["store_id"].astype(str)
    transactions["product_id"]     = transactions["product_id"].astype(str)
    transactions["quantity"] = pd.to_numeric(transactions["quantity"], errors="coerce").fillna(0.0)
    transactions["timestamp"] = pd.to_datetime(transactions["timestamp"], utc=True, errors="coerce")
    transactions["transaction_id"] = transactions["transaction_id"].astype(str)

    if transactions["timestamp"].notna().any():
        max_ts = transactions["timestamp"].max()
    else:
        max_ts = pd.Timestamp.utcnow(tz="UTC")

    recent_cutoff = max_ts - pd.Timedelta(days=30)
    recent_sales = transactions[transactions["timestamp"] >= recent_cutoff].copy()
    historical_sales = transactions[transactions["timestamp"] < recent_cutoff].copy()

    recent = (
        recent_sales.groupby(["store_id", "product_id"])
        .agg(
            recent_qty=("quantity", "sum"),
            recent_txns=("transaction_id", "nunique"),
            recent_avg=("quantity", "mean"),
            recent_std=("quantity", "std"),
        )
        .reset_index()
    )

    historical = (
        historical_sales.groupby(["store_id", "product_id"])
        .agg(
            historical_qty=("quantity", "sum"),
            historical_txns=("transaction_id", "nunique"),
            historical_avg=("quantity", "mean"),
        )
        .reset_index()
    )

    totals = (
        transactions.groupby(["store_id", "product_id"])
        .agg(
            total_sold=("quantity", "sum"),
            num_sales=("transaction_id", "nunique"),
            last_sale_ts=("timestamp", "max"),
        )
        .reset_index()
    )
    totals["days_since_last_sale"] = (
        (max_ts - totals["last_sale_ts"]).dt.total_seconds() / 86400.0
    ).fillna(0.0)
    totals = totals.drop(columns=["last_sale_ts"])

    store_txns = (
        transactions.groupby("store_id")
        .agg(store_total_txns=("transaction_id", "nunique"))
        .reset_index()
    )

    return {
        "transactions": transactions,
        "recent": recent,
        "historical": historical,
        "totals": totals,
        "store_txns": store_txns,
        "max_ts": max_ts,
    }


def build_model_input(
    inventory: pd.DataFrame,
    products: pd.DataFrame,
    txn_aggs: Dict[str, pd.DataFrame],
) -> pd.DataFrame:
    model_input = inventory.merge(
        products,
        on=["store_id", "product_id"],
        how="inner",
        validate="one_to_one",
    )
    model_input = model_input.merge(
        txn_aggs["recent"], on=["store_id", "product_id"], how="left"
    )
    model_input = model_input.merge(
        txn_aggs["historical"], on=["store_id", "product_id"], how="left"
    )
    model_input = model_input.merge(
        txn_aggs["totals"], on=["store_id", "product_id"], how="left"
    )
    model_input = model_input.merge(
        txn_aggs["store_txns"], on="store_id", how="left"
    )

    numeric_cols = [
        "recent_qty",
        "recent_txns",
        "recent_avg",
        "recent_std",
        "historical_qty",
        "historical_txns",
        "historical_avg",
        "total_sold",
        "num_sales",
        "days_since_last_sale",
        "store_total_txns",
        "stock_qty",
        "retail_price",
    ]
    for col in numeric_cols:
        model_input[col] = pd.to_numeric(model_input[col], errors="coerce").fillna(0.0)

    model_input["recent_std"] = model_input["recent_std"].fillna(0.0)
    model_input["category"] = model_input["category"].fillna("unknown").astype(str).str.lower()
    model_input["product_name"] = model_input["product_name"].fillna("").astype(str)

    # Cast join keys to str so they match ProductInput / pydantic schemas
    model_input["store_id"]   = model_input["store_id"].astype(str)
    model_input["product_id"] = model_input["product_id"].astype(str)

    # Canonical product key: normalized name used to group the same product
    # across stores for transfer recommendations (POS product_ids are store-scoped)
    model_input["canonical_product_id"] = (
        model_input["product_name"].str.strip().str.lower()
    )

    cols = [
        "store_id",
        "product_id",
        "canonical_product_id",
        "product_name",
        "category",
        "stock_qty",
        "retail_price",
        "recent_qty",
        "recent_txns",
        "recent_avg",
        "recent_std",
        "historical_qty",
        "historical_txns",
        "historical_avg",
        "total_sold",
        "num_sales",
        "days_since_last_sale",
        "store_total_txns",
    ]
    return model_input[cols].sort_values(["store_id", "product_id"]).reset_index(drop=True)


def run_inference(model_input: pd.DataFrame) -> Dict[str, List[dict]]:
    sys.path.insert(0, BASE_DIR)
    import app as ml_app

    # Build ProductInput objects using the original (store-scoped) product_id
    # so forecast lookups and prediction output are accurate.
    rows = model_input.drop(columns=["canonical_product_id"]).to_dict(orient="records")
    products = [ml_app.ProductInput(**row) for row in rows]
    predictions = ml_app._run_predictions(products)

    # For the transfer engine, replace product_id with canonical_product_id so
    # the same physical product across stores (which have different POS-assigned
    # IDs) is grouped together and transfers are computed correctly.
    canonical_map = model_input.set_index("product_id")["canonical_product_id"].to_dict()

    products_for_transfer = []
    for p in products:
        data = p.model_dump()
        data["product_id"] = canonical_map.get(p.product_id, p.product_id)
        products_for_transfer.append(ml_app.ProductInput(**data))

    predictions_for_transfer = []
    for pred in predictions:
        data = pred.model_dump()
        data["product_id"] = canonical_map.get(pred.product_id, pred.product_id)
        predictions_for_transfer.append(ml_app.ProductPrediction(**data))

    transfers, restocks = ml_app._compute_recommendations(
        products_for_transfer, predictions_for_transfer
    )

    return {
        "predictions": [p.model_dump() for p in predictions],
        "transfers": [t.model_dump() for t in transfers],
        "restocks": [r.model_dump() for r in restocks],
    }


def build_metadata(
    inventory: pd.DataFrame,
    products: pd.DataFrame,
    transactions: pd.DataFrame,
    model_input: pd.DataFrame,
    txn_aggs: Dict[str, pd.DataFrame],
) -> dict:
    sys.path.insert(0, BASE_DIR)
    import app as ml_app

    allowed_categories = set(ml_app.CATEGORY_CLASSES)
    category_counts = products["category"].value_counts().to_dict()
    unknown_categories = {
        cat: int(count)
        for cat, count in category_counts.items()
        if cat not in allowed_categories
    }

    return {
        "source_files": {
            "inventory": DEFAULT_INVENTORY,
            "products": DEFAULT_PRODUCTS,
            "transactions": DEFAULT_TRANSACTIONS,
        },
        "row_counts": {
            "inventory_rows": int(len(inventory)),
            "product_rows": int(len(products)),
            "transaction_rows": int(len(transactions)),
            "model_input_rows": int(len(model_input)),
        },
        "unique_counts": {
            "inventory_pairs": int(inventory[["store_id", "product_id"]].drop_duplicates().shape[0]),
            "product_pairs": int(products[["store_id", "product_id"]].drop_duplicates().shape[0]),
            "transaction_pairs": int(transactions[["store_id", "product_id"]].drop_duplicates().shape[0]),
            "stores_in_output": int(model_input["store_id"].nunique()),
            "products_in_output": int(model_input["product_id"].nunique()),
        },
        "mapping_checks": {
            "inventory_without_product": int(
                inventory.merge(
                    products[["store_id", "product_id"]],
                    on=["store_id", "product_id"],
                    how="left",
                    indicator=True,
                ).query('_merge == "left_only"').shape[0]
            ),
            "product_without_inventory": int(
                products.merge(
                    inventory[["store_id", "product_id"]],
                    on=["store_id", "product_id"],
                    how="left",
                    indicator=True,
                ).query('_merge == "left_only"').shape[0]
            ),
            "transaction_pairs_without_product": int(
                transactions[["store_id", "product_id"]]
                .drop_duplicates()
                .merge(
                    products[["store_id", "product_id"]].drop_duplicates(),
                    on=["store_id", "product_id"],
                    how="left",
                    indicator=True,
                )
                .query('_merge == "left_only"')
                .shape[0]
            ),
        },
        "transaction_window": {
            "min_timestamp": transactions["timestamp"].min().isoformat() if transactions["timestamp"].notna().any() else None,
            "max_timestamp": txn_aggs["max_ts"].isoformat() if pd.notna(txn_aggs["max_ts"]) else None,
        },
        "model_category_coverage": {
            "known_categories": sorted(allowed_categories),
            "unknown_categories_in_products": unknown_categories,
        },
    }


def push_to_supabase(predictions: List[dict], transfers: List[dict], model_input: pd.DataFrame = None) -> None:
    """Publish through the same atomic storefront bridge used by batch jobs."""
    from supabase_watcher import SUPABASE_URL, SUPABASE_KEY
    from supabase import create_client
    from publish_results import publish_results
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print(publish_results(client, {"predictions": predictions, "transfers": transfers}))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Jiran ML model from Supabase JSON view exports.")
    parser.add_argument("--inventory", default=DEFAULT_INVENTORY)
    parser.add_argument("--products", default=DEFAULT_PRODUCTS)
    parser.add_argument("--transactions", default=DEFAULT_TRANSACTIONS)
    parser.add_argument("--push", action="store_true",
                        help="Push predictions and transfers to Supabase after running")
    args = parser.parse_args()

    out_dir = os.path.dirname(os.path.abspath(DEFAULT_OUTPUT))
    predictions_path = os.path.join(out_dir, "ml_predictions.json")
    transfers_path   = os.path.join(out_dir, "ml_transfers.json")
    restocks_path    = os.path.join(out_dir, "ml_restocks.json")

    inventory = normalize_inventory(load_json_frame(args.inventory))
    products = normalize_products(load_json_frame(args.products))
    txn_aggs = aggregate_transactions(load_json_frame(args.transactions))
    transactions = txn_aggs["transactions"]

    model_input = build_model_input(inventory, products, txn_aggs)
    inference = run_inference(model_input)
    metadata = build_metadata(inventory, products, transactions, model_input, txn_aggs)

    summary = {
        "prediction_count": len(inference["predictions"]),
        "transfer_count":   len(inference["transfers"]),
        "restock_count":    len(inference["restocks"]),
    }

    with open(predictions_path, "w") as f:
        json.dump({"metadata": metadata, "summary": summary,
                   "predictions": inference["predictions"]}, f, indent=2, default=str)

    with open(transfers_path, "w") as f:
        json.dump({"metadata": metadata, "summary": summary,
                   "transfers": inference["transfers"]}, f, indent=2, default=str)

    with open(restocks_path, "w") as f:
        json.dump({"metadata": metadata, "summary": summary,
                   "restocks": inference["restocks"]}, f, indent=2, default=str)

    print(f"Wrote {predictions_path}")
    print(f"Wrote {transfers_path}")
    print(f"Wrote {restocks_path}")
    print(json.dumps(summary, indent=2))

    if args.push:
        print("\nPushing to Supabase...")
        push_to_supabase(inference["predictions"], inference["transfers"], model_input)


if __name__ == "__main__":
    main()
