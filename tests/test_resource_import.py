from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from tools.resource_import import normalize


class ResourceImportTests(unittest.TestCase):
    def test_erpnext_export_maps_to_jiran_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "erpnext.csv"
            output = Path(tmp) / "jiran.csv"
            source.write_text(
                "item_code,item_name,item_group,actual_qty,valuation_rate,warehouse\n"
                "SKU-1,Reusable Crate,Logistics,12,31.50,Dubai Hub\n",
                encoding="utf-8",
            )
            self.assertEqual(normalize("erpnext", source, output), 1)
            with output.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["sku"], "SKU-1")
            self.assertEqual(rows[0]["quantity"], "12")
            self.assertEqual(rows[0]["location"], "Dubai Hub")
            self.assertEqual(rows[0]["currency"], "AED")

    def test_invalid_rows_are_skipped_and_no_ai_fields_are_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "odoo.csv"
            output = Path(tmp) / "jiran.csv"
            source.write_text("default_code,name,qty_available\n,Missing SKU,7\n", encoding="utf-8")
            self.assertEqual(normalize("odoo", source, output), 0)
            self.assertNotIn("prediction", output.read_text())


if __name__ == "__main__":
    unittest.main()
