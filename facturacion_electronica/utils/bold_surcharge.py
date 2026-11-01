"""Canonical Bold surcharge calculation for POS invoices.

The cashier enters the sales portion paid through Bold. The system charges
that amount plus the configured surcharge. The browser provides immediate
feedback, but this module is authoritative and runs again on the server.
"""

import frappe
from frappe import _
from frappe.utils import flt

BOLD_MODE = "Bold"
BOLD_TAX_DESCRIPTION = "Comisión Bold (1.5%)"
DEFAULT_RATE = 1.5


def _is_bold_payment(row):
	return (row.get("mode_of_payment") or "").strip().casefold() == BOLD_MODE.casefold()


def _is_bold_tax(row):
	return bool(row.get("custom_is_bold_surcharge")) or row.get("description") == BOLD_TAX_DESCRIPTION


def _precision(doc):
	return doc.precision("grand_total") or 2


def _rounded(doc, value):
	return flt(value, _precision(doc))


def get_settings_for_profile(pos_profile, company=None):
	if not pos_profile:
		frappe.throw(_("POS Profile is required to calculate the Bold surcharge."))

	profile = frappe.get_cached_doc("POS Profile", pos_profile)
	if company and profile.company != company:
		frappe.throw(_("POS Profile {0} does not belong to company {1}.").format(pos_profile, company))

	rate = flt(profile.get("custom_bold_surcharge_rate") or DEFAULT_RATE)
	account = profile.get("custom_bold_surcharge_account")
	if rate < 0:
		frappe.throw(_("Bold surcharge rate cannot be negative."))
	if not account:
		frappe.throw(
			_("Configure the Bold surcharge account in POS Profile {0}.").format(frappe.bold(pos_profile))
		)

	account_values = frappe.get_cached_value(
		"Account", account, ["company", "is_group", "disabled"], as_dict=True
	)
	if not account_values:
		frappe.throw(_("Bold surcharge account {0} does not exist.").format(account))
	if account_values.company != profile.company:
		frappe.throw(_("Bold surcharge account must belong to company {0}.").format(profile.company))
	if account_values.is_group or account_values.disabled:
		frappe.throw(_("Bold surcharge account must be an enabled ledger account."))

	return {"rate": rate, "account": account}


@frappe.whitelist()
def get_settings(pos_profile):
	"""Return the POS Profile configuration used by the POS preview."""
	settings = get_settings_for_profile(pos_profile)
	return {"rate": settings["rate"], "account": settings["account"]}


def _resolve_base_amount(doc, bold_payments, tax_rows, rate):
	"""Resolve the sales portion paid through Bold without compounding.

	The hidden base field is canonical when the current payment still matches
	base + surcharge. Legacy drafts without that field are inferred from the
	existing surcharge. A changed raw payment is interpreted as a new base.
	"""
	precision = _precision(doc)
	tolerance = 1 / (10**precision)
	payment_amount = _rounded(doc, sum(flt(row.amount) for row in bold_payments))
	current_surcharge = _rounded(doc, sum(flt(row.tax_amount) for row in tax_rows))
	stored_base = _rounded(doc, doc.get("custom_bold_base_amount") or 0)

	if stored_base:
		expected = _rounded(doc, stored_base + stored_base * rate / 100)
		if abs(payment_amount - expected) <= tolerance:
			return stored_base

	if current_surcharge:
		inferred = _rounded(doc, payment_amount - current_surcharge)
		expected_surcharge = _rounded(doc, inferred * rate / 100)
		if abs(current_surcharge - expected_surcharge) <= tolerance:
			return inferred

	return payment_amount


def normalize_bold_surcharge(doc):
	"""Create exactly one Bold surcharge row and normalize the Bold payment.

	This function is idempotent. It is safe to call during every validation and
	on both draft save and submit.
	"""
	bold_payments = [row for row in (doc.get("payments") or []) if _is_bold_payment(row)]
	tax_rows = [row for row in (doc.get("taxes") or []) if _is_bold_tax(row)]

	if not bold_payments:
		for row in tax_rows:
			doc.remove(row)
		doc.custom_bold_base_amount = 0
		doc.custom_bold_surcharge_amount = 0
		return

	payment_amount = _rounded(doc, sum(flt(row.amount) for row in bold_payments))
	stored_base = _rounded(doc, doc.get("custom_bold_base_amount") or 0)
	if not payment_amount and not stored_base and not tax_rows:
		doc.custom_bold_base_amount = 0
		doc.custom_bold_surcharge_amount = 0
		return

	settings = get_settings_for_profile(doc.pos_profile, doc.company)
	rate = settings["rate"]
	base = _resolve_base_amount(doc, bold_payments, tax_rows, rate)

	if not doc.is_return and base < 0:
		frappe.throw(_("Bold payment amount cannot be negative."))
	if doc.is_return and base > 0:
		frappe.throw(_("Bold payment amount must be negative on a return."))

	commission = _rounded(doc, base * rate / 100)
	gross = _rounded(doc, base + commission)
	doc.custom_bold_base_amount = base
	doc.custom_bold_surcharge_amount = commission

	primary_payment = bold_payments[0]
	primary_payment.amount = gross
	for duplicate in bold_payments[1:]:
		duplicate.amount = 0

	if not commission:
		for row in tax_rows:
			doc.remove(row)
		doc.calculate_taxes_and_totals()
		return

	if tax_rows:
		primary_tax = tax_rows[0]
		for duplicate in tax_rows[1:]:
			doc.remove(duplicate)
	else:
		primary_tax = doc.append("taxes", {})

	primary_tax.charge_type = "Actual"
	primary_tax.account_head = settings["account"]
	primary_tax.description = BOLD_TAX_DESCRIPTION
	primary_tax.tax_amount = commission
	primary_tax.included_in_print_rate = 0
	primary_tax.custom_is_bold_surcharge = 1
	if doc.get("cost_center") and not primary_tax.get("cost_center"):
		primary_tax.cost_center = doc.cost_center

	doc.calculate_taxes_and_totals()


def validate_bold_surcharge(doc):
	"""Assert the normalized values after ERPNext's own validation."""
	bold_payments = [row for row in (doc.get("payments") or []) if _is_bold_payment(row)]
	tax_rows = [row for row in (doc.get("taxes") or []) if _is_bold_tax(row)]
	base = _rounded(doc, doc.get("custom_bold_base_amount") or 0)
	commission = _rounded(doc, doc.get("custom_bold_surcharge_amount") or 0)

	if not bold_payments or not base:
		if tax_rows or commission:
			frappe.throw(_("Bold surcharge remained on an invoice without a Bold payment."))
		return

	settings = get_settings_for_profile(doc.pos_profile, doc.company)
	expected_commission = _rounded(doc, base * settings["rate"] / 100)
	expected_gross = _rounded(doc, base + expected_commission)
	actual_gross = _rounded(doc, sum(flt(row.amount) for row in bold_payments))
	actual_commission = _rounded(doc, sum(flt(row.tax_amount) for row in tax_rows))

	if len(tax_rows) != 1:
		frappe.throw(_("The POS invoice must contain exactly one Bold surcharge row."))
	if actual_commission != expected_commission or commission != expected_commission:
		frappe.throw(_("Bold surcharge is inconsistent with the Bold payment amount."))
	if actual_gross != expected_gross:
		frappe.throw(_("Bold payment must include its configured surcharge."))
