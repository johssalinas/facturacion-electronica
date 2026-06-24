import frappe
from frappe import _

from erpnext.accounts.doctype.pos_invoice.pos_invoice import POSInvoice

from facturacion_electronica.utils.api_fe import _duenos_en_factura, enviar_factura_fe


class CustomPOSInvoice(POSInvoice):
	def before_submit(self):
		try:
			super().before_submit()
		except AttributeError:
			pass
		self._clasificar_cliente_fe()

	def on_submit(self):
		try:
			super().on_submit()
		except AttributeError:
			pass
		if self.get("custom_enviar_dian"):
			self._enviar_a_dian_inmediato()

	def _clasificar_cliente_fe(self):
		cust = frappe.get_cached_doc("Customer", self.customer)
		if cust.get("requiere_factura_inmediata"):
			self.custom_enviar_dian = 1
		else:
			self.custom_enviar_dian = 0
			if not self.get("estado_fe"):
				self.estado_fe = "Pendiente"

	def _enviar_a_dian_inmediato(self):
		duenos = _duenos_en_factura(self)
		if not duenos:
			frappe.msgprint(
				_("La factura no tiene items con dueño fiscal asignado. No se envio a DIAN."),
				indicator="orange",
			)
			self.db_set("estado_fe", "No Aplica")
			return
		for dueno, items in duenos.items():
			try:
				enviar_factura_fe(self, dueno, items, tipo_operacion="Inmediata B2B")
			except Exception as e:
				frappe.log_error(title=f"FE B2B POS {self.name} {dueno}", message=str(e))
				frappe.msgprint(
					_("Error al enviar a DIAN para el dueño {0}: {1}. Se reintentara despues.").format(
						dueno, str(e)
					),
					indicator="red",
				)
		self.reload()
