import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder.functions import Sum
from pypika.terms import Timestamp
from pypika.queries import Column as ConstantColumn
from pypika import functions as fn
from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import POSClosingEntry


class CustomPOSClosingEntry(POSClosingEntry):
	"""Override POS Closing Entry for shared cash register.

	Removes the owner validation so that a closing entry can include
	invoices from ANY user who sold on the same POS Profile during the period.
	"""

	def validate_pos_invoices(self):
		"""Validate POS invoices without checking owner."""
		invalid_rows = []

		for d in self.pos_invoices:
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

			# NOTE: No owner check — shared cash register

			if invalid_row.get("msg"):
				invalid_rows.append(invalid_row)

		if not invalid_rows:
			return

		error_list = []
		for row in invalid_rows:
			for msg in row.get("msg"):
				error_list.append(f"Row #{row.get('idx')}: {msg}")

		frappe.throw(error_list, title=_("Invalid POS Invoices"), as_list=True)

	def validate_pos_sales_invoices(self):
		"""Validate Sales Invoices without checking owner."""
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

			# NOTE: No owner check — shared cash register

			if invalid_row.get("msg"):
				invalid_rows.append(invalid_row)

		if not invalid_rows:
			return

		error_list = []
		for row in invalid_rows:
			for msg in row.get("msg"):
				error_list.append(f"Row #{row.get('idx')}: {msg}")

		frappe.throw(error_list, title=_("Invalid Sales Invoices"), as_list=True)


@frappe.whitelist()
def get_invoices(start, end, pos_profile, user):
	"""Get invoices for POS Closing — includes ALL users, not just the closing user.

	This is the override for the standard get_invoices that filters by owner.
	In a shared cash register, all invoices on the same POS Profile during the
	period belong to the same cash register regardless of who created them.
	"""
	invoice_doctype = frappe.db.get_single_value("POS Settings", "invoice_type")

	sales_inv_query = _build_shared_invoice_query("Sales Invoice", pos_profile, start, end)
	query = sales_inv_query

	if invoice_doctype == "POS Invoice":
		pos_inv_query = _build_shared_invoice_query("POS Invoice", pos_profile, start, end)
		query = query + pos_inv_query

	query = query.orderby(query.timestamp)
	invoices = query.run(as_dict=1)

	from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import (
		get_payments,
		get_taxes,
	)

	data = {"invoices": invoices, "payments": get_payments(invoices), "taxes": get_taxes(invoices)}
	return data


def _build_shared_invoice_query(invoice_doctype, pos_profile, start, end):
	"""Build invoice query WITHOUT filtering by owner — shared cash register."""
	InvoiceDocType = DocType(invoice_doctype)
	query = (
		frappe.qb.from_(InvoiceDocType)
		.select(
			InvoiceDocType.name,
			InvoiceDocType.customer,
			InvoiceDocType.posting_date,
			InvoiceDocType.grand_total,
			InvoiceDocType.net_total,
			InvoiceDocType.total_qty,
			InvoiceDocType.total_taxes_and_charges,
			InvoiceDocType.change_amount,
			InvoiceDocType.account_for_change_amount,
			InvoiceDocType.is_return,
			InvoiceDocType.return_against,
			InvoiceDocType.owner,
			fn.Timestamp(InvoiceDocType.posting_date, InvoiceDocType.posting_time).as_("timestamp"),
			ConstantColumn(invoice_doctype).as_("doctype"),
		)
		.where(
			# NOTE: No owner filter — all users on same profile
			(InvoiceDocType.docstatus == 1)
			& (InvoiceDocType.is_pos == 1)
			& (InvoiceDocType.pos_profile == pos_profile)
			& (
				(fn.Timestamp(InvoiceDocType.posting_date, InvoiceDocType.posting_time) >= start)
				& (fn.Timestamp(InvoiceDocType.posting_date, InvoiceDocType.posting_time) <= end)
			)
			& (InvoiceDocType.consolidated_invoice.isnull() | (InvoiceDocType.consolidated_invoice == ""))
		)
	)
	return query
