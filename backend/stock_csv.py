"""Writing staff edits of stock and rate back into catalogue/stock.csv.

stock.csv stays the source of truth: ingest reloads from it, so a DB-only edit
would be undone on the next ingest.
"""

import csv
import os
import threading

from backend.config import STOCK_CSV

_lock = threading.Lock()


def _format_number(value):
    return str(int(value)) if float(value).is_integer() else str(value)


def update_row(design_id, quantity, rate):
    """Set quantity_available and rate for one design."""
    with _lock:
        with open(STOCK_CSV, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)
        found = False
        for row in rows:
            if (row.get("design_id") or "").strip() == design_id:
                row["quantity_available"] = str(int(quantity))
                row["rate"] = _format_number(rate)
                found = True
        if not found:
            raise KeyError(design_id)
        tmp = STOCK_CSV.with_suffix(".csv.tmp")
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp, STOCK_CSV)
