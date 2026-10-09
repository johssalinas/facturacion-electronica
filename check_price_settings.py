"""
Revisa las configuraciones nativas de ERPNext que pueden afectar
el precio de venta al registrar una Purchase Invoice.
"""
import frappe


def run():
    # ── 1. Buying Settings ────────────────────────────────────────────────────
    buying = frappe.get_single("Buying Settings")
    print("=== Buying Settings ===")
    print(f"  maintain_same_rate              : {buying.get('maintain_same_rate')}")
    print(f"  maintain_same_rate_action        : {buying.get('maintain_same_rate_action')}")
    print(f"  allow_multiple_items             : {buying.get('allow_multiple_items')}")

    # ── 2. Stock Settings ─────────────────────────────────────────────────────
    stock = frappe.get_single("Stock Settings")
    print("\n=== Stock Settings ===")
    print(f"  auto_insert_price_list_rate_if_missing : {stock.get('auto_insert_price_list_rate_if_missing')}")
    print(f"  update_existing_price_list_rate        : {stock.get('update_existing_price_list_rate')}")
    print(f"  valuation_method                       : {stock.get('valuation_method')}")
    print(f"  set_qty_in_transactions_based_on_material_transfer : {stock.get('set_qty_in_transactions_based_on_material_transfer')}")

    # ── 3. Selling Settings ───────────────────────────────────────────────────
    selling = frappe.get_single("Selling Settings")
    print("\n=== Selling Settings ===")
    print(f"  selling_price_list : {selling.get('selling_price_list')}")
    print(f"  maintain_same_rate : {selling.get('maintain_same_rate')}")

    # ── 4. Item Prices activas en lista de venta estándar ─────────────────────
    price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list") or "Standard Selling"
    item_prices = frappe.db.sql("""
        SELECT item_code, price_list, price_list_rate, modified, modified_by
        FROM `tabItem Price`
        WHERE price_list = %s
        ORDER BY modified DESC
        LIMIT 20
    """, price_list, as_dict=True)

    print(f"\n=== Últimas 20 modificaciones en Item Price (lista: {price_list}) ===")
    for p in item_prices:
        print(f"  {str(p.modified)[:16]}  {p.item_code:<30} ${p.price_list_rate:>12,.0f}  por: {p.modified_by}")

    # ── 5. Verificar en Purchase Invoice si ERPNext tiene lógica de update_price
    #       Buscar en Purchase Invoice Item si hay campo update_item_price o similar
    pi_item_cols = frappe.db.sql(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema=DATABASE() AND table_name='tabPurchase Invoice Item' "
        "AND column_name LIKE '%price%'",
        as_list=True
    )
    print("\n=== Columnas con 'price' en tabPurchase Invoice Item ===")
    for c in pi_item_cols:
        print(f"  {c[0]}")

    # ── 6. Ver si Purchase Invoice tiene campo update_stock o update_price ────
    pi_cols = frappe.db.sql(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema=DATABASE() AND table_name='tabPurchase Invoice' "
        "AND (column_name LIKE '%price%' OR column_name LIKE '%update%')",
        as_list=True
    )
    print("\n=== Columnas con 'price' o 'update' en tabPurchase Invoice ===")
    for c in pi_cols:
        print(f"  {c[0]}")

    # ── 7. Últimas Purchase Invoices sometidas ────────────────────────────────
    recent_pi = frappe.db.sql("""
        SELECT name, supplier, posting_date, docstatus, modified
        FROM `tabPurchase Invoice`
        WHERE docstatus = 1
        ORDER BY modified DESC
        LIMIT 10
    """, as_dict=True)
    print("\n=== Últimas 10 Purchase Invoices sometidas ===")
    for pi in recent_pi:
        print(f"  {pi.name}  {str(pi.posting_date)}  {pi.supplier}")
