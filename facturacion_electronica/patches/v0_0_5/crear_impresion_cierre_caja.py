import frappe
import json
import os
from frappe.utils import cint


def execute():
	# 1) Ensure the custom print format exists
	html_path = os.path.join(
		frappe.get_app_path("facturacion_electronica", "facturacion_electronica"),
		"print_format",
		"cierre_de_caja_sm",
		"cierre_de_caja_sm.json",
	)
	if not os.path.exists(html_path):
		# fallback: look one level up (nested app package)
		alt = os.path.join(
			frappe.get_app_path("facturacion_electronica"),
			"facturacion_electronica",
			"print_format",
			"cierre_de_caja_sm",
			"cierre_de_caja_sm.json",
		)
		if os.path.exists(alt):
			html_path = alt

	if os.path.exists(html_path):
		with open(html_path, encoding="utf-8") as f:
			data = json.load(f)
		data["doctype"] = "Print Format"
		if not frappe.db.exists("Print Format", "Cierre de Caja SM"):
			frappe.get_doc(data).insert(ignore_permissions=True)
			frappe.db.commit()
			print("Print Format Cierre de Caja SM creado")
		else:
			existing = frappe.get_doc("Print Format", "Cierre de Caja SM")
			changed = False
			if existing.html != data.get("html"):
				existing.html = data.get("html")
				changed = True
			if cint(existing.custom_format) != cint(data.get("custom_format", 0)):
				existing.custom_format = data.get("custom_format", 0)
				changed = True
			if changed:
				existing.save(ignore_permissions=True)
				frappe.db.commit()
				print("Print Format Cierre de Caja SM actualizado")

	# 2) Set it as the default print format for POS Closing Entry
	dt = frappe.db.get_value("DocType", "POS Closing Entry", "default_print_format")
	if dt != "Cierre de Caja SM":
		frappe.db.set_value("DocType", "POS Closing Entry", "default_print_format", "Cierre de Caja SM")
		frappe.db.commit()
		print("default_print_format POS Closing Entry -> Cierre de Caja SM")
