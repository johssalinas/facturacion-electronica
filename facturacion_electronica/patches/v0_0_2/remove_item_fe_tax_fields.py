import frappe

OBSOLETE_FIELDS = [
	"Item-fe_tax_code",
	"Item-fe_tax_rate",
	"Item-fe_is_excluded",
]


def execute():
	for name in OBSOLETE_FIELDS:
		if frappe.db.exists("Custom Field", name):
			try:
				frappe.delete_doc("Custom Field", name)
			except Exception:
				pass
