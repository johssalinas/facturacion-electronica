"""Configuracion idempotente del panel "Balance de Productos".

Se ejecuta en cada `bench migrate` (hook after_migrate) y crea o actualiza:

  * Number Cards (indicadores) y Dashboard Charts (graficos) basados en el reporte
    "Balance por Producto".
  * El Dashboard "Balance por Producto" y el Workspace "Balance de Productos".
  * La barra lateral y el icono de escritorio del panel.
  * Los enlaces dentro de los espacios y dashboards nativos de Ventas (Selling)
    e Inventario (Stock), y en el escritorio personalizado de Lorena y Andrea.

Cada paso corre aislado: si uno falla se registra en Error Log y el migrate continua.
Nunca modifica transacciones, inventario ni contabilidad.
"""

import json

import frappe

REPORT = "Balance por Producto"
MODULE = "Facturacion Electronica"
WORKSPACE = "Balance de Productos"
DASHBOARD = "Balance por Producto"
PANEL_LABEL = "Panel de Balance"
APP = "facturacion_electronica"
METODO_TARJETA = (
	"facturacion_electronica.facturacion_electronica.report.balance_por_producto.balance_por_producto.tarjeta"
)

ROLES = [
	"System Manager",
	"Dueño Negocio",
	"Accounts Manager",
	"Stock Manager",
	"Sales Manager",
	"Purchase Manager",
	"Auditor",
]
# "Accounts User" y "Stock User" quedan fuera a proposito: la cajera los tiene para poder
# facturar en el POS y no debe ver costos ni utilidad.

VISTA_TOTAL = "Evolución total"
G_DINERO = "Dinero: ventas, compras y utilidad"
G_INVENTARIO = "Inventario: valor al cierre"

# (nombre, kpi, rango, color)
TARJETAS = [
	("Ventas del mes", "ventas", "Mes actual", "#2490EF"),
	("Compras del mes", "compras", "Mes actual", "#F5A623"),
	("Utilidad bruta del mes", "utilidad", "Mes actual", "#29CD42"),
	("Margen bruto del mes", "margen", "Mes actual", "#29CD42"),
	("Valor del inventario", "inventario", "Año actual", "#8E44AD"),
	("Productos con pérdida (mes)", "perdiendo", "Mes actual", "#E24C4C"),
	("Ventas sin costo confiable (mes)", "sin_costo", "Mes actual", "#F1C40F"),
]

KPI_DINERO = {"ventas", "compras", "utilidad", "inventario", "sin_costo"}

FILTROS_FECHA = {
	"from_date": "frappe.datetime.year_start()",
	"to_date": "frappe.datetime.get_today()",
}

# (nombre, tipo de grafico, filtros del reporte, ancho en el dashboard)
GRAFICOS = [
	(
		"Ventas, compras y utilidad por mes",
		"Bar",
		{"vista": VISTA_TOTAL, "periodo": "Mensual", "grafico_evol": G_DINERO},
		"Full",
	),
	(
		"Ventas, compras y utilidad por semana",
		"Bar",
		{"vista": VISTA_TOTAL, "periodo": "Semanal", "grafico_evol": G_DINERO},
		"Full",
	),
	(
		"Valor del inventario por semana",
		"Line",
		{"vista": VISTA_TOTAL, "periodo": "Semanal", "grafico_evol": G_INVENTARIO},
		"Half",
	),
	(
		"Top 15 productos por utilidad",
		"Bar",
		{"vista": "Resumen por producto", "grafico": "Top 15 por utilidad"},
		"Half",
	),
	(
		"15 productos con menor utilidad",
		"Bar",
		{"vista": "Resumen por producto", "grafico": "15 con menor utilidad"},
		"Half",
	),
	(
		"Top 15 productos: compras vs ventas",
		"Bar",
		{"vista": "Resumen por producto", "grafico": "Top 15: compras vs ventas"},
		"Half",
	),
	(
		"Margen % de los 15 productos más vendidos",
		"Bar",
		{"vista": "Resumen por producto", "grafico": "Top 15: margen %"},
		"Half",
	),
]

# Se agregan a los dashboards nativos
CHARTS_VENTAS = ["Ventas, compras y utilidad por mes", "Top 15 productos por utilidad"]
CARDS_VENTAS = ["Utilidad bruta del mes", "Margen bruto del mes", "Productos con pérdida (mes)"]
CHARTS_STOCK = ["Valor del inventario por semana", "Top 15 productos: compras vs ventas"]
CARDS_STOCK = ["Valor del inventario", "Ventas sin costo confiable (mes)"]

# Atajos del Workspace (tipo, destino, doctype de referencia del reporte)
REPORTES_RELACIONADOS = [
	("Gross Profit", "Gross Profit"),
	("Item-wise Sales Register", "Item-wise Sales Register"),
	("Item-wise Purchase Register", "Item-wise Purchase Register"),
	("Stock Balance", "Stock Balance"),
	("Stock Ledger", "Stock Ledger"),
]


# --------------------------------------------------------------------------- #
# Punto de entrada
# --------------------------------------------------------------------------- #
def run():
	if not frappe.db.exists("Report", REPORT):
		print(f"Balance por Producto: el reporte '{REPORT}' aun no existe, se omite la configuracion del panel.")
		return

	pasos = [
		crear_tarjetas,
		crear_graficos,
		crear_dashboard,
		crear_workspace,
		crear_sidebar_e_icono,
		enlazar_dashboards_nativos,
		enlazar_sidebars_nativos,
		enlazar_workspaces_nativos,
		enlazar_escritorios_personalizados,
	]
	for paso in pasos:
		try:
			paso()
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"Balance por Producto: fallo en {paso.__name__}")
			print(f"ADVERTENCIA: fallo el paso {paso.__name__}; revise Error Log.")

	frappe.clear_cache()
	print("Panel Balance de Productos configurado.")


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def _roles():
	return [{"role": r} for r in ROLES if frappe.db.exists("Role", r)]


def _guardar(doctype, nombre, valores, tablas=None):
	"""Crea o actualiza un documento. `tablas` reemplaza tablas hijas completas."""
	if frappe.db.exists(doctype, nombre):
		doc = frappe.get_doc(doctype, nombre)
		doc.update(valores)
	else:
		doc = frappe.new_doc(doctype)
		doc.update(valores)
	for campo, filas in (tablas or {}).items():
		doc.set(campo, [])
		for fila in filas:
			doc.append(campo, fila)
	doc.flags.ignore_permissions = True
	if doc.is_new():
		doc.insert()
	else:
		doc.save()
	return doc


def _id():
	return frappe.generate_hash(length=10)


# --------------------------------------------------------------------------- #
# Number Cards y Dashboard Charts
# --------------------------------------------------------------------------- #
def crear_tarjetas():
	moneda = frappe.defaults.get_global_default("currency") or "COP"
	for nombre, kpi, rango, color in TARJETAS:
		_guardar(
			"Number Card",
			nombre,
			{
				"label": nombre,
				"type": "Custom",
				"method": METODO_TARJETA,
				# Number Card Custom se autoriza segun el permiso de lectura de este DocType.
				# Se usa uno que la cajera (Sales/Stock/Accounts User) no puede leer.
				"document_type": "Stock Reconciliation",
				"module": MODULE,
				"is_public": 1,
				"is_standard": 0,
				"show_full_number": 1,
				"color": color,
				# Frappe aplica la moneda de la tarjeta a cualquier valor: solo las tarjetas de dinero la llevan
				"currency": moneda if kpi in KPI_DINERO else None,
				"filters_json": json.dumps({"kpi": kpi, "rango": rango}),
			},
		)


def crear_graficos():
	for nombre, tipo, filtros, _ancho in GRAFICOS:
		_guardar(
			"Dashboard Chart",
			nombre,
			{
				"chart_name": nombre,
				"chart_type": "Report",
				"report_name": REPORT,
				"use_report_chart": 1,
				"type": tipo,
				"module": MODULE,
				"is_public": 1,
				"is_standard": 0,
				"timeseries": 0,
				"filters_json": json.dumps(filtros),
				"dynamic_filters_json": json.dumps(FILTROS_FECHA),
			},
			tablas={"roles": _roles()},
		)


def crear_dashboard():
	_guardar(
		"Dashboard",
		DASHBOARD,
		{"dashboard_name": DASHBOARD, "module": MODULE, "is_standard": 0},
		tablas={
			"charts": [{"chart": nombre, "width": ancho} for nombre, _t, _f, ancho in GRAFICOS],
			"cards": [{"card": nombre} for nombre, *_ in TARJETAS],
		},
	)


# --------------------------------------------------------------------------- #
# Workspace propio
# --------------------------------------------------------------------------- #
def _bloque(tipo, **data):
	data.setdefault("col", 12)
	return {"id": _id(), "type": tipo, "data": data}


def _contenido_workspace():
	bloques = [
		_bloque(
			"header",
			text='<span class="h3"><b>Balance por producto</b></span>',
		),
		_bloque(
			"paragraph",
			text=(
				"¿Qué estoy ganando o perdiendo en cada producto? Compras, ventas, utilidad e inventario, "
				"por día, semana, mes y año. Abra el reporte para filtrar, exportar a Excel o imprimir en PDF."
			),
		),
	]
	for nombre, *_ in TARJETAS[:6]:
		bloques.append(_bloque("number_card", number_card_name=nombre, col=4))
	bloques.append(_bloque("spacer"))
	for nombre, _tipo, _f, ancho in GRAFICOS:
		bloques.append(_bloque("chart", chart_name=nombre, col=12 if ancho == "Full" else 6))
	bloques.append(_bloque("header", text='<span class="h4"><b>Reportes</b></span>'))
	bloques.append(_bloque("shortcut", shortcut_name=REPORT, col=3))
	for etiqueta, _destino in REPORTES_RELACIONADOS:
		bloques.append(_bloque("shortcut", shortcut_name=etiqueta, col=3))
	return json.dumps(bloques)


def _atajo(etiqueta, destino, doctype_ref, color="Grey"):
	return {
		"label": etiqueta,
		"type": "Report",
		"link_to": destino,
		"report_ref_doctype": doctype_ref,
		"color": color,
	}


def crear_workspace():
	atajos = [_atajo(REPORT, REPORT, "Item", "Blue")]
	for etiqueta, destino in REPORTES_RELACIONADOS:
		if frappe.db.exists("Report", destino):
			atajos.append(_atajo(etiqueta, destino, frappe.db.get_value("Report", destino, "ref_doctype")))

	valores = {
		"label": WORKSPACE,
		"title": WORKSPACE,
		"type": "Workspace",
		"module": MODULE,
		"public": 1,
		"is_hidden": 0,
		"icon": "chart",
		"sequence_id": 7.5,
		"content": _contenido_workspace(),
	}
	doc = _guardar(
		"Workspace",
		WORKSPACE,
		valores,
		tablas={
			"roles": _roles(),
			"charts": [{"chart_name": n, "label": n} for n, *_ in GRAFICOS],
			"number_cards": [{"number_card_name": n, "label": n} for n, *_ in TARJETAS],
			"shortcuts": atajos,
		},
	)
	if doc.name != WORKSPACE:
		frappe.throw(f"El workspace se creo con un nombre inesperado: {doc.name}")


# --------------------------------------------------------------------------- #
# Barra lateral e icono de escritorio del panel
# --------------------------------------------------------------------------- #
def _item_sidebar(label, link_type, link_to, tipo="Link", icon=None, child=0, route_options=None):
	item = {
		"label": label,
		"type": tipo,
		"link_type": link_type,
		"link_to": link_to,
		"icon": icon,
		"child": child,
		"collapsible": 1,
		"indent": 1 if tipo == "Section Break" else 0,
		"keep_closed": 0,
		"show_arrow": 0,
	}
	if route_options:
		item["route_options"] = json.dumps(route_options)
	return item


def crear_sidebar_e_icono():
	items = [
		_item_sidebar("Home", "Workspace", WORKSPACE, icon="home"),
		_item_sidebar("Dashboard", "Dashboard", DASHBOARD, icon="chart"),
		_item_sidebar("Balance por producto", "DocType", None, tipo="Section Break", icon="chart"),
		_item_sidebar("Resumen por producto", "Report", REPORT, child=1),
		_item_sidebar(
			"Evolución mensual total",
			"Report",
			REPORT,
			child=1,
			route_options={"vista": VISTA_TOTAL, "periodo": "Mensual"},
		),
		_item_sidebar(
			"Evolución semanal por producto",
			"Report",
			REPORT,
			child=1,
			route_options={"vista": "Evolución por producto", "periodo": "Semanal"},
		),
		_item_sidebar("Reportes relacionados", "DocType", None, tipo="Section Break", icon="stock"),
	]
	for etiqueta, destino in REPORTES_RELACIONADOS:
		if frappe.db.exists("Report", destino):
			items.append(_item_sidebar(etiqueta, "Report", destino, child=1))

	_guardar(
		"Workspace Sidebar",
		WORKSPACE,
		{
			"title": WORKSPACE,
			"header_icon": "chart",
			"module": MODULE,
			"app": APP,
			"standard": 0,
		},
		tablas={"items": items},
	)

	_guardar(
		"Desktop Icon",
		WORKSPACE,
		{
			"label": WORKSPACE,
			"icon_type": "Link",
			"link_type": "Workspace Sidebar",
			"link_to": WORKSPACE,
			"parent_icon": "ERPNext" if frappe.db.exists("Desktop Icon", "ERPNext") else None,
			"app": APP,
			"standard": 1,
			"hidden": 0,
			"idx": 2,
		},
		tablas={"roles": _roles()},
	)


# --------------------------------------------------------------------------- #
# Enlaces en los dashboards / espacios nativos de Ventas e Inventario
# --------------------------------------------------------------------------- #
def _agregar_filas_hijas(padre, doctype_padre, campo, doctype_hijo, campo_link, valores, extra=None):
	"""Inserta filas hijas sin tocar ni validar el padre (los dashboards estandar
	no se pueden guardar fuera de modo desarrollador)."""
	existentes = set(
		frappe.get_all(doctype_hijo, filters={"parent": padre, "parenttype": doctype_padre}, pluck=campo_link)
	)
	idx = (
		frappe.db.sql(
			f"select coalesce(max(idx), 0) from `tab{doctype_hijo}` where parent = %s and parenttype = %s",
			(padre, doctype_padre),
		)[0][0]
		or 0
	)
	for valor in valores:
		if valor in existentes:
			continue
		idx += 1
		fila = {
			"doctype": doctype_hijo,
			"parent": padre,
			"parenttype": doctype_padre,
			"parentfield": campo,
			"idx": idx,
			campo_link: valor,
		}
		fila.update(extra or {})
		frappe.get_doc(fila).insert(ignore_permissions=True)


def enlazar_dashboards_nativos():
	for nombre, charts, cards in (
		("Selling", CHARTS_VENTAS, CARDS_VENTAS),
		("Stock", CHARTS_STOCK, CARDS_STOCK),
	):
		if not frappe.db.exists("Dashboard", nombre):
			continue
		_agregar_filas_hijas(
			nombre, "Dashboard", "charts", "Dashboard Chart Link", "chart", charts, {"width": "Half"}
		)
		_agregar_filas_hijas(nombre, "Dashboard", "cards", "Number Card Link", "card", cards)
		frappe.clear_document_cache("Dashboard", nombre)


def enlazar_sidebars_nativos():
	"""Agrega 'Balance por Producto' y 'Panel de Balance' justo despues de 'Dashboard'."""
	for nombre in ("Selling", "Stock"):
		if not frappe.db.exists("Workspace Sidebar", nombre):
			continue
		sb = frappe.get_doc("Workspace Sidebar", nombre)
		etiquetas = {i.label for i in sb.items}
		nuevos = []
		if REPORT not in etiquetas:
			nuevos.append(_item_sidebar(REPORT, "Report", REPORT, icon="chart"))
		if PANEL_LABEL not in etiquetas:
			nuevos.append(_item_sidebar(PANEL_LABEL, "Workspace", WORKSPACE, icon="chart"))
		if not nuevos:
			continue

		posicion = next((n for n, i in enumerate(sb.items) if i.label == "Dashboard"), 1) + 1
		for nuevo in nuevos:
			sb.append("items", nuevo)
		agregados = sb.items[-len(nuevos):]
		del sb.items[-len(nuevos):]
		sb.items[posicion:posicion] = agregados
		for n, fila in enumerate(sb.items, start=1):
			fila.idx = n
		sb.flags.ignore_permissions = True
		sb.save()


def enlazar_workspaces_nativos():
	"""Agrega el atajo al reporte al inicio de los espacios Selling y Stock.

	Los atajos de tipo Report se ocultan solos a quien no tiene permiso. No se usa un atajo URL
	para el panel porque Frappe no lo filtra por permisos (la cajera lo veria)."""
	for nombre in ("Selling", "Stock"):
		if not frappe.db.exists("Workspace", nombre):
			continue
		ws = frappe.get_doc("Workspace", nombre)
		cambio = False

		# Limpieza de la version anterior, que agregaba un atajo URL "Panel de Balance"
		anteriores = [s for s in ws.shortcuts if s.label == PANEL_LABEL]
		for s in anteriores:
			ws.remove(s)
			cambio = True

		if REPORT not in {s.label for s in ws.shortcuts}:
			ws.append("shortcuts", _atajo(REPORT, REPORT, "Item", "Blue"))
			cambio = True

		bloques = json.loads(ws.content or "[]")
		limpios = [b for b in bloques if b.get("data", {}).get("shortcut_name") != PANEL_LABEL]
		if len(limpios) != len(bloques):
			cambio = True
		if not any(b.get("data", {}).get("shortcut_name") == REPORT for b in limpios):
			limpios.insert(0, _bloque("shortcut", shortcut_name=REPORT, col=3))
			cambio = True
		if not cambio:
			continue
		ws.content = json.dumps(limpios)
		ws.flags.ignore_permissions = True
		ws.save()


# --------------------------------------------------------------------------- #
# Escritorio personalizado (Lorena y Andrea tienen un layout propio)
# --------------------------------------------------------------------------- #
USUARIOS_ESCRITORIO = {
	"lorena@gmail.com": "Analisis de Ventas",
	"andrea@gmail.com": "Balance de Inventario",
}

ITEM_ESCRITORIO = {
	"label": "Balance por Producto",
	"link": "/app/balance-de-productos",
	"link_type": "External",
	"icon_type": "Link",
	"icon": "chart",
	"standard": 1,
	"name": "Balance por Producto",
	"hidden": 0,
	"restrict_removal": 0,
	"bg_color": "purple",
	"parent_icon": None,
}


def enlazar_escritorios_personalizados():
	for usuario, despues_de in USUARIOS_ESCRITORIO.items():
		if not frappe.db.exists("Desktop Layout", usuario):
			continue
		doc = frappe.get_doc("Desktop Layout", usuario)
		try:
			items = json.loads(doc.layout or "[]")
		except ValueError:
			continue
		if any(i.get("name") == ITEM_ESCRITORIO["name"] for i in items):
			continue

		ancla = next((i.get("idx") for i in items if i.get("label") == despues_de), None)
		if ancla is None:
			ancla = max([i.get("idx", 0) for i in items if i.get("idx", 0) < 99], default=0)
		for i in items:
			if ancla < i.get("idx", 0) < 99:
				i["idx"] = i["idx"] + 1
		nuevo = dict(ITEM_ESCRITORIO)
		nuevo["idx"] = ancla + 1
		items.append(nuevo)
		items.sort(key=lambda i: i.get("idx", 0))
		doc.db_set("layout", json.dumps(items), update_modified=False)
		frappe.clear_cache(user=usuario)
