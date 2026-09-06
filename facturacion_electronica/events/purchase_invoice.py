import json

import frappe

PURCHASE_TAX_ACCOUNT = "13551 - IVA descontable - SM"


def apply_purchase_tax_template(doc, method):
	"""Aplica el IVA de compra por producto (item-level) en la factura de compra.

	Usa el campo 'purchase_tax_template' del producto (Plantilla Impuesto de Compra),
	que define la tarifa de IVA de compra de ese producto. Asigna 'item_tax_template'
	e 'item_tax_rate' a cada fila y quita la plantilla a nivel de factura, para que
	una factura con productos mixtos (19%, 5%, exento, sin IVA) calcule el IVA
	correcto por producto.
	"""
	if doc.doctype != "Purchase Invoice" or doc.get("is_return"):
		return

	for item in doc.items:
		if not item.get("item_code"):
			continue
		template = frappe.db.get_value("Item", item.item_code, "purchase_tax_template")
		item.item_tax_template = template
		if template:
			rate = frappe.db.get_value("Item Tax Template Detail", {"parent": template}, "tax_rate")
			item.item_tax_rate = json.dumps({PURCHASE_TAX_ACCOUNT: float(rate)}) if rate else "{}"
		else:
			item.item_tax_rate = "{}"

	doc.taxes_and_charges = None
	doc.taxes = []
