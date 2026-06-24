import frappe
from frappe import _

from facturacion_electronica.utils.api_fe import _duenos_en_factura, enviar_factura_fe


def before_submit(doc, method=None):
	if doc.get("es_resumen_diario_ccf"):
		doc.custom_enviar_dian = 1
		return
	cust = frappe.get_cached_doc("Customer", doc.customer)
	if cust.get("requiere_factura_inmediata") and not doc.get("custom_enviar_dian"):
		doc.custom_enviar_dian = 1


def on_submit(doc, method=None):
	if not doc.get("custom_enviar_dian"):
		return
	if doc.get("es_resumen_diario_ccf"):
		dueno = doc.get("dueno_fiscal_fe")
		if not dueno:
			return
		try:
			enviar_factura_fe(doc, dueno, list(doc.items), tipo_operacion="Resumen Diario CCF")
		except Exception as e:
			frappe.log_error(title=f"FE Resumen SI {doc.name}", message=str(e))
			frappe.msgprint(
				_("Error al enviar resumen a DIAN: {0}. Se reintentara despues.").format(str(e)),
				indicator="red",
			)
		return
	duenos = _duenos_en_factura(doc)
	if not duenos:
		doc.db_set("estado_fe", "No Aplica")
		return
	for dueno, items in duenos.items():
		try:
			enviar_factura_fe(doc, dueno, items, tipo_operacion="Inmediata B2B")
		except Exception as e:
			frappe.log_error(title=f"FE B2B SI {doc.name} {dueno}", message=str(e))
			frappe.msgprint(
				_("Error al enviar a DIAN para el dueño {0}: {1}. Se reintentara despues.").format(
					dueno, str(e)
				),
				indicator="red",
			)
