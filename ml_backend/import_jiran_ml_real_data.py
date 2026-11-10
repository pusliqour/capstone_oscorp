"""Import Jiran Square exports into the live ML service contract.

The source files live in the private ``M4MD-M7SN/jiran-ml`` repository. This
module converts the three store catalogs and order exports into:

* ``transactions.csv``, ``stock.csv``, and ``products.csv`` for ``train.py``;
* ``ml_inventory.csv`` for the Supabase watcher used by the running API.

No credentials are read unless ``--push`` is requested. When pushing, set
``SUPABASE_URL`` and one of ``SUPABASE_SERVICE_KEY``/``SUPABASE_KEY``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

CAT_MAP = {
    "beverage": "beverages",
    "beverages": "beverages",
    "frozen": "frozen",
    "produce": "produce",
    "household": "household",
    "pantry": "pantry",
    "personal care": "personal_care",
    "personal_care": "personal_care",
    "snacks": "snacks",
    "bakery": "bakery",
    "dairy": "dairy",
    "meat": "meat",
    "electronics": "electronics",
}

INVENTORY_COLUMNS = [
    "store_id",
    "product_id",
    "store_name",
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
    "updated_at",
]


def normalize_store_id(value: object) -> str:
    """Return a deterministic store ID shared by catalog and order exports."""
    cleaned = re.sub(r"[^A-Z0-9]+", "_", str(value).strip().upper()).strip("_")
    if not cleaned:
        raise ValueError("Store location cannot be blank")
    return f"STORE_{cleaned}"


def normalize_category(value: object) -> str:
    if pd.isna(value):
        return "general"
    cleaned = str(value).strip().lower()
    return CAT_MAP.get(cleaned, cleaned.replace(" ", "_") or "general")


def _require_columns(frame: pd.DataFrame, required: Iterable[str], source: str) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"{source} is missing required columns: {missing}")


def _validated_numeric(
    frame: pd.DataFrame,
    column: str,
    source: str,
    *,
    minimum: float,
    inclusive: bool = True,
) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="raise")
    finite = np.isfinite(values)
    in_range = values >= minimum if inclusive else values > minimum
    if not bool((finite & in_range).all()):
        qualifier = "at least" if inclusive else "greater than"
        raise ValueError(
            f"{source} column {column!r} must contain finite values {qualifier} {minimum}"
        )
    return values


def transform_exports(
    catalog_frames: list[pd.DataFrame], order_frames: list[pd.DataFrame]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Convert loaded Square frames to the training CSV contract."""
    if not catalog_frames or not order_frames:
        raise ValueError("At least one catalog and one order export are required")

    catalog_records: list[pd.DataFrame] = []
    for index, raw in enumerate(catalog_frames, start=1):
        source = f"catalog #{index}"
        _require_columns(raw, ["Product", "SKU", "Categories", "Price", "Location"], source)
        quantity_columns = [
            column for column in raw.columns if str(column).startswith("Current Quantity ")
        ]
        if len(quantity_columns) != 1:
            raise ValueError(
                f"{source} must contain exactly one 'Current Quantity …' column; "
                f"found {quantity_columns}"
            )
        quantity_column = quantity_columns[0]
        frame = raw[["Product", "SKU", "Categories", "Price", "Location", quantity_column]].copy()
        frame = frame.rename(
            columns={
                "Product": "product_name",
                "SKU": "raw_product_id",
                "Categories": "category",
                "Price": "retail_price",
                "Location": "store_name",
                quantity_column: "stock_qty",
            }
        )
        frame = frame.dropna(
            subset=["raw_product_id", "product_name", "store_name", "retail_price", "stock_qty"]
        )
        if frame.empty:
            raise ValueError(f"{source} has no usable catalog rows")
        frame["raw_product_id"] = frame["raw_product_id"].astype(str).str.strip()
        frame["product_name"] = frame["product_name"].astype(str).str.strip()
        frame["store_name"] = frame["store_name"].astype(str).str.strip()
        frame["store_id"] = frame["store_name"].map(normalize_store_id)
        frame["category"] = frame["category"].map(normalize_category)
        frame["retail_price"] = _validated_numeric(
            frame, "retail_price", source, minimum=0
        )
        frame["stock_qty"] = _validated_numeric(
            frame, "stock_qty", source, minimum=0
        )
        catalog_records.append(frame)

    catalog = pd.concat(catalog_records, ignore_index=True)
    # Some Square store-exclusive SKUs are reused by another store for a
    # completely different item. Preserve genuinely shared SKUs, but namespace
    # conflicting ones so their metadata, forecasts, and recommendations never
    # bleed across stores.
    metadata_columns = ["product_name", "category", "retail_price"]
    conflicting_skus = {
        str(raw_product_id)
        for raw_product_id, group in catalog.groupby("raw_product_id")
        if len(group[metadata_columns].drop_duplicates()) > 1
    }
    catalog["product_id"] = catalog.apply(
        lambda row: (
            f"{row['store_id']}::{row['raw_product_id']}"
            if row["raw_product_id"] in conflicting_skus
            else row["raw_product_id"]
        ),
        axis=1,
    )
    duplicate_stock = catalog.duplicated(["store_id", "product_id"], keep=False)
    if duplicate_stock.any():
        duplicates = catalog.loc[duplicate_stock, ["store_id", "product_id"]].drop_duplicates()
        raise ValueError(f"Duplicate catalog store/SKU rows: {duplicates.to_dict('records')[:5]}")

    products = (
        catalog[["product_id", "product_name", "category", "retail_price"]]
        .drop_duplicates("product_id", keep="first")
        .sort_values("product_id")
        .reset_index(drop=True)
    )

    order_records: list[pd.DataFrame] = []
    for index, raw in enumerate(order_frames, start=1):
        source = f"orders #{index}"
        required = [
            "external_order_id",
            "order_time",
            "external_location_id",
            "sku",
            "quantity",
        ]
        _require_columns(raw, required, source)
        frame = raw.copy()
        if "status" in frame.columns:
            frame = frame[frame["status"].astype(str).str.lower() == "completed"]
        frame = frame[required].dropna(subset=["external_order_id", "sku", "external_location_id"])
        if frame.empty:
            raise ValueError(f"{source} has no completed usable order rows")
        frame = frame.rename(
            columns={
                "external_order_id": "transaction_id",
                "order_time": "timestamp",
                "external_location_id": "store_name",
                "sku": "raw_product_id",
            }
        )
        frame["transaction_id"] = frame["transaction_id"].astype(str).str.strip()
        frame["raw_product_id"] = frame["raw_product_id"].astype(str).str.strip()
        frame["store_name"] = frame["store_name"].astype(str).str.strip()
        frame["store_id"] = frame["store_name"].map(normalize_store_id)
        frame["quantity"] = _validated_numeric(
            frame, "quantity", source, minimum=0, inclusive=False
        )
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
        order_records.append(frame)

    orders = pd.concat(order_records, ignore_index=True)
    product_ids_by_store_sku = {
        (row.store_id, row.raw_product_id): row.product_id
        for row in catalog[["store_id", "raw_product_id", "product_id"]].itertuples(
            index=False
        )
    }
    order_store_skus = list(zip(orders["store_id"], orders["raw_product_id"]))
    missing_stock = sorted(set(order_store_skus) - set(product_ids_by_store_sku))
    if missing_stock:
        raise ValueError(f"Order store/SKU pairs missing from catalogs: {missing_stock[:20]}")
    orders["product_id"] = [product_ids_by_store_sku[pair] for pair in order_store_skus]

    transactions = (
        orders[["transaction_id", "store_id", "product_id", "quantity", "timestamp"]]
        .sort_values(["timestamp", "transaction_id", "product_id"])
        .reset_index(drop=True)
    )
    # The catalogs do not carry an export timestamp. Record when this snapshot
    # was loaded rather than presenting the latest order time as stock freshness.
    updated_at = pd.Timestamp.now(tz="UTC")
    stock = catalog[["store_id", "product_id", "stock_qty"]].copy()
    stock["updated_at"] = updated_at
    stock = stock.sort_values(["store_id", "product_id"]).reset_index(drop=True)
    return transactions, stock, products


def _sales_aggregation(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
    columns = [
        "store_id",
        "product_id",
        f"{prefix}_qty",
        f"{prefix}_txns",
        f"{prefix}_avg",
    ]
    if frame.empty:
        if prefix == "recent":
            columns.append("recent_std")
        return pd.DataFrame(columns=columns)
    grouped = frame.groupby(["store_id", "product_id"])["quantity"]
    result = grouped.agg([("qty", "sum"), ("txns", "count"), ("avg", "mean")]).reset_index()
    result = result.rename(
        columns={
            "qty": f"{prefix}_qty",
            "txns": f"{prefix}_txns",
            "avg": f"{prefix}_avg",
        }
    )
    if prefix == "recent":
        std = grouped.std().fillna(0).rename("recent_std").reset_index()
        result = result.merge(std, on=["store_id", "product_id"], how="left")
    return result


def build_ml_inventory(
    transactions: pd.DataFrame, stock: pd.DataFrame, products: pd.DataFrame
) -> pd.DataFrame:
    """Aggregate the training frames into the live watcher input table."""
    if transactions.empty:
        raise ValueError("Cannot build ML inventory without completed transactions")
    sales = transactions.copy()
    sales["timestamp"] = pd.to_datetime(sales["timestamp"], utc=True, errors="raise")
    as_of = sales["timestamp"].max()
    cutoff = as_of - pd.Timedelta(days=30)

    recent = _sales_aggregation(sales[sales["timestamp"] >= cutoff], "recent")
    historical = _sales_aggregation(sales[sales["timestamp"] < cutoff], "historical")
    total = (
        sales.groupby(["store_id", "product_id"])
        .agg(
            total_sold=("quantity", "sum"),
            num_sales=("quantity", "count"),
            last_sale_ts=("timestamp", "max"),
        )
        .reset_index()
    )
    store_txns = (
        sales.groupby("store_id")["transaction_id"]
        .nunique()
        .rename("store_total_txns")
        .reset_index()
    )
    store_names = (
        sales[["store_id"]]
        .drop_duplicates()
        .assign(store_name=lambda df: df["store_id"].str.removeprefix("STORE_").str.replace("_", " ").str.title())
    )

    inventory = stock.merge(products, on="product_id", how="left", validate="many_to_one")
    inventory = inventory.merge(store_names, on="store_id", how="left", validate="many_to_one")
    inventory = inventory.merge(recent, on=["store_id", "product_id"], how="left")
    inventory = inventory.merge(historical, on=["store_id", "product_id"], how="left")
    inventory = inventory.merge(total, on=["store_id", "product_id"], how="left")
    inventory = inventory.merge(store_txns, on="store_id", how="left")

    inventory["last_sale_ts"] = pd.to_datetime(inventory["last_sale_ts"], utc=True, errors="coerce")
    inventory["days_since_last_sale"] = (
        (as_of - inventory["last_sale_ts"]).dt.total_seconds() / 86400
    ).clip(lower=0).fillna(999).round(2)
    numeric = [
        "recent_qty",
        "recent_txns",
        "recent_avg",
        "recent_std",
        "historical_qty",
        "historical_txns",
        "historical_avg",
        "total_sold",
        "num_sales",
        "store_total_txns",
    ]
    inventory[numeric] = inventory[numeric].fillna(0)
    inventory = inventory[INVENTORY_COLUMNS].sort_values(["store_id", "product_id"])
    return inventory.reset_index(drop=True)


def load_real_exports(source_dir: Path) -> tuple[list[pd.DataFrame], list[pd.DataFrame]]:
    catalog_paths = sorted(source_dir.glob("jiran_square_catalog_store_*.xlsx"))
    order_paths = sorted(source_dir.glob("orders_single_sheet_import_store_*.xlsx"))
    if len(catalog_paths) != 3 or len(order_paths) != 3:
        raise FileNotFoundError(
            f"Expected 3 catalog and 3 order exports in {source_dir}; "
            f"found {len(catalog_paths)} and {len(order_paths)}"
        )
    catalogs = [pd.read_excel(path, sheet_name="Square Catalog") for path in catalog_paths]
    orders = [pd.read_excel(path, sheet_name="orders_import") for path in order_paths]
    return catalogs, orders


def source_commit(source_dir: Path) -> str | None:
    try:
        output = subprocess.check_output(
            ["git", "-C", str(source_dir), "rev-parse", "HEAD"], text=True
        )
        return output.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def push_inventory(inventory: pd.DataFrame) -> None:
    from supabase import create_client

    url = os.getenv("SUPABASE_URL", "http://127.0.0.1:54321")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    if not key:
        raise RuntimeError("Set SUPABASE_SERVICE_KEY or SUPABASE_KEY before --push")
    client = create_client(url, key)
    records = json.loads(inventory.to_json(orient="records", date_format="iso"))
    response = client.rpc(
        "replace_ml_inventory", {"inventory_rows": records}
    ).execute()
    if int(response.data) != len(records):
        raise RuntimeError(
            f"Supabase replaced {response.data} rows; expected {len(records)}"
        )


def main() -> None:
    projects_dir = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / ".private/reference/original-ml-repository/data/real",
        help="Directory containing the six Square XLSX exports",
    )
    parser.add_argument(
        "--training-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "training" / "data",
    )
    parser.add_argument(
        "--inventory-csv",
        type=Path,
        default=Path(__file__).resolve().parent / "integration_data" / "ml_inventory.csv",
    )
    parser.add_argument("--push", action="store_true", help="Upsert ml_inventory to Supabase")
    args = parser.parse_args()

    catalogs, orders = load_real_exports(args.source_dir)
    transactions, stock, products = transform_exports(catalogs, orders)
    inventory = build_ml_inventory(transactions, stock, products)

    args.training_dir.mkdir(parents=True, exist_ok=True)
    args.inventory_csv.parent.mkdir(parents=True, exist_ok=True)
    transactions.to_csv(args.training_dir / "transactions.csv", index=False)
    stock.to_csv(args.training_dir / "stock.csv", index=False)
    products.to_csv(args.training_dir / "products.csv", index=False)
    inventory.to_csv(args.inventory_csv, index=False)

    commit = source_commit(args.source_dir)
    manifest = {
        "source_repository": "https://github.com/M4MD-M7SN/jiran-ml",
        "source_commit": commit,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_as_of": str(transactions["timestamp"].max()),
        "catalog_products": int(len(products)),
        "inventory_rows": int(len(inventory)),
        "transaction_lines": int(len(transactions)),
        "stores": sorted(transactions["store_id"].unique().tolist()),
    }
    manifest_path = args.inventory_csv.with_name("provenance.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    if args.push:
        push_inventory(inventory)

    print(json.dumps({**manifest, "pushed": args.push}, indent=2))


if __name__ == "__main__":
    main()
