from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from openpyxl import load_workbook

from audit_erp import FrappeClient, normalize


def tokens(value: object) -> set[str]:
    return {token for token in normalize(value).split() if len(token) > 1}


def similarity(source: str, candidate: str, source_uom: object, candidate_uom: object) -> float:
    source_normalized = normalize(source)
    candidate_normalized = normalize(candidate)
    source_tokens = tokens(source)
    candidate_tokens = tokens(candidate)
    if not source_tokens or not candidate_tokens:
        token_overlap = 0.0
    else:
        token_overlap = len(source_tokens & candidate_tokens) / len(source_tokens | candidate_tokens)
    containment = 0.0
    if source_tokens and candidate_tokens:
        containment = len(source_tokens & candidate_tokens) / min(len(source_tokens), len(candidate_tokens))
    sequence = SequenceMatcher(None, source_normalized, candidate_normalized).ratio()
    score = 0.40 * sequence + 0.35 * token_overlap + 0.25 * containment
    source_numbers = set(re.findall(r"\d+", source_normalized))
    candidate_numbers = set(re.findall(r"\d+", candidate_normalized))
    if source_numbers and candidate_numbers:
        if source_numbers & candidate_numbers:
            score += 0.12
        else:
            score -= 0.08
    if normalize(source_uom) == normalize(candidate_uom):
        score += 0.06
    return min(score, 1.0)


def read_rows(path: Path) -> list[dict[str, object]]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    worksheet = workbook.active
    values = list(worksheet.iter_rows(values_only=True))
    workbook.close()
    headers = [str(value).strip() if value is not None else "" for value in values[0]]
    return [dict(zip(headers, row)) for row in values[1:] if any(value is not None for value in row)]


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print("Uso: uv run ... python match_products.py <inventario.xlsx> [flat]", file=sys.stderr)
        return 2
    user = os.environ.get("ERP_USER")
    password = os.environ.get("ERP_PASSWORD")
    if not user or not password:
        raise RuntimeError("Defina ERP_USER y ERP_PASSWORD en el entorno")

    rows = read_rows(Path(sys.argv[1]).resolve())
    client = FrappeClient(os.environ.get("ERP_URL", "https://salsamentariamultiespecial.duckdns.org"), user, password)
    result = client.get_list("Item", ["name", "item_code", "item_name", "stock_uom", "disabled", "is_stock_item"], [], 10000)
    items_by_name: dict[str, list[dict[str, object]]] = {}
    for item in result:
        items_by_name.setdefault(normalize(item.get("item_name")), []).append(item)

    output = []
    exact_one = 0
    unresolved = 0
    for row in rows:
        name = str(row.get("Nombre del Producto") or "")
        exact_matches = items_by_name.get(normalize(name), [])
        status = "exact_one" if len(exact_matches) == 1 else ("multiple_exact" if exact_matches else "unresolved")
        if status == "exact_one":
            exact_one += 1
            continue
        unresolved += 1
        candidates = []
        for item in result:
            score = similarity(name, str(item.get("item_name") or ""), row.get("UOM"), item.get("stock_uom"))
            candidates.append({
                "score": round(score, 3),
                "item_code": item.get("item_code") or item.get("name"),
                "item_name": item.get("item_name"),
                "stock_uom": item.get("stock_uom"),
                "disabled": item.get("disabled"),
                "is_stock_item": item.get("is_stock_item"),
            })
        candidates.sort(key=lambda candidate: (-candidate["score"], str(candidate["item_code"])))
        output.append({
            "excel_name": name,
            "excel_uom": row.get("UOM"),
            "qty": row.get("Cant. Entrada"),
            "invoice_code": row.get("codigo de factura"),
            "status": status,
            "exact_matches": [
                {
                    "item_code": item.get("item_code") or item.get("name"),
                    "item_name": item.get("item_name"),
                    "stock_uom": item.get("stock_uom"),
                }
                for item in exact_matches
            ],
            "top_candidates": [
                {
                    "score": candidate["score"],
                    "item_code": candidate["item_code"],
                    "item_name": candidate["item_name"],
                    "stock_uom": candidate["stock_uom"],
                }
                for candidate in candidates[:3]
            ],
        })

    if len(sys.argv) == 3 and sys.argv[2] == "flat":
        for match in output:
            candidates = match["top_candidates"]
            best = candidates[0] if candidates else {}
            second = candidates[1] if len(candidates) > 1 else {}
            print("\t".join(str(value or "") for value in (
                match["excel_name"], match["status"], best.get("score"), best.get("item_code"), best.get("item_name"), second.get("score"), second.get("item_code"), second.get("item_name"))))
        return 0
    print(json.dumps({
        "excel_rows": len(rows),
        "exact_one_rows": exact_one,
        "rows_requiring_review": unresolved,
        "matches": output,
    }, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
