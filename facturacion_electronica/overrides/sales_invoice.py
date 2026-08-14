import frappe
from frappe import _

from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice


class CustomSalesInvoice(SalesInvoice):
	def validate_pos_opening_entry(self):
		"""Override to remove the 'outdated' date check.

		Allows selling across midnight without forcing a new opening entry.
		Only validates that an open entry exists for the POS Profile.
		"""
		if not self.is_pos:
			return

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
		# Set allow_zero_valuation_rate=1 on every stock item row so the
		# stock ledger never throws "Valuation Rate Missing" for items that
		# have no prior stock entries or a zero cost/valuation rate.
		#
		# This covers both POS Sales Invoices (POS Settings.invoice_type ==
		# "Sales Invoice") and regular Sales Invoices with update_stock=1.
		# The stock ledger checks this flag in check_if_allow_zero_valuation_rate()
		# before throwing the error.  Using the official ERPNext field means
		# accounting still posts correctly with a zero valuation rate.
		for item in self.items:
			if not item.allow_zero_valuation_rate:
				item.allow_zero_valuation_rate = 1

		super().before_submit()
