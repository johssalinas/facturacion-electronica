import frappe
from frappe import _
from frappe.utils import flt
from frappe.query_builder import DocType
from frappe.query_builder import functions as fn
from frappe.query_builder.custom import ConstantColumn
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

	def validate_sales_invoices(self):
		"""Validate Sales Invoices without checking owner."""
		invalid_rows = []

		for d in self.sales_invoices:
			invalid_row = {"idx": d.idx}
			sales_invoice = frappe.db.get_values(
				"Sales Invoice",
				d.sales_invoice,
				["pos_profile", "docstatus", "owner", "is_pos", "is_created_using_pos", "pos_closing_entry"],
				as_dict=1,
			)

			if not sales_invoice:
				invalid_row.setdefault("msg", []).append(_("Sales Invoice not found"))
				invalid_rows.append(invalid_row)
				continue

			sales_invoice = sales_invoice[0]

			if sales_invoice.pos_closing_entry:
				invalid_row.setdefault("msg", []).append(_("Sales Invoice is already consolidated"))
				invalid_rows.append(invalid_row)
				continue

			if sales_invoice.is_pos == 0:
				invalid_row.setdefault("msg", []).append(_("Sales Invoice does not have Payments"))

			if sales_invoice.is_created_using_pos == 0:
				invalid_row.setdefault("msg", []).append(_("Sales Invoice is not created using POS"))

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

	# Deduct "Salida de Dinero" (cash outflows) posted during the period so the
	# expected cash in the register reflects money that left the cash drawer
	# (e.g. supplier paid in cash).
	salidas = _get_salidas_de_dinero(start, end, pos_profile)
	if salidas:
		for p in data["payments"]:
			salida_total = salidas.get(p.mode_of_payment, 0)
			if salida_total:
				p["amount"] = flt(p["amount"]) - flt(salida_total)
		data["salidas_de_dinero"] = _salidas_to_list(salidas)

	# Enrich invoices with mode_of_payment and payment status for display in the closing entry table
	for inv in invoices:
		payments = frappe.get_all(
			"Sales Invoice Payment",
			filters={"parent": inv.name, "amount": [">", 0]},
			fields=["mode_of_payment"],
			order_by="amount desc",
		)
		inv["custom_modo_de_pago"] = ", ".join(
			list(dict.fromkeys(p.mode_of_payment for p in payments))
		) if payments else ""

		# Determine payment status from outstanding_amount
		outstanding = frappe.db.get_value(inv.doctype, inv.name, "outstanding_amount") or 0
		grand_total = inv.get("grand_total") or 0
		if outstanding <= 0:
			inv["custom_estado_pago"] = "Pagada"
		elif grand_total and outstanding >= grand_total:
			inv["custom_estado_pago"] = "Sin Pago"
		else:
			inv["custom_estado_pago"] = "Pago Parcial"

	return data


def _get_salidas_de_dinero(start, end, pos_profile):
	"""Return {mode_of_payment: total_amount} of submitted Salida de Dinero in the period."""
	filters = {
		"docstatus": 1,
		"posting_date": [">=", frappe.utils.getdate(start)],
	}
	# match by period timestamp when possible
	rows = frappe.get_all(
		"Salida de Dinero",
		filters=filters,
		fields=["mode_of_payment", "amount", "posting_date", "posting_time"],
	)
	if not rows:
		return {}

	start_dt = _to_datetime(start)
	end_dt = _to_datetime(end)

	salidas = {}
	for r in rows:
		ts = _to_datetime(f"{r.posting_date} {r.posting_time or '00:00:00'}")
		if start_dt and end_dt and not (start_dt <= ts <= end_dt):
			continue
		salidas[r.mode_of_payment] = flt(salidas.get(r.mode_of_payment, 0)) + flt(r.amount)

	return salidas


def _to_datetime(value):
	try:
		return frappe.utils.get_datetime(value)
	except Exception:
		return None


def _salidas_to_list(salidas):
	return [{"mode_of_payment": k, "amount": v} for k, v in sorted(salidas.items())]


@frappe.whitelist()
def get_salidas_de_dinero(name):
	"""Return the submitted Salida de Dinero docs for a POS Closing Entry or a
	POS Opening Entry (name can be either)."""
	opening = name
	if frappe.db.exists("POS Closing Entry", name):
		opening = frappe.db.get_value("POS Closing Entry", name, "pos_opening_entry")
	if not opening or not frappe.db.exists("POS Opening Entry", opening):
		return []

	rows = frappe.get_all(
		"Salida de Dinero",
		filters={"docstatus": 1, "pos_opening_entry": opening},
		fields=[
			"name",
			"posting_date",
			"posting_time",
			"mode_of_payment",
			"amount",
			"description",
			"party",
			"ref_no",
		],
		order_by="creation asc",
	)
	return rows


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
		)
	)

	if invoice_doctype == "POS Invoice":
		query = query.where(fn.IfNull(InvoiceDocType.consolidated_invoice, "").eq(""))
	else:
		query = query.where(
			(InvoiceDocType.is_created_using_pos == 1)
			& fn.IfNull(InvoiceDocType.pos_closing_entry, "").eq("")
		)

	return query
