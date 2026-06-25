import frappe

OBSOLETE_FIELDS = [
	"Item-fe_unit_measure_code",
	"Item-fe_standard_code",
]


def execute():
	for name in OBSOLETE_FIELDS:
		if frappe.db.exists("Custom Field", name):
			try:
				frappe.delete_doc("Custom Field", name)
			except Exception:
				pass
