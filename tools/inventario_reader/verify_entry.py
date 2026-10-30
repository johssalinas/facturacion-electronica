from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from audit_erp import FrappeClient
from match_products import read_rows


def main() -> int:
    if len(sys.argv) != 3:
        print("Uso: python verify_entry.py <inventario.xlsx> <stock-entry-name>", file=sys.stderr)
        return 2
    user = os.environ.get("ERP_USER")
    password = os.environ.get("ERP_PASSWORD")
    if not user or not password:
        raise RuntimeError("Defina ERP_USER y ERP_PASSWORD en el entorno")
    rows = read_rows(Path(sys.argv[1]).resolve())
    client = FrappeClient(os.environ.get("ERP_URL", "https://salsamentariamultiespecial.duckdns.org"), user, password)
    doc = client.get_doc("Stock Entry", sys.argv[2])
    items = doc.get("items") or []
    expected_qty = sum(float(row.get("Cant. Entrada") or 0) for row in rows)
    actual_qty = sum(float(item.get("qty") or 0) for item in items)
    warehouses = sorted({item.get("t_warehouse") for item in items})
    result = {
        "name": doc.get("name"),
        "docstatus": doc.get("docstatus"),
        "posting_date": doc.get("posting_date"),
        "stock_entry_type": doc.get("stock_entry_type"),
        "company": doc.get("company"),
        "source_rows": len(rows),
        "document_lines": len(items),
        "expected_quantity_total": expected_qty,
        "document_quantity_total": actual_qty,
        "quantity_totals_match": abs(expected_qty - actual_qty) < 0.000001,
        "warehouses": warehouses,
        "all_lines_without_supplier": all(not item.get("supplier") for item in items),
        "all_lines_allow_zero_valuation": all(item.get("allow_zero_valuation_rate") for item in items),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    if result["docstatus"] != 1 or not result["quantity_totals_match"]:
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
