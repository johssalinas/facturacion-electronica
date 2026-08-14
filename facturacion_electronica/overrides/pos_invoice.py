import frappe
from frappe import _

from erpnext.accounts.doctype.pos_invoice.pos_invoice import POSInvoice

from facturacion_electronica.utils.api_fe import _duenos_en_factura, enviar_factura_fe


class CustomPOSInvoice(POSInvoice):
	def validate_pos_opening_entry(self):
		"""Override to remove the 'outdated' date check.

		In our setup, a cash register can stay open across midnight
		(e.g., selling until 12am). We only check that an open entry exists
		for the POS Profile, without requiring it to be from today.
		"""
		opening_entries = frappe.get_all(
			"POS Opening Entry",
			fields=["name", "period_start_date"],
			filters={"pos_profile": self.pos_profile, "status": "Open"},
			order_by="period_start_date desc",
		)
		if not opening_entries:
			frappe.throw(
				title=_("POS Opening Entry Missing"),
				msg=_("No open POS Opening Entry found for POS Profile {0}.").format(
					frappe.bold(self.pos_profile)
				),
			)
		if len(opening_entries) > 1:
			frappe.throw(
				title=_("Multiple POS Opening Entry"),
				msg=_(
					"POS Profile - {0} has multiple open POS Opening Entries. Please close or cancel the existing entries before proceeding."
				).format(self.pos_profile),
			)
		# NOTE: No date check — allow selling across midnight

	def before_submit(self):
		# Set allow_zero_valuation_rate=1 on every item so the stock ledger
		# never throws "Valuation Rate Missing" for items without prior stock
		# entries or with zero cost.  This is the correct ERPNext mechanism
		# to allow selling items whose valuation rate is 0 or unknown.
		for item in self.items:
			if not item.allow_zero_valuation_rate:
				item.allow_zero_valuation_rate = 1

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
