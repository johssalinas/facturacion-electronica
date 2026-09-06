import frappe


def apply_purchase_tax_template(doc, method):
    """Aplica la plantilla de impuesto de compra definida en el producto (Item).

    Si algun producto tiene el campo 'purchase_tax_template' definido, se usa
    esa plantilla en la factura de compra, sobrescribiendo la regla automatica
    por categoria. Pensado para proveedores que NO cobran IVA ('Compra Sin IVA').
    """
    if doc.doctype != "Purchase Invoice" or doc.get("is_return"):
        return

    template = None
    for item in doc.items:
        if not item.get("item_code"):
            continue
        t = frappe.db.get_value("Item", item.item_code, "purchase_tax_template")
        if t:
            template = t
            break

    if template and template != doc.get("taxes_and_charges"):
        doc.taxes_and_charges = template
        doc.taxes = []
