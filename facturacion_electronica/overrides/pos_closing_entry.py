import frappe
from frappe import _
from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import POSClosingEntry


class CustomPOSClosingEntry(POSClosingEntry):
	"""Override POS Closing Entry to allow closing with invoices from any user.

	In a multi-user POS setup (same profile, multiple users), the closing entry
	should accept invoices created by any user during that session, not just
	the user who opened the cash register.

	The owner field on POS Invoice still records who made the sale for audit purposes.
	"""

	def validate_pos_invoices(self):
		"""Same as parent but without the owner check on individual invoices."""
		invalid_rows = []

		for d in self.pos_transactions:
			invalid_row = {"idx": d.idx}
			pos_invoice = frappe.db.get_values(
				"POS Invoice",
				d.pos_invoice,
				["consolidated_invoice", "pos_profile", "docstatus", "owner"],
				as_dict=1,
			)

			if not pos_invoice:
				invalid_row.setdefault("msg", []).append(_("POS Invoice not found"))
				invalid_rows.append(invalid_row)
				continue

			pos_invoice = pos_invoice[0]

			if pos_invoice.consolidated_invoice:
				invalid_row.setdefault("msg", []).append(_("POS Invoice is already consolidated"))
				invalid_rows.append(invalid_row)
				continue

			if pos_invoice.pos_profile != self.pos_profile:
				invalid_row.setdefault("msg", []).append(
					_("POS Profile doesn't match {}").format(frappe.bold(self.pos_profile))
				)

			if pos_invoice.docstatus != 1:
				invalid_row.setdefault("msg", []).append(_("POS Invoice is not submitted"))

			# NOTE: We intentionally do NOT check pos_invoice.owner != self.user
			# This allows closing the cash register with invoices from multiple users.

			if invalid_row.get("msg"):
				invalid_rows.append(invalid_row)

		if not invalid_rows:
			return

		error_list = []
		for row in invalid_rows:
			for msg in row.get("msg"):
				error_list.append(f"Row #{row.get('idx')}: {msg}")

		frappe.throw(
			error_list,
			title=_("Invalid POS Invoices"),
			as_list=True,
		)

	def validate_pos_sales_invoices(self):
		"""Same as parent but without the owner check on sales invoices."""
		invalid_rows = []

		for d in self.sales_invoices:
			invalid_row = {"idx": d.idx}
			sales_invoice = frappe.db.get_values(
				"Sales Invoice",
				d.sales_invoice,
				["consolidated_invoice", "pos_profile", "docstatus", "owner"],
				as_dict=1,
			)

			if not sales_invoice:
				invalid_row.setdefault("msg", []).append(_("Sales Invoice not found"))
				invalid_rows.append(invalid_row)
				continue

			sales_invoice = sales_invoice[0]

			if sales_invoice.consolidated_invoice:
				invalid_row.setdefault("msg", []).append(_("Sales Invoice is already consolidated"))
				invalid_rows.append(invalid_row)
				continue

			if sales_invoice.pos_profile != self.pos_profile:
				invalid_row.setdefault("msg", []).append(
					_("POS Profile doesn't match {}").format(frappe.bold(self.pos_profile))
				)

			if sales_invoice.docstatus != 1:
				invalid_row.setdefault("msg", []).append(_("Sales Invoice is not submitted"))

			# NOTE: We intentionally do NOT check sales_invoice.owner != self.user

			if invalid_row.get("msg"):
				invalid_rows.append(invalid_row)

		if not invalid_rows:
			return

		error_list = []
		for row in invalid_rows:
			for msg in row.get("msg"):
				error_list.append(f"Row #{row.get('idx')}: {msg}")

		frappe.throw(
			error_list,
			title=_("Invalid Sales Invoices"),
			as_list=True,
		)
