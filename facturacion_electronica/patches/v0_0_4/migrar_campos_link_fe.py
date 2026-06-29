import frappe

CODE_TO_NOMBRE = {
	"Tipo Documento Identidad FE": {
		"13": "C\u00e9dula de Ciudadan\u00eda",
		"31": "NIT",
		"22": "C\u00e9dula de Extranjer\u00eda",
		"41": "Pasaporte",
		"42": "PPT",
		"50": "NIT Otro Pa\u00eds",
		"91": "NUIP",
	},
	"Tributo FE": {
		"01": "IVA",
		"02": "IVA y Consumo",
		"03": "Excluido de IVA",
		"04": "No Responsable de IVA",
		"ZZ": "No Aplica",
	},
	"Municipio FE": {
		"68001": "Bucaramanga",
		"68276": "Floridablanca",
		"68406": "Gir\u00f3n",
		"68417": "Lebrija",
		"68547": "Piedecuesta",
	},
	"Codigo Impuesto FE": {
		"01": "IVA",
		"04": "Impuesto Nacional al Consumo",
		"35": "Ultraprocesados",
	},
	"Unidad Medida FE": {
		"94": "Unidad",
		"KGM": "Kilogramo",
		"GRM": "Gramo",
		"MGM": "Miligramo",
		"LBR": "Libra",
		"LTR": "Litro",
		"MLT": "Mililitro",
		"GLL": "Gal\u00f3n",
		"MTR": "Metro",
		"CMT": "Cent\u00edmetro",
		"MMT": "Mil\u00edmetro",
		"KTM": "Kil\u00f3metro",
		"BX": "Caja",
		"PK": "Paquete",
		"DZN": "Docena",
		"ONZ": "Onza",
		"BO": "Botella",
		"VI": "Frasco",
		"SA": "Saco",
		"PR": "Par",
		"U2": "Tableta",
		"SR": "Tira",
		"TU": "Tubo",
		"HUR": "Hora",
		"NRL": "Rollo",
	},
}

MIGRATIONS = [
	("Customer", "fe_identification_document_code", "Tipo Documento Identidad FE"),
	("Customer", "fe_tribute_code", "Tributo FE"),
	("Customer", "fe_municipality_code", "Municipio FE"),
	("Account", "fe_tax_code", "Codigo Impuesto FE"),
	("UOM", "fe_unit_measure_code", "Unidad Medida FE"),
	("Dueno Fiscal", "municipality_code", "Municipio FE"),
]

MODO_PAGO_AUTO = {
	"efectivo": "Efectivo",
	"cash": "Efectivo",
	"transferencia": "Transferencia",
	"nequi": "Transferencia",
	"daviplata": "Transferencia",
	"pse": "Transferencia",
	"banco": "Transferencia",
	"tarjeta de credito": "Tarjeta de Cr\u00e9dito",
	"tarjeta credito": "Tarjeta de Cr\u00e9dito",
	"credito": "Tarjeta de Cr\u00e9dito",
	"tarjeta de debito": "Tarjeta de D\u00e9bito",
	"tarjeta debito": "Tarjeta de D\u00e9bito",
	"debito": "Tarjeta de D\u00e9bito",
	"cheque": "Cheque",
	"consignacion": "Consignaci\u00f3n",
	"consignaci\u00f3n": "Consignaci\u00f3n",
}


def _migrar_campo(doctype, fieldname, target_doctype):
	mapping = CODE_TO_NOMBRE.get(target_doctype, {})
	nombres_validos = set(mapping.values())
	try:
		rows = frappe.db.get_all(
			doctype,
			filters={fieldname: ["not in", ["", None]]},
			fields=["name", fieldname],
			as_list=True,
		)
	except Exception:
		return
	for name, old_val in rows:
		if not old_val or old_val in nombres_validos:
			continue
		new_val = mapping.get(old_val)
		if new_val:
			frappe.db.set_value(doctype, name, fieldname, new_val, update_modified=False)


def _auto_asignar_modos_pago():
	try:
		rows = frappe.db.get_all("Mode of Payment", fields=["name", "mode_of_payment"])
	except Exception:
		return
	for row in rows:
		key = (row.mode_of_payment or "").lower().strip()
		if not key:
			continue
		tipo = MODO_PAGO_AUTO.get(key)
		if not tipo:
			for k, v in MODO_PAGO_AUTO.items():
				if k in key or key in k:
					tipo = v
					break
		if tipo:
			frappe.db.set_value(
				"Mode of Payment", row.name, "fe_tipo_medio_pago", tipo, update_modified=False
			)


def _migrar_configuracion_api_fe():
	try:
		config = frappe.get_single("Configuracion API FE")
	except Exception:
		return
	for fieldname, target_doctype in [
		("tax_code_default", "Codigo Impuesto FE"),
		("unidad_medida_default", "Unidad Medida FE"),
	]:
		mapping = CODE_TO_NOMBRE.get(target_doctype, {})
		old_val = config.get(fieldname)
		if old_val and old_val in mapping:
			config.db_set(fieldname, mapping[old_val])


def execute():
	for doctype, fieldname, target_doctype in MIGRATIONS:
		_migrar_campo(doctype, fieldname, target_doctype)
	_migrar_configuracion_api_fe()
	_auto_asignar_modos_pago()
