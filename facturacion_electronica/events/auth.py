import frappe

DESKTOP_USERS = ["sharith@gmail.com", "lorena@gmail.com"]


def on_login(login_manager):
	user = login_manager.user
	if user in DESKTOP_USERS:
		frappe.local.flags.redirect_location = "/desk/desktop"
