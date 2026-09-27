"""
Crea en ERPNext el Mode of Payment "Bold" y el ítem de servicio "COMISION-BOLD".

Ejecutar una sola vez desde el servidor:

  BC=$(docker ps -q --filter "name=backend-vvekd3jmyymltrmfoi8vdbdu" | head -1)
  docker exec $BC bash -lc '
    cd /home/frappe/frappe-bench &&
    bench --site salsamentariamultiespecial.duckdns.org execute \
      facturacion_electronica.utils.setup_bold.run
  '
"""

import frappe


def run():
    _create_mode_of_payment()
    _create_bold_item()
    frappe.db.commit()
    print("✅  Setup Bold completado.")


# ---------------------------------------------------------------------------
# Mode of Payment
# ---------------------------------------------------------------------------

def _create_mode_of_payment():
    name = "Bold"
    if frappe.db.exists("Mode of Payment", name):
        print(f"  · Mode of Payment '{name}' ya existe — omitido.")
        return

    doc = frappe.get_doc({
        "doctype": "Mode of Payment",
        "mode_of_payment": name,
        "type": "Bank",
    })
    doc.flags.ignore_permissions = True
    doc.insert()
    print(f"  ✓ Mode of Payment '{name}' creado (type=Bank).")

    # Código DIAN: 48 = Tarjeta Débito (lo más representativo para datáfono)
    _asignar_fe_tipo_medio_pago(name, preferred_codes=["48", "22", "47"])


def _asignar_fe_tipo_medio_pago(mop_name, preferred_codes):
    for code in preferred_codes:
        if frappe.db.exists("Tipo Medio Pago FE", code):
            frappe.db.set_value("Mode of Payment", mop_name, "fe_tipo_medio_pago", code)
            print(f"  ✓ fe_tipo_medio_pago = '{code}' asignado a '{mop_name}'.")
            return
    codes = frappe.db.get_all("Tipo Medio Pago FE", pluck="name")
    print(f"  ⚠  Ningún código preferido encontrado. Disponibles: {codes}")
    print(f"     Asigna fe_tipo_medio_pago manualmente: Mode of Payment > Bold.")


# ---------------------------------------------------------------------------
# Item COMISION-BOLD
# ---------------------------------------------------------------------------

def _create_bold_item():
    item_code = "COMISION-BOLD"
    if frappe.db.exists("Item", item_code):
        print(f"  · Item '{item_code}' ya existe — omitido.")
        return

    company = (
        frappe.db.get_single_value("Global Defaults", "default_company")
        or "Salsamentaria Multiespecial"
    )

    # Buscar una cuenta de ingresos activa (no grupo) de la compañía
    income_account = frappe.db.get_value(
        "Account",
        {
            "company": company,
            "account_type": "Income Account",
            "is_group": 0,
            "disabled": 0,
        },
        "name",
    ) or f"Sales - SM"

    doc = frappe.get_doc({
        "doctype": "Item",
        "item_code": item_code,
        "item_name": "Comisión Bold (1.5%)",
        "item_group": "Services",
        "stock_uom": "Nos",
        "is_stock_item": 0,
        "is_sales_item": 1,
        "is_purchase_item": 0,
        "include_item_in_manufacturing": 0,
        "description": (
            "Recargo automático por pago con datáfono Bold. "
            "Equivale al 1.5% del total de la venta. "
            "No modificar manualmente — el POS lo calcula al seleccionar el modo de pago Bold."
        ),
        "item_defaults": [
            {
                "company": company,
                "income_account": income_account,
            }
        ],
    })
    doc.flags.ignore_permissions = True
    doc.insert()
    print(f"  ✓ Item '{item_code}' creado.")
    print(f"    income_account: {income_account}")
    print(f"    Nota: el ítem NO necesita lista de precios — el POS asigna la tasa dinámicamente.")
