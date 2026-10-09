"""Temp utility to set environment to Sandbox"""
import frappe


@frappe.whitelist(allow_guest=False)
def set_sandbox_mode():
	"""Cambia el ambiente a Sandbox"""
	if not frappe.session.user == "Administrator":
		frappe.throw("Solo Administrator")
	
	config = frappe.get_single("Configuracion API FE")
	config.ambiente = "Sandbox"
	config.save(ignore_permissions=True)
	frappe.db.commit()
	
	return {"ok": True, "ambiente": config.ambiente}
