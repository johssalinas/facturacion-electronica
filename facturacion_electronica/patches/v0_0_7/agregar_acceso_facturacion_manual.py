import json

import frappe

USERS = ["lorena@gmail.com", "andrea@gmail.com"]

NUEVO_ITEM = {
	"label": "Facturacion Manual FE",
	"link": "/app/facturacion-manual-fe",
	"link_type": "External",
	"icon_type": "Link",
	"icon": "file-pdf",
	"standard": 1,
	"name": "Facturacion Manual FE",
	"hidden": 0,
	"restrict_removal": 0,
	"bg_color": "gray",
	"parent_icon": None,
}


def execute():
	"""Agrega el acceso directo 'Facturacion Manual FE' al desktop de Lorena
	y Andrea, justo despues de 'Log Factura Electronica' / antes de
	'Configuracion API FE', sin duplicar si ya existe.
	"""
	for user in USERS:
		if not frappe.db.exists("Desktop Layout", user):
			continue
		doc = frappe.get_doc("Desktop Layout", user)
		try:
			items = json.loads(doc.layout or "[]")
		except Exception:
			continue
		if any(i.get("name") == "Facturacion Manual FE" for i in items):
			continue

		# Insertar despues del item "Log FE" (Log Factura Electronica); si no
		# existe, al final antes de idx 99 (Documentacion), o al final.
		insert_after_idx = None
		for i in items:
			if i.get("name") == "Log FE":
				insert_after_idx = i.get("idx")
				break

		if insert_after_idx is not None:
			for i in items:
				if i.get("idx", 0) > insert_after_idx and i.get("idx", 0) < 99:
					i["idx"] = i.get("idx", 0) + 1
			nuevo_idx = insert_after_idx + 1
		else:
			max_idx = max([i.get("idx", 0) for i in items if i.get("idx", 0) < 99], default=0)
			nuevo_idx = max_idx + 1

		item = dict(NUEVO_ITEM)
		item["idx"] = nuevo_idx
		items.append(item)
		items.sort(key=lambda i: i.get("idx", 0))

		doc.db_set("layout", json.dumps(items), update_modified=False)
		frappe.db.commit()
		print(f"Acceso 'Facturacion Manual FE' agregado al desktop de {user}")
