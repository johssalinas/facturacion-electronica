import frappe


def _ensure_property_setter(name, doc_type, field_name, property, value):
	if frappe.db.exists("Property Setter", name):
		frappe.db.set_value("Property Setter", name, "value", value, update_modified=False)
	else:
		frappe.get_doc(
			{
				"doctype": "Property Setter",
				"doc_type": doc_type,
				"doctype_or_field": "DocField",
				"field_name": field_name,
				"property": property,
				"value": value,
			}
		).insert(ignore_permissions=True)


def execute():
	# IVA de compra por producto (item-level):
	# 1) El campo item_tax_template del item de compra se alimenta del campo custom
	#    purchase_tax_template del producto.
	_ensure_property_setter(
		"Purchase Invoice Item-item_tax_template-fetch_from",
		"Purchase Invoice Item",
		"item_tax_template",
		"fetch_from",
		"item_code.purchase_tax_template",
	)

	# 2) En compras el IVA se suma a la base (no está incluido en el precio),
	#    a diferencia de ventas donde sí está incluido.
	_ensure_property_setter(
		"Purchase Taxes and Charges-included_in_print_rate-default",
		"Purchase Taxes and Charges",
		"included_in_print_rate",
		"default",
		"0",
	)

	frappe.db.commit()
