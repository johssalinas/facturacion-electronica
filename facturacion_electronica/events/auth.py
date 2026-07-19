import frappe

DESKTOP_USERS = ["sharith@gmail.com", "lorena@gmail.com", "andrea@gmail.com"]


def on_login(login_manager):
	pass


def boot_session(bootinfo):
	user = frappe.session.user
	if user in DESKTOP_USERS:
		bootinfo.desktop_redirect = "/desk/desktop"
