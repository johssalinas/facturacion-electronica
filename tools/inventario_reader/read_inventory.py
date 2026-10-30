from __future__ import annotations

import json
import sys
from pathlib import Path

from openpyxl import load_workbook


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python read_inventory.py <archivo.xlsx>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1]).resolve()
    if not path.is_file():
        print(f"No existe el archivo: {path}", file=sys.stderr)
        return 1

    workbook = load_workbook(path, read_only=True, data_only=True)
    result = {"file": str(path), "sheets": []}
    for worksheet in workbook.worksheets:
        rows = worksheet.iter_rows(values_only=True)
        header = next(rows, ())
        sample = [list(row) for _, row in zip(range(10), rows)]
        result["sheets"].append(
            {
                "title": worksheet.title,
                "max_row": worksheet.max_row,
                "max_column": worksheet.max_column,
                "headers": list(header),
                "sample_rows": sample,
            }
        )
    workbook.close()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
