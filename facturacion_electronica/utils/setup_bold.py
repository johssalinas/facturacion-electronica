"""Idempotent Bold configuration helper.

Creates/updates the Mode of Payment and configures every POS Profile that
already includes Bold. The old COMISION-BOLD item is disabled because the
surcharge is represented as a document-level charge, never as a cart item.
"""

import frappe

from facturacion_electronica.utils.bold_surcharge import DEFAULT_RATE

BOLD_MODE = "Bold"
DEFAULT_ACCOUNT = "41351 - Comercio al por Mayor - SM"


def run():
	_create_or_update_mode_of_payment()
	_configure_pos_profiles()
	_disable_legacy_item()
	frappe.db.commit()
	print("Bold configurado correctamente.")


def _create_or_update_mode_of_payment():
	if frappe.db.exists("Mode of Payment", BOLD_MODE):
		doc = frappe.get_doc("Mode of Payment", BOLD_MODE)
	else:
		doc = frappe.get_doc(
			{"doctype": "Mode of Payment", "mode_of_payment": BOLD_MODE, "type": "Bank"}
		)
		doc.flags.ignore_permissions = True
		doc.insert()

	if doc.type != "Bank":
		doc.db_set("type", "Bank", update_modified=False)

	if not doc.get("fe_tipo_medio_pago"):
		for value in ("Tarjeta de Débito", "Tarjeta Débito", "48", "Transferencia"):
			if frappe.db.exists("Tipo Medio Pago FE", value):
				doc.db_set("fe_tipo_medio_pago", value, update_modified=False)
				break


def _resolve_account(company):
	if frappe.db.exists("Account", DEFAULT_ACCOUNT):
		account_company, is_group, disabled = frappe.db.get_value(
			"Account", DEFAULT_ACCOUNT, ["company", "is_group", "disabled"]
		)
		if account_company == company and not is_group and not disabled:
			return DEFAULT_ACCOUNT

	return frappe.db.get_value(
		"Account",
		{
			"company": company,
			"root_type": "Income",
			"is_group": 0,
			"disabled": 0,
		},
		"name",
	)


def _configure_pos_profiles():
	profile_names = frappe.get_all(
		"POS Payment Method",
		filters={"mode_of_payment": BOLD_MODE, "parenttype": "POS Profile"},
		pluck="parent",
	)
	for name in set(profile_names):
		profile = frappe.get_doc("POS Profile", name)
		account = _resolve_account(profile.company)
		if not account:
			print(f"ADVERTENCIA: no hay cuenta de ingreso para configurar Bold en {name}.")
			continue
		profile.db_set("custom_bold_surcharge_rate", DEFAULT_RATE, update_modified=False)
		profile.db_set("custom_bold_surcharge_account", account, update_modified=False)
		print(f"POS Profile {name}: {DEFAULT_RATE}% -> {account}")


def _disable_legacy_item():
	if frappe.db.exists("Item", "COMISION-BOLD"):
		frappe.db.set_value("Item", "COMISION-BOLD", "disabled", 1, update_modified=False)
		print("Item legado COMISION-BOLD deshabilitado (ya no se usa en el carrito).")
