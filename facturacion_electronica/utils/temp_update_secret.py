"""Temporal utility to update encrypted client_secret"""
import frappe
from frappe.utils.password import set_encrypted_password


@frappe.whitelist(allow_guest=False)
def update_client_secret_lorena():
	"""Actualiza el client_secret de Lorena (sandbox) - solo para admin"""
	if not frappe.session.user == "Administrator":
		frappe.throw("Solo Administrator puede ejecutar esto")
	
	set_encrypted_password(
		"Dueno Fiscal",
		"Lorena",
		"irQBN5wSWIVKA4Lo0aui2vgHzqNQS3XDwqUaiLUu",
		fieldname="client_secret"
	)
	frappe.db.commit()
	
	return {"ok": True, "msg": "client_secret actualizado"}
