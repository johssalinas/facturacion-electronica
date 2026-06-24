import frappe
from frappe import _


def on_cancel(doc, method=None):
	if doc.get("estado_fe") in ("Validada", "Enviada"):
		frappe.msgprint(
			_(
				"Esta factura fue enviada a la DIAN. Para anularla electronicamente debe emitir"
				" una nota credito. El estado FE se marca como 'No Aplica' en ERPNext."
			),
			indicator="orange",
		)
	doc.db_set("estado_fe", "No Aplica")


@frappe.whitelist()
def reenviar_pos_invoice_dian(name):
	from facturacion_electronica.utils.api_fe import _duenos_en_factura, enviar_factura_fe

	doc = frappe.get_doc("POS Invoice", name)
	duenos = _duenos_en_factura(doc)
	if not duenos:
		frappe.throw(_("La factura no tiene items con dueño fiscal asignado"))
	for dueno, items in duenos.items():
		enviar_factura_fe(doc, dueno, items, tipo_operacion="Manual")
	return {"ok": True, "estado": doc.get("estado_fe")}
