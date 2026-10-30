from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request

from audit_erp import FrappeClient, normalize
from match_products import read_rows, similarity

COMPANY = "Salsamentaria Multiespecial"
WAREHOUSE = "Principal - SM"
STOCK_ENTRY_TYPE = "Inventario Inicial"
POSTING_DATE = "2026-09-27"


def request_json(client: FrappeClient, method: str, path: str, payload: dict[str, object]) -> dict[str, object]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    response = client.opener.open(
        Request(
            f"{client.base_url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        ),
        timeout=60,
    )
    return json.loads(response.read().decode("utf-8"))


def choose_item(row: dict[str, object], items: list[dict[str, object]]) -> tuple[dict[str, object], str, float]:
    name = str(row.get("Nombre del Producto") or "")
    excel_uom = row.get("UOM")
    normalized_name = normalize(name)
    exact = [item for item in items if normalize(item.get("item_name")) == normalized_name]
    if exact:
        same_uom = [item for item in exact if normalize(item.get("stock_uom")) == normalize(excel_uom)]
        pool = same_uom or exact
        chosen = sorted(pool, key=lambda item: str(item.get("item_code") or item.get("name")))[0]
        return chosen, "exact_name_uom" if same_uom else "exact_name", 1.0

    scored = []
    for item in items:
        score = similarity(name, str(item.get("item_name") or ""), excel_uom, item.get("stock_uom"))
        scored.append((score, str(item.get("item_code") or item.get("name")), item))
    scored.sort(key=lambda value: (-value[0], value[1]))
    if not scored:
        raise RuntimeError(f"No hay productos activos inventariables para buscar: {name}")
    score, _, chosen = scored[0]
    return chosen, "fuzzy_top_candidate", score


def build_document(rows: list[dict[str, object]], items: list[dict[str, object]]) -> tuple[dict[str, object], list[dict[str, object]]]:
    selected: list[dict[str, object]] = []
    for row_number, row in enumerate(rows, start=2):
        item, match_type, score = choose_item(row, items)
        qty = float(row.get("Cant. Entrada") or 0)
        if qty <= 0:
            raise RuntimeError(f"Cantidad no positiva en fila {row_number}: {qty}")
        selected.append({
            "row": row_number,
            "excel_name": row.get("Nombre del Producto"),
            "invoice_code": row.get("codigo de factura"),
            "qty": qty,
            "item_code": item.get("item_code") or item.get("name"),
            "item_name": item.get("item_name"),
            "stock_uom": item.get("stock_uom"),
            "match_type": match_type,
            "score": round(score, 3),
        })

    by_code: dict[str, dict[str, object]] = {}
    for match in selected:
        code = str(match["item_code"])
        line = by_code.setdefault(code, {
            "item_code": code,
            "item_name": match["item_name"],
            "uom": match["stock_uom"],
            "stock_uom": match["stock_uom"],
            "qty": 0.0,
            "transfer_qty": 0.0,
            "t_warehouse": WAREHOUSE,
            "allow_zero_valuation_rate": 1,
            "basic_rate": 0,
        })
        line["qty"] += match["qty"]
        line["transfer_qty"] += match["qty"]

    document = {
        "doctype": "Stock Entry",
        "stock_entry_type": STOCK_ENTRY_TYPE,
        "company": COMPANY,
        "posting_date": POSTING_DATE,
        "items": list(by_code.values()),
        "remarks": "Importación inventario 27-09-2026. Sin proveedor ni número de pieza del proveedor.",
    }
    return document, selected


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print("Uso: python create_inventory_entry.py <inventario.xlsx> [--submit]", file=sys.stderr)
        return 2
    path = Path(sys.argv[1]).resolve()
    should_submit = len(sys.argv) == 3 and sys.argv[2] == "--submit"
    user = os.environ.get("ERP_USER")
    password = os.environ.get("ERP_PASSWORD")
    if not user or not password:
        raise RuntimeError("Defina ERP_USER y ERP_PASSWORD en el entorno")

    rows = read_rows(path)
    client = FrappeClient(os.environ.get("ERP_URL", "https://salsamentariamultiespecial.duckdns.org"), user, password)
    all_items = client.get_list("Item", ["name", "item_code", "item_name", "stock_uom", "disabled", "is_stock_item"], [], 10000)
    active_stock_items = [item for item in all_items if not item.get("disabled") and item.get("is_stock_item")]
    document, selected = build_document(rows, active_stock_items)
    fuzzy = [match for match in selected if match["match_type"] == "fuzzy_top_candidate"]
    exact_no_uom = [match for match in selected if match["match_type"] == "exact_name"]
    duplicate_codes = {code: count for code, count in Counter(match["item_code"] for match in selected).items() if count > 1}

    preview = {
        "source": str(path),
        "source_rows": len(rows),
        "active_stock_items_consulted": len(active_stock_items),
        "selected_rows": len(selected),
        "stock_entry_lines_after_merging": len(document["items"]),
        "fuzzy_rows": len(fuzzy),
        "exact_matches_without_uom_match": len(exact_no_uom),
        "merged_item_codes": duplicate_codes,
        "posting_date": POSTING_DATE,
        "stock_entry_type": STOCK_ENTRY_TYPE,
        "company": COMPANY,
        "warehouse": WAREHOUSE,
        "zero_valuation_allowed": True,
        "fuzzy_selection": fuzzy,
    }
    if len(rows) != 231 or len(selected) != len(rows):
        raise RuntimeError(f"Control de filas falló: Excel={len(rows)}, seleccionadas={len(selected)}")

    if not should_submit:
        print(json.dumps(preview, ensure_ascii=False, indent=2, default=str))
        return 0

    created = request_json(client, "POST", "/api/resource/Stock%20Entry", {"data": document})
    created_doc = created.get("data") or {}
    name = created_doc.get("name")
    if not name:
        raise RuntimeError(f"ERPNext no devolvió el nombre de la entrada creada: {created}")
    submitted = request_json(client, "POST", "/api/method/frappe.client.submit", {"doc": created_doc})
    submitted_doc = submitted.get("message") or submitted.get("data") or {}
    print(json.dumps({
        "status": "submitted",
        "name": name,
        "docstatus": submitted_doc.get("docstatus") if isinstance(submitted_doc, dict) else None,
        "selected_rows": len(selected),
        "stock_entry_lines": len(document["items"]),
        "fuzzy_rows": len(fuzzy),
        "posting_date": POSTING_DATE,
        "stock_entry_type": STOCK_ENTRY_TYPE,
        "warehouse": WAREHOUSE,
    }, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (HTTPError, URLError) as exc:
        print(f"ERROR HTTP: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
