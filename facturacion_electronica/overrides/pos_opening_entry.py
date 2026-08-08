import frappe
from frappe import _
from erpnext.accounts.doctype.pos_opening_entry.pos_opening_entry import POSOpeningEntry


class CustomPOSOpeningEntry(POSOpeningEntry):
	"""Override POS Opening Entry to support shared cash register.

	We keep the standard validation that prevents opening a profile already open
	(since we want only ONE open register at a time). The key change is in
	check_opening_entry which lets any user find and use the existing open register.
	"""
	pass


@frappe.whitelist()
def check_opening_entry(user):
	"""Find any open POS Opening Entry for the user's assigned POS Profiles.

	Unlike the standard version which only returns entries opened by the current user,
	this returns ANY open entry for a POS Profile the user has access to.
	This allows multiple users to sell on the same open cash register.
	"""
	# Get POS Profiles this user is allowed to use
	user_profiles = frappe.get_all(
		"POS Profile User",
		filters={"user": user},
		fields=["parent"],
		pluck="parent",
	)

	if not user_profiles:
		# Fallback: check if there's any POS Profile without user restrictions
		user_profiles = frappe.get_all(
			"POS Profile",
			filters={"disabled": 0},
			fields=["name"],
			pluck="name",
		)

	if not user_profiles:
		return []

	# Find any open POS Opening Entry for those profiles (regardless of who opened it)
	open_vouchers = frappe.get_all(
		"POS Opening Entry",
		filters={
			"pos_profile": ["in", user_profiles],
			"pos_closing_entry": ["in", ["", None]],
			"docstatus": 1,
		},
		fields=["name", "company", "pos_profile", "period_start_date"],
		order_by="period_start_date desc",
	)

	return open_vouchers
