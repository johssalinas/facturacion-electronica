"""
Exporta TODOS los productos con su inventario actual en el formato
exacto del reporte Stock Balance de ERPNext (mismas columnas, mismos
estilos, mismo motor xlsxwriter via frappe.utils.xlsxutils.make_xlsx).

Incluye productos con y sin movimientos de inventario (LEFT JOIN).

Uso:
    bench --site salsamentariamultiespecial.duckdns.org \
          execute facturacion_electronica.exportar_inventario.run
"""

import frappe
from frappe.utils.xlsxutils import make_xlsx, get_default_xlsx_styles


def run():
    site = "salsamentariamultiespecial.duckdns.org"

    # ── 1. Columnas idénticas al reporte Stock Balance ────────────────────────
    columns = [
        {"label": "Producto",           "fieldname": "item_code",  "fieldtype": "Link",     "width": 100},
        {"label": "Nombre del Producto","fieldname": "item_name",  "fieldtype": "Data",      "width": 150},
        {"label": "Grupo de Producto",  "fieldname": "item_group", "fieldtype": "Link",     "width": 100},
        {"label": "Almacén",            "fieldname": "warehouse",  "fieldtype": "Link",     "width": 100},
        {"label": "UOM",                "fieldname": "stock_uom",  "fieldtype": "Link",     "width":  90},
        {"label": "Cant. Saldo",        "fieldname": "bal_qty",    "fieldtype": "Float",    "width": 100},
        {"label": "Cant. Apertura",     "fieldname": "opening_qty","fieldtype": "Float",    "width": 100},
        {"label": "Cant. Entrada",      "fieldname": "in_qty",     "fieldtype": "Float",    "width":  80},
        {"label": "Cant. Salida",       "fieldname": "out_qty",    "fieldtype": "Float",    "width":  80},
        {"label": "Empresa",            "fieldname": "company",    "fieldtype": "Link",     "width": 100},
    ]

    # ── 2. Consulta SQL — LEFT JOIN para incluir items SIN movimientos ────────
    rows_raw = frappe.db.sql("""
        SELECT
            i.item_code,
            i.item_name,
            i.item_group,
            COALESCE(sle.warehouse, 'Sin movimientos') AS warehouse,
            i.stock_uom,
            COALESCE(SUM(sle.actual_qty), 0)                          AS bal_qty,
            COALESCE(SUM(CASE WHEN sle.actual_qty > 0
                              THEN sle.actual_qty ELSE 0 END), 0)     AS in_qty,
            COALESCE(SUM(CASE WHEN sle.actual_qty < 0
                              THEN ABS(sle.actual_qty) ELSE 0 END),0) AS out_qty,
            COALESCE(sle.company, 'Salsamentaria Multiespecial')      AS company
        FROM `tabItem` i
        LEFT JOIN `tabStock Ledger Entry` sle
               ON sle.item_code = i.item_code
              AND sle.docstatus = 1
              AND sle.is_cancelled = 0
        WHERE i.disabled = 0
        GROUP BY
            i.item_code,
            i.item_name,
            i.item_group,
            sle.warehouse,
            i.stock_uom,
            sle.company
        ORDER BY i.item_name, sle.warehouse
    """, as_dict=True)

    if not rows_raw:
        print("No se encontraron productos.")
        return

    # ── 3. Calcular opening_qty (saldo antes del primer movimiento = 0
    #       para simplificar, igual que Stock Balance sin fecha de inicio) ─────
    for r in rows_raw:
        r["opening_qty"] = 0.0

    print(f"Total de filas (producto × almacén): {len(rows_raw)}")
    print(f"  Con stock > 0 : {sum(1 for r in rows_raw if (r.bal_qty or 0) > 0)}")
    print(f"  Con stock = 0 : {sum(1 for r in rows_raw if (r.bal_qty or 0) == 0)}")
    print(f"  Con stock < 0 : {sum(1 for r in rows_raw if (r.bal_qty or 0) < 0)}")

    # ── 4. Fila de totales (igual que Stock Balance) ───────────────────────────
    total_row = {
        "item_code":   "Total",
        "item_name":   "",
        "item_group":  "",
        "warehouse":   "",
        "stock_uom":   "",
        "bal_qty":     sum(r.get("bal_qty")  or 0 for r in rows_raw),
        "opening_qty": 0.0,
        "in_qty":      sum(r.get("in_qty")   or 0 for r in rows_raw),
        "out_qty":     sum(r.get("out_qty")  or 0 for r in rows_raw),
        "company":     "",
    }
    all_rows = list(rows_raw) + [total_row]

    # ── 5. Convertir a lista de listas (formato que espera make_xlsx) ─────────
    fieldnames = [c["fieldname"] for c in columns]
    header_row  = [c["label"] for c in columns]

    data_rows = [header_row]
    for row in all_rows:
        data_rows.append([row.get(f) for f in fieldnames])

    # ── 6. Estilos usando el sistema nativo de Frappe ─────────────────────────
    styles = get_default_xlsx_styles(
        columns=columns,
        data=list(rows_raw),        # sin la fila total para el cálculo de índices
        has_total_row=True,
    )

    # ── 7. Generar el Excel ───────────────────────────────────────────────────
    column_widths = [c["width"] for c in columns]
    xlsx_data = make_xlsx(
        data=data_rows,
        sheet_name="Stock Balance",
        column_widths=column_widths,
        styles=styles,
    )

    output_path = "/tmp/inventario_productos.xlsx"
    with open(output_path, "wb") as f:
        f.write(xlsx_data.getvalue())

    print(f"Excel guardado en: {output_path}")
