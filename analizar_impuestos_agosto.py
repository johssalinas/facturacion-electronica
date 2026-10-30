"""Analiza las cuentas de impuestos usadas en agosto 2026"""
import frappe

frappe.init(site="salsamentariamultiespecial.duckdns.org")
frappe.connect()

# Ver todas las cuentas de impuestos usadas en agosto
result = frappe.db.sql("""
    SELECT DISTINCT
        stc.account_head,
        stc.rate,
        COUNT(DISTINCT si.name) as num_facturas,
        SUM(si.grand_total) as total
    FROM `tabSales Taxes and Charges` stc
    INNER JOIN `tabSales Invoice` si ON si.name = stc.parent
    WHERE si.posting_date >= '2026-08-01'
    AND si.posting_date <= '2026-08-31'
    AND si.docstatus = 1
    AND stc.parenttype = 'Sales Invoice'
    GROUP BY stc.account_head, stc.rate
    ORDER BY num_facturas DESC
""", as_dict=1)

print("\n=== CUENTAS DE IMPUESTOS USADAS EN AGOSTO ===")
for r in result:
    print(f"{r.account_head:60} | Rate: {r.rate:>5} | {r.num_facturas:>4} facturas | Total: ${r.total:>15,.0f}")

# Ver total sin filtro de impuestos
total_agosto = frappe.db.sql("""
    SELECT 
        COUNT(*) as facturas,
        SUM(grand_total) as total
    FROM `tabSales Invoice`
    WHERE posting_date >= '2026-08-01'
    AND posting_date <= '2026-08-31'
    AND docstatus = 1
""", as_dict=1)[0]

print(f"\n=== TOTAL AGOSTO (TODAS LAS FACTURAS SUBMITTED) ===")
print(f"Facturas: {total_agosto.facturas}")
print(f"Total: ${total_agosto.total:,.0f}")

frappe.destroy()
