import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class FEConsumoItem(Document):
	def before_insert(self):
		if not self.fecha:
			self.fecha = now_datetime()
		if not self.item_name and self.item_code:
			self.item_name = frappe.db.get_value("Item", self.item_code, "item_name")
