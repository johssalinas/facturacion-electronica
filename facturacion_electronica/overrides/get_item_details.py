import json

import frappe
from erpnext.stock.get_item_details import (
	get_item_tax_template as _native_get_item_tax_template,
)


@frappe.whitelist()
def get_item_tax_template(ctx, item=None, out=None):
	"""Preserva la plantilla de impuesto del item si ya está asignada.

	ERPNext vuelve a consultar la plantilla de impuesto cuando se cambia el precio
	('rate') de una fila, y como usa las plantillas nativas del Item (tabla 'taxes',
	que está vacía), termina BORRANDO la plantilla que viene del campo custom
	'purchase_tax_template'. Aquí, si la fila ya trae plantilla, la conservamos.
	"""
	if isinstance(ctx, str):
		try:
			ctx = json.loads(ctx)
		except Exception:
			ctx = {}

	if isinstance(ctx, dict) and ctx.get("item_tax_template"):
		return ctx["item_tax_template"]

	return _native_get_item_tax_template(ctx, item, out)
