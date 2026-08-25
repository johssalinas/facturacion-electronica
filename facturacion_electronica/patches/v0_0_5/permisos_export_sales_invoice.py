import frappe


def execute():
	# Grant export permission on Sales Invoice (Factura de Venta) to Accounts Manager.
	# Custom DocPerm takes precedence over the standard DocPerm, so we update both.
	for role in ("Accounts Manager",):
		for doctype in ("Sales Invoice",):
			for name in frappe.get_all(
				"Custom DocPerm",
				filters={"parent": doctype, "role": role},
				fields=["name"],
				pluck="name",
			):
				if not frappe.db.get_value("Custom DocPerm", name, "export"):
					frappe.db.set_value("Custom DocPerm", name, "export", 1, update_modified=False)
			for name in frappe.get_all(
				"DocPerm",
				filters={"parent": doctype, "role": role},
				fields=["name"],
				pluck="name",
			):
				if not frappe.db.get_value("DocPerm", name, "export"):
					frappe.db.set_value("DocPerm", name, "export", 1, update_modified=False)

	# Ensure export on Item (Producto) for the sales/admin roles already granted.
	for role in ("Sales Manager", "Item Manager"):
		for name in frappe.get_all(
			"Custom DocPerm",
			filters={"parent": "Item", "role": role},
			fields=["name"],
			pluck="name",
		):
			if not frappe.db.get_value("Custom DocPerm", name, "export"):
				frappe.db.set_value("Custom DocPerm", name, "export", 1, update_modified=False)

	frappe.db.commit()
