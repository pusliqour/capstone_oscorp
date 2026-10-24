#!/usr/bin/env python3
"""Normalize open-source ERP inventory exports into Jiran's import contract.

No AI predictions are generated. This adapter only maps inventory facts supplied by
the operator so the existing Jiran CSV import path can replace Square as a source.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

SCHEMAS = {
    "erpnext": {
        "sku": ("item_code",),
        "name": ("item_name", "item_code"),
        "category": ("item_group",),
        "quantity": ("actual_qty", "qty"),
        "price": ("valuation_rate", "standard_rate"),
        "location": ("warehouse",),
    },
    "odoo": {
        "sku": ("default_code", "id"),
        "name": ("name",),
        "category": ("categ_id/name", "categ_id", "category"),
        "quantity": ("qty_available", "quantity"),
        "price": ("list_price", "standard_price"),
        "location": ("warehouse_id/name", "warehouse", "location"),
    },
    "jiran": {
        "sku": ("sku",), "name": ("name",), "category": ("category",),
        "quantity": ("quantity",), "price": ("price",), "location": ("location",),
    },
}
OUTPUT_FIELDS = ["sku", "name", "category", "quantity", "price", "currency", "location"]


def first(row: dict[str, str], candidates: tuple[str, ...], default: str = "") -> str:
    for key in candidates:
        value = (row.get(key) or "").strip()
        if value:
            return value
    return default


def normalize(source: str, input_path: Path, output_path: Path, currency: str = "AED") -> int:
    mapping = SCHEMAS[source]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with input_path.open(newline="", encoding="utf-8-sig") as src, output_path.open("w", newline="", encoding="utf-8") as dst:
        reader = csv.DictReader(src)
        writer = csv.DictWriter(dst, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for row in reader:
            normalized = {field: first(row, mapping[field]) for field in mapping}
            if not normalized["sku"] or not normalized["name"]:
                continue
            normalized["quantity"] = normalized["quantity"] or "0"
            normalized["price"] = normalized["price"] or "0"
            normalized["currency"] = currency
            writer.writerow(normalized)
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=sorted(SCHEMAS), required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--currency", default="AED")
    args = parser.parse_args()
    count = normalize(args.source, args.input, args.output, args.currency)
    print(f"Normalized {count} inventory rows to {args.output}")


if __name__ == "__main__":
    main()
