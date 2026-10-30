from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener
import http.cookiejar

from openpyxl import load_workbook

BASE_URL = os.environ.get("ERP_URL", "https://salsamentariamultiespecial.duckdns.org").rstrip("/")
PAGE_SIZE = 500


def normalize(value: object) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()
    return re.sub(r"\s+", " ", text)


def read_rows(path: Path) -> list[dict[str, object]]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    worksheet = workbook.active
    rows = list(worksheet.iter_rows(values_only=True))
    workbook.close()
    headers = [str(value).strip() if value is not None else "" for value in rows[0]]
    return [dict(zip(headers, row)) for row in rows[1:] if any(value is not None for value in row)]


class FrappeClient:
    def __init__(self, base_url: str, user: str, password: str):
        self.base_url = base_url
        self.opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        payload = urlencode({"usr": user, "pwd": password}).encode()
        response = self.opener.open(
            Request(
                f"{base_url}/api/method/login",
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            ),
            timeout=30,
        )
        body = json.loads(response.read().decode("utf-8"))
        if body.get("message") != "Logged In":
            raise RuntimeError(f"El login no fue aceptado: {body.get('message')!r}")

    def get_list(self, doctype: str, fields: list[str], filters: list[list[object]] | None = None, limit: int = PAGE_SIZE) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        start = 0
        while True:
            remaining = limit - len(result)
            if remaining <= 0:
                return result[:limit]
            params = {
                "fields": json.dumps(fields, ensure_ascii=False),
                "limit_page_length": str(min(PAGE_SIZE, remaining)),
                "limit_start": str(start),
                "order_by": "name asc",
            }
            if filters:
                params["filters"] = json.dumps(filters, ensure_ascii=False)
            url = f"{self.base_url}/api/resource/{quote(doctype, safe='')}?{urlencode(params)}"
            response = self.opener.open(Request(url, headers={"Accept": "application/json"}), timeout=30)
            body = json.loads(response.read().decode("utf-8"))
            page = body.get("data", [])
            result.extend(page)
            if len(page) < int(params["limit_page_length"]):
                return result[:limit]
            start += len(page)

    def get_doc(self, doctype: str, name: str) -> dict[str, object]:
        url = f"{self.base_url}/api/resource/{quote(doctype, safe='')}/{quote(name, safe='')}"
        response = self.opener.open(Request(url, headers={"Accept": "application/json"}), timeout=30)
        return json.loads(response.read().decode("utf-8")).get("data", {})


def chunks(values: list[str], size: int = 100):
    for index in range(0, len(values), size):
        yield values[index:index + size]


def safe_list(client: FrappeClient, doctype: str, fields: list[str], filters: list[list[object]], limit: int = PAGE_SIZE) -> dict[str, object]:
    try:
        return {"ok": True, "data": client.get_list(doctype, fields, filters, limit)}
    except (HTTPError, URLError, RuntimeError, TimeoutError) as exc:
        detail = str(exc)
        if isinstance(exc, HTTPError):
            try:
                detail = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:500]}"
            except Exception:
                detail = f"HTTP {exc.code}"
        return {"ok": False, "error": detail, "data": []}


def safe_doc(client: FrappeClient, doctype: str, name: str) -> dict[str, object]:
    try:
        return {"ok": True, "data": client.get_doc(doctype, name)}
    except (HTTPError, URLError, RuntimeError, TimeoutError) as exc:
        detail = str(exc)
        if isinstance(exc, HTTPError):
            try:
                detail = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:500]}"
            except Exception:
                detail = f"HTTP {exc.code}"
        return {"ok": False, "error": detail, "data": {}}


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: uv run ... python audit_erp.py <inventario.xlsx>", file=sys.stderr)
        return 2
    excel_path = Path(sys.argv[1]).resolve()
    rows = read_rows(excel_path)
    name_key = "Nombre del Producto"
    code_key = "codigo de factura"
    qty_key = "Cant. Entrada"
    uom_key = "UOM"
    product_counts = Counter(normalize(row.get(name_key)) for row in rows)
    missing_code_rows = [row for row in rows if row.get(code_key) in (None, "")]

    user = os.environ.get("ERP_USER")
    password = os.environ.get("ERP_PASSWORD")
    if not user or not password:
        raise RuntimeError("Defina ERP_USER y ERP_PASSWORD en el entorno")
    client = FrappeClient(BASE_URL, user, password)

    items_result = safe_list(client, "Item", ["name", "item_code", "item_name", "stock_uom", "disabled", "is_stock_item"], [], 10000)
    if not items_result["ok"]:
        raise RuntimeError(f"No se pudo consultar Item: {items_result['error']}")
    items = items_result["data"]
    item_by_name: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in items:
        item_by_name[normalize(item.get("item_name"))].append(item)

    matched_codes: list[str] = []
    row_matches = []
    for row in rows:
        matches = item_by_name.get(normalize(row.get(name_key)), [])
        codes = [str(item.get("item_code") or item.get("name")) for item in matches]
        matched_codes.extend(codes)
        row_matches.append({
            "excel_name": row.get(name_key),
            "uom_excel": row.get(uom_key),
            "qty": row.get(qty_key),
            "invoice_code": row.get(code_key),
            "item_matches": matches,
            "match_status": "exact_one" if len(matches) == 1 else ("not_found" if not matches else "multiple"),
        })
    unique_codes = sorted(set(matched_codes))

    suppliers = []
    supplier_errors = []
    stock_entries = []
    stock_errors = []
    purchase_receipts = []
    purchase_receipt_errors = []
    purchase_invoice_items = []
    purchase_invoice_errors = []
    for code_chunk in chunks(unique_codes):
        result = safe_list(client, "Item Supplier", ["name", "parent", "supplier", "supplier_part_no"], [["parent", "in", code_chunk]], 10000)
        if result["ok"]:
            suppliers.extend(result["data"])
        else:
            supplier_errors.append(result["error"])
        result = safe_list(client, "Stock Entry Detail", ["name", "parent", "item_code", "qty", "s_warehouse", "t_warehouse"], [["item_code", "in", code_chunk]], 10000)
        if result["ok"]:
            stock_entries.extend(result["data"])
        else:
            stock_errors.append(result["error"])
        result = safe_list(client, "Purchase Receipt Item", ["name", "parent", "item_code", "qty", "rate", "warehouse"], [["item_code", "in", code_chunk]], 10000)
        if result["ok"]:
            purchase_receipts.extend(result["data"])
        else:
            purchase_receipt_errors.append(result["error"])
        result = safe_list(client, "Purchase Invoice Item", ["name", "parent", "item_code", "qty", "rate"], [["item_code", "in", code_chunk]], 10000)
        if result["ok"]:
            purchase_invoice_items.extend(result["data"])
        else:
            purchase_invoice_errors.append(result["error"])

    stock_parent_names = sorted(set(str(row["parent"]) for row in stock_entries if row.get("parent")))
    receipt_parent_names = sorted(set(str(row["parent"]) for row in purchase_receipts if row.get("parent")))
    invoice_parent_names = sorted(set(str(row["parent"]) for row in purchase_invoice_items if row.get("parent")))
    stock_headers = []
    receipt_headers = []
    invoice_headers = []
    for doctype, names, fields, target in [
        ("Stock Entry", stock_parent_names, ["name", "posting_date", "stock_entry_type", "docstatus", "company", "from_warehouse", "to_warehouse"], stock_headers),
        ("Purchase Receipt", receipt_parent_names, ["name", "posting_date", "supplier", "docstatus", "company", "set_warehouse"], receipt_headers),
        ("Purchase Invoice", invoice_parent_names, ["name", "posting_date", "supplier", "docstatus", "company", "bill_no"], invoice_headers),
    ]:
        for name_chunk in chunks(names):
            result = safe_list(client, doctype, fields, [["name", "in", name_chunk]], 10000)
            if result["ok"]:
                target.extend(result["data"])

    supplier_by_item: dict[str, list[dict[str, object]]] = defaultdict(list)
    for supplier in suppliers:
        supplier_by_item[str(supplier.get("parent"))].append(supplier)
    for match in row_matches:
        match["suppliers"] = []
        for item in match["item_matches"]:
            code = str(item.get("item_code") or item.get("name"))
            match["suppliers"].extend(supplier_by_item.get(code, []))

    report = {
        "source": str(excel_path),
        "source_summary": {
            "data_rows": len(rows),
            "unique_product_names": len(product_counts),
            "duplicate_product_names": {key: count for key, count in product_counts.items() if count > 1},
            "rows_without_invoice_code": len(missing_code_rows),
            "invoice_codes_are_mixed_types": sorted({type(row.get(code_key)).__name__ for row in rows if row.get(code_key) not in (None, "")}),
        },
        "erp_summary": {
            "items_consulted": len(items),
            "excel_rows_exactly_one_item": sum(match["match_status"] == "exact_one" for match in row_matches),
            "excel_rows_without_item": sum(match["match_status"] == "not_found" for match in row_matches),
            "excel_rows_with_multiple_items": sum(match["match_status"] == "multiple" for match in row_matches),
            "matched_item_codes": len(unique_codes),
            "item_supplier_rows": sum(len(values) for values in supplier_by_item.values()),
            "stock_entry_detail_rows": len(stock_entries),
            "purchase_receipt_item_rows": len(purchase_receipts),
            "purchase_invoice_item_rows": len(purchase_invoice_items),
        },
        "errors": {
            "item_supplier": supplier_errors,
            "stock_entry_detail": stock_errors,
            "purchase_receipt_item": purchase_receipt_errors,
            "purchase_invoice_item": purchase_invoice_errors,
        },
        "rows": row_matches,
        "existing_documents": {
            "stock_entry_headers": stock_headers,
            "stock_entry_items": stock_entries,
            "purchase_receipt_headers": receipt_headers,
            "purchase_receipt_items": purchase_receipts,
            "purchase_invoice_headers": invoice_headers,
            "purchase_invoice_items": purchase_invoice_items,
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
