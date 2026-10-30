from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import load_workbook

DB_CONTAINER = "db-vvekd3jmyymltrmfoi8vdbdu-153547931911"
DB_NAME = "_95ec91ca53977b46"
DB_USER = "root"
DB_PASSWORD = os.environ.get("ERP_DB_PASSWORD")
SSH_HOST = "root@46.225.227.129"
SSH_KEY = str(Path.home() / ".ssh" / "id_ed25519_hetzner")


def sql_quote(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def read_names(path: Path) -> list[str]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    worksheet = workbook.active
    rows = list(worksheet.iter_rows(values_only=True))
    workbook.close()
    headers = [str(value).strip() if value is not None else "" for value in rows[0]]
    name_index = headers.index("Nombre del Producto")
    return [str(row[name_index]).strip() for row in rows[1:] if row[name_index] not in (None, "")]


def run_query(names: list[str]) -> list[dict[str, object]]:
    if not DB_PASSWORD:
        raise RuntimeError("Defina ERP_DB_PASSWORD en el entorno")
    name_values = ", ".join(sql_quote(name) for name in sorted(set(names)))
    sql = f"""
SELECT 'ITEM_SUPPLIER' AS kind, i.item_code, i.item_name, s.name AS parent,
       NULL AS posting_date, NULL AS docstatus, s.supplier,
       s.supplier_part_no AS reference_code, NULL AS qty, NULL AS rate
FROM `tabItem` i
LEFT JOIN `tabItem Supplier` s ON s.parent = i.name
WHERE i.item_name IN ({name_values})
UNION ALL
SELECT 'STOCK_ENTRY', i.item_code, i.item_name, se.name,
       se.posting_date, se.docstatus, NULL,
       se.stock_entry_type, sed.qty, NULL
FROM `tabItem` i
JOIN `tabStock Entry Detail` sed ON sed.item_code = i.item_code
JOIN `tabStock Entry` se ON se.name = sed.parent
WHERE i.item_name IN ({name_values})
UNION ALL
SELECT 'PURCHASE_RECEIPT', i.item_code, i.item_name, pr.name,
       pr.posting_date, pr.docstatus, pr.supplier,
       NULL, pri.qty, pri.rate
FROM `tabItem` i
JOIN `tabPurchase Receipt Item` pri ON pri.item_code = i.item_code
JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
WHERE i.item_name IN ({name_values})
UNION ALL
SELECT 'PURCHASE_INVOICE', i.item_code, i.item_name, pi.name,
       pi.posting_date, pi.docstatus, pi.supplier,
       pi.bill_no, pii.qty, pii.rate
FROM `tabItem` i
JOIN `tabPurchase Invoice Item` pii ON pii.item_code = i.item_code
JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
WHERE i.item_name IN ({name_values})
ORDER BY item_name, kind, parent;
"""
    command = [
        "ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
        "-i", SSH_KEY, SSH_HOST,
        f"docker exec -i {DB_CONTAINER} mariadb -u {DB_USER} -p{DB_PASSWORD} -D {DB_NAME} --default-character-set=utf8mb4 --batch --raw --skip-column-names",
    ]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, timeout=120)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    records = []
    for line in completed.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) != 10:
            continue
        keys = ["kind", "item_code", "item_name", "parent", "posting_date", "docstatus", "supplier", "reference_code", "qty", "rate"]
        record = dict(zip(keys, fields))
        for key in ("posting_date", "supplier", "reference_code", "qty", "rate"):
            if record[key] == "NULL":
                record[key] = None
        if record["docstatus"] == "NULL":
            record["docstatus"] = None
        records.append(record)
    return records


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print("Uso: uv run ... python sql_audit.py <inventario.xlsx> [invoices]", file=sys.stderr)
        return 2
    path = Path(sys.argv[1]).resolve()
    names = read_names(path)
    records = run_query(names)
    by_item: dict[str, dict[str, object]] = defaultdict(lambda: {"item_code": None, "item_name": None, "suppliers": [], "stock_entries": [], "purchase_receipts": [], "purchase_invoices": []})
    for record in records:
        code = record["item_code"]
        item = by_item[code]
        item["item_code"] = code
        item["item_name"] = record["item_name"]
        kind = record["kind"]
        if kind == "ITEM_SUPPLIER":
            if record["supplier"] is not None:
                item["suppliers"].append({"supplier": record["supplier"], "supplier_part_no": record["reference_code"]})
        elif kind == "STOCK_ENTRY":
            item["stock_entries"].append({k: record[k] for k in ("parent", "posting_date", "docstatus", "reference_code", "qty")})
        elif kind == "PURCHASE_RECEIPT":
            item["purchase_receipts"].append({k: record[k] for k in ("parent", "posting_date", "docstatus", "supplier", "qty", "rate")})
        elif kind == "PURCHASE_INVOICE":
            item["purchase_invoices"].append({k: record[k] for k in ("parent", "posting_date", "docstatus", "supplier", "reference_code", "qty", "rate")})

    missing_supplier = []
    matched = []
    not_in_erp = sorted(set(names) - {str(item["item_name"]) for item in by_item.values()})
    for item in by_item.values():
        compact = {"item_code": item["item_code"], "item_name": item["item_name"]}
        if item["suppliers"]:
            matched.append({**compact, "suppliers": item["suppliers"]})
        else:
            missing_supplier.append(compact)
    name_to_codes: dict[str, list[str]] = defaultdict(list)
    for item in by_item.values():
        name_to_codes[str(item["item_name"])].append(str(item["item_code"]))
    existing_documents = []
    for item in by_item.values():
        if item["stock_entries"] or item["purchase_receipts"] or item["purchase_invoices"]:
            existing_documents.append({
                "item_code": item["item_code"],
                "item_name": item["item_name"],
                "stock_entries": item["stock_entries"],
                "purchase_receipts": item["purchase_receipts"],
                "purchase_invoices": item["purchase_invoices"],
            })

    stock_rollup: dict[str, dict[str, object]] = {}
    invoice_rollup: dict[str, dict[str, object]] = {}
    for item in by_item.values():
        for row in item["stock_entries"]:
            key = str(row["parent"])
            entry = stock_rollup.setdefault(key, {"parent": key, "posting_date": row["posting_date"], "docstatus": row["docstatus"], "reference_code": row["reference_code"], "lines": 0, "qty": 0.0})
            entry["lines"] += 1
            entry["qty"] += float(row["qty"] or 0)
        for row in item["purchase_invoices"]:
            key = str(row["parent"])
            entry = invoice_rollup.setdefault(key, {"parent": key, "posting_date": row["posting_date"], "docstatus": row["docstatus"], "supplier": row["supplier"], "bill_no": row["reference_code"], "lines": 0, "qty": 0.0})
            entry["lines"] += 1
            entry["qty"] += float(row["qty"] or 0)

    compact_report = {
        "source": str(path),
        "excel_product_rows": len(names),
        "excel_unique_product_names": len(set(names)),
        "erp_products_found_by_exact_name": len(by_item),
        "erp_products_not_found_by_exact_name": len(not_in_erp),
        "ambiguous_erp_names": {name: codes for name, codes in name_to_codes.items() if len(codes) > 1},
        "products_with_supplier_rows": len(matched),
        "products_without_supplier_rows": len(missing_supplier),
        "supplier_rows": sum(len(item["suppliers"]) for item in by_item.values()),
        "stock_entry_lines_for_excel_products": sum(len(item["stock_entries"]) for item in by_item.values()),
        "purchase_receipt_lines_for_excel_products": sum(len(item["purchase_receipts"]) for item in by_item.values()),
        "purchase_invoice_lines_for_excel_products": sum(len(item["purchase_invoices"]) for item in by_item.values()),
        "stock_entry_documents_for_excel_products": len(stock_rollup),
        "purchase_invoice_documents_for_excel_products": len(invoice_rollup),
        "not_in_erp": not_in_erp,
        "missing_supplier_products": missing_supplier,
        "stock_entry_rollup": sorted(stock_rollup.values(), key=lambda row: (str(row["posting_date"]), str(row["parent"]))),
        "purchase_invoice_rollup": sorted(invoice_rollup.values(), key=lambda row: (str(row["posting_date"]), str(row["parent"]))),
    }
    if len(sys.argv) == 3 and sys.argv[2] == "stock":
        print(json.dumps({"stock_entry_rollup": sorted(stock_rollup.values(), key=lambda row: (str(row["posting_date"]), str(row["parent"])))}, ensure_ascii=False, indent=2))
        return 0
    if len(sys.argv) == 3 and sys.argv[2] == "invoices":
        print(json.dumps({"purchase_invoice_rollup": sorted(invoice_rollup.values(), key=lambda row: (str(row["posting_date"]), str(row["parent"])))}, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(compact_report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
