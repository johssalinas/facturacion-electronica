"""Temp utility to update numbering_range_id"""
import frappe


@frappe.whitelist(allow_guest=False)
def update_numbering_range_id():
	"""Actualiza numbering_range_id a 6141 (sandbox)"""
	if not frappe.session.user == "Administrator":
		frappe.throw("Solo Administrator")
	
	frappe.db.set_value('Dueno Fiscal', 'Lorena', 'numbering_range_id', 6141)
	frappe.db.commit()
	
	# Verificar
	doc = frappe.get_doc("Dueno Fiscal", "Lorena")
	
	return {
		"ok": True, 
		"numbering_range_id": doc.numbering_range_id,
		"nombre": doc.name
	}
