import frappe
from frappe import _
from erpnext.accounts.doctype.pos_opening_entry.pos_opening_entry import POSOpeningEntry


class CustomPOSOpeningEntry(POSOpeningEntry):
	"""Override POS Opening Entry to allow multiple users to open the same POS Profile.

	In a small store, multiple people (cajera + administradora) may need to sell
	from different devices using the same POS Profile. Each user opens and closes
	their own cash register independently.

	Changes:
	- Removes the check that blocks opening a POS Profile if it's already open by another user.
	- Keeps the check that prevents the same user from having two open POS sessions.
	"""

	def validate(self):
		# Call parent validate but skip check_open_pos_exists
		self.validate_pos_profile_and_cashier()
		self.check_user_already_assigned()
		self.validate_payment_method_account()

	def validate_pos_profile_and_cashier(self):
		"""Same as parent but without the 'profile already open' check."""
		from frappe.utils import cint

		if not frappe.db.exists("POS Profile", self.pos_profile):
			frappe.throw(_("POS Profile {} does not exist.").format(self.pos_profile))

		pos_profile_company, pos_profile_disabled = frappe.db.get_value(
			"POS Profile", self.pos_profile, ["company", "disabled"]
		)

		if pos_profile_disabled:
			frappe.throw(_("POS Profile {} is disabled.").format(frappe.bold(self.pos_profile)))

		if self.company != pos_profile_company:
			frappe.throw(
				_("POS Profile {} does not belong to company {}").format(self.pos_profile, self.company)
			)

		if not cint(frappe.db.get_value("User", self.user, "enabled")):
			frappe.throw(_("User {} is disabled. Please select valid user/cashier").format(self.user))

		# NOTE: We intentionally do NOT call check_open_pos_exists() here.
		# This allows multiple users to have the same POS Profile open simultaneously.
