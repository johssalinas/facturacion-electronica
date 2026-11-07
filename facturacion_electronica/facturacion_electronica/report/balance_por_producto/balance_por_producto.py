# Copyright (c) 2026, Salsamentaria and contributors
# License: MIT

"""
Reporte "Balance por Producto".

Une, por producto, lo que se compro, lo que se vendio, cuanto se gano o perdio
y como evoluciona el inventario, en tres vistas:

  * Resumen por producto      -> una fila por producto en el rango de fechas.
  * Evolucion por producto    -> una fila por producto y periodo (dia/semana/mes/...).
  * Evolucion total           -> una fila por periodo con todos los productos juntos.

Fuentes (todo en pesos sin IVA):
  * Ventas   : Sales Invoice Item (base_net_amount, stock_qty)
  * Compras  : Purchase Invoice Item (base_net_amount, stock_qty)
  * Kardex   : Stock Ledger Entry (saldos, costo de ventas del sistema, ajustes)

Base de costo (filtro "base_costo"):
  * "Costo de compra (promedio)": costo de lo vendido = cantidad vendida x promedio
    ponderado de TODAS las compras del producto hasta la fecha de la venta.
  * "Kardex del sistema (FIFO)": costo de lo vendido tal como lo valoro ERPNext.
    Es el valor contable, pero depende de que el inventario inicial y los
    ajustes hayan sido cargados con su costo correcto.
"""

import datetime
from bisect import bisect_right
from collections import defaultdict

import frappe
from frappe.utils import add_days, cint, date_diff, flt, getdate, nowdate

VISTA_RESUMEN = "Resumen por producto"
VISTA_EVOL_PRODUCTO = "Evolución por producto"
VISTA_EVOL_TOTAL = "Evolución total"
VISTAS = [VISTA_RESUMEN, VISTA_EVOL_PRODUCTO, VISTA_EVOL_TOTAL]

BASE_COMPRA = "Costo de compra (promedio)"
BASE_KARDEX = "Kardex del sistema (FIFO)"
BASES = [BASE_COMPRA, BASE_KARDEX]

PERIODOS = ["Diario", "Semanal", "Mensual", "Trimestral", "Anual"]

RESULTADOS = ["Todos", "Con ganancia", "Con pérdida", "Sin costo confiable"]

FORMATO_COMPLETO = "Completo"
FORMATO_COMPACTO = "Compacto (para imprimir o PDF)"
FORMATOS = [FORMATO_COMPLETO, FORMATO_COMPACTO]
# Columnas que se conservan en el formato compacto (resumen y evolucion por producto)
COMPACTO = {
	"periodo", "item_code", "item_name", "uom", "estado",
	"compra_qty", "compra_monto", "compra_prom",
	"venta_qty", "venta_monto", "venta_prom",
	"cogs", "utilidad", "margen",
	"inv_final_qty", "inv_final_valor",
	# evolucion total
	"var_ventas", "balance_caja", "n_productos",
}

# Graficos
G_TOP_UTILIDAD = "Top 15 por utilidad"
G_PERDIDAS = "15 con menor utilidad"
G_VENTAS_COMPRAS = "Top 15: compras vs ventas"
G_MARGEN = "Top 15: margen %"
G_DINERO = "Dinero: ventas, compras y utilidad"
G_PRECIOS = "Precios: venta vs costo (un producto)"
G_INVENTARIO = "Inventario: valor al cierre"
GRAFICOS_RESUMEN = [G_TOP_UTILIDAD, G_PERDIDAS, G_VENTAS_COMPRAS, G_MARGEN]
GRAFICOS_EVOLUCION = [G_DINERO, G_PRECIOS, G_INVENTARIO]
GRAFICOS = GRAFICOS_RESUMEN + GRAFICOS_EVOLUCION

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
UOM_GRAMOS = {"gram", "gramo", "gramos", "g", "gr"}

EPS = 0.0001

# Un margen fuera de este rango casi siempre indica un error de datos (unidad de medida o precio mal digitado)
MARGEN_MIN = -100.0
MARGEN_MAX = 99.0

COLOR_VENTAS = "#2490EF"
COLOR_COMPRAS = "#F5A623"
COLOR_COSTO = "#A0A4A8"
COLOR_UTILIDAD = "#29CD42"


# --------------------------------------------------------------------------- #
# Punto de entrada del reporte
# --------------------------------------------------------------------------- #
def execute(filters=None):
	f = normalizar_filtros(filters)
	analisis = Analisis(f)

	if f.vista == VISTA_EVOL_TOTAL:
		columns = columnas_evolucion_total()
		data, chart = analisis.evolucion_total()
	elif f.vista == VISTA_EVOL_PRODUCTO:
		columns = columnas_evolucion_producto()
		data, chart = analisis.evolucion_producto()
	else:
		columns = columnas_resumen()
		data, chart = analisis.resumen()

	if data:
		data.append(fila_total(f.vista, data))

	if f.formato == FORMATO_COMPACTO:
		columns = [c for c in columns if c["fieldname"] in COMPACTO]

	return columns, data, analisis.mensaje(), chart, analisis.tarjetas()


def fila_total(vista, filas):
	"""Fila TOTAL con solo las sumas que tienen sentido (no se suman precios, porcentajes
	ni cantidades de unidades distintas). El margen se pondera por ventas.

	Frappe puede sumar columnas por su cuenta (`add_total_row`), pero ese calculo ignora
	`disable_total` al exportar a Excel y sumaria precios promedio."""

	def suma(campo):
		return sum(r.get(campo) or 0 for r in filas)

	if vista == VISTA_RESUMEN:
		con_utilidad = [r for r in filas if r["utilidad"] is not None]
		utilidad = sum(r["utilidad"] for r in con_utilidad)
		base = sum(r["venta_monto"] - r["venta_sin_costo"] for r in con_utilidad)
		return {
			"es_total": 1,
			"item_name": f"TOTAL ({len(filas)} productos)",
			"compra_monto": suma("compra_monto"),
			"venta_monto": suma("venta_monto"),
			"venta_sin_costo": suma("venta_sin_costo"),
			"cogs": suma("cogs"),
			"utilidad": utilidad,
			"margen": pct(utilidad, base),
			"balance_caja": suma("balance_caja"),
			"inv_final_valor": suma("inv_final_valor"),
			"participacion": 100.0,
		}

	utilidad = sum(r["_base"] - r["_cogs"] for r in filas) if vista == VISTA_EVOL_PRODUCTO else suma("utilidad")
	base = (
		sum(r["_base"] for r in filas)
		if vista == VISTA_EVOL_PRODUCTO
		else suma("venta_monto") - suma("venta_sin_costo")
	)
	total = {
		"es_total": 1,
		"periodo": "TOTAL",
		"compra_monto": suma("compra_monto"),
		"venta_monto": suma("venta_monto"),
		"cogs": suma("cogs"),
		"utilidad": utilidad,
		"margen": pct(utilidad, base),
	}
	if vista == VISTA_EVOL_TOTAL:
		total["venta_sin_costo"] = suma("venta_sin_costo")
		total["balance_caja"] = suma("balance_caja")
		total["inv_final_valor"] = filas[-1]["inv_final_valor"]
	return total


def normalizar_filtros(filters):
	f = frappe._dict(frappe.parse_json(filters) or {})

	f.company = f.company or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	if not f.company:
		frappe.throw("Seleccione una empresa.")

	f.to_date = getdate(f.to_date or nowdate())
	f.from_date = getdate(f.from_date or datetime.date(f.to_date.year, 1, 1))
	if f.from_date > f.to_date:
		frappe.throw("La fecha inicial no puede ser mayor que la fecha final.")

	f.vista = f.vista if f.vista in VISTAS else VISTA_RESUMEN
	f.periodo = f.periodo if f.periodo in PERIODOS else "Mensual"
	f.base_costo = f.base_costo if f.base_costo in BASES else BASE_COMPRA
	f.resultado = f.resultado if f.resultado in RESULTADOS else "Todos"
	f.solo_vendidos = 1 if f.solo_vendidos is None else cint(f.solo_vendidos)
	f.excluir_sospechosos = 1 if f.excluir_sospechosos is None else cint(f.excluir_sospechosos)
	f.formato = f.formato if f.formato in FORMATOS else FORMATO_COMPLETO
	grafico = f.grafico if f.vista == VISTA_RESUMEN else (f.grafico_evol or f.grafico)
	f.grafico = grafico if grafico in GRAFICOS else None
	return f


# --------------------------------------------------------------------------- #
# Columnas
# --------------------------------------------------------------------------- #
def _col(label, fieldname, fieldtype="Data", width=110, options=None, total=False, precision=None):
	c = {"label": label, "fieldname": fieldname, "fieldtype": fieldtype, "width": width}
	if options:
		c["options"] = options
	if precision is not None:
		c["precision"] = precision
	if not total:
		c["disable_total"] = 1
	return c


def columnas_resumen():
	return [
		_col("Producto", "item_code", "Link", 105, "Item"),
		_col("Nombre", "item_name", "Data", 230),
		_col("Grupo", "item_group", "Link", 120, "Item Group"),
		_col("UM", "uom", "Data", 50),
		_col("Resultado", "estado", "Data", 90),
		_col("Alertas", "alerta", "Data", 220),
		_col("ABC", "abc", "Data", 45),
		# Compras
		_col("Cant. comprada", "compra_qty", "Float", 105, precision=2),
		_col("Compras (sin IVA)", "compra_monto", "Currency", 130, total=True),
		_col("Costo prom. compra", "compra_prom", "Currency", 115),
		_col("Último costo compra", "compra_ultimo", "Currency", 115),
		# Ventas
		_col("Cant. vendida", "venta_qty", "Float", 100, precision=2),
		_col("Ventas (sin IVA)", "venta_monto", "Currency", 130, total=True),
		_col("Ventas sin costo confiable", "venta_sin_costo", "Currency", 130, total=True),
		_col("Precio prom. venta", "venta_prom", "Currency", 115),
		_col("Último precio venta", "venta_ultimo", "Currency", 115),
		# Resultado
		_col("Costo de lo vendido", "cogs", "Currency", 130, total=True),
		_col("Utilidad bruta", "utilidad", "Currency", 125, total=True),
		_col("Margen %", "margen", "Percent", 85),
		_col("Utilidad por unidad", "utilidad_unit", "Currency", 115),
		_col("Ventas − Compras", "balance_caja", "Currency", 130, total=True),
		# Inventario
		_col("Inventario inicial", "inv_inicial_qty", "Float", 100, precision=2),
		_col("Ajustes / inv. inicial", "ajuste_qty", "Float", 105, precision=2),
		_col("Inventario final", "inv_final_qty", "Float", 100, precision=2),
		_col("Valor inventario final", "inv_final_valor", "Currency", 130, total=True),
		_col("Días de cobertura", "cobertura", "Float", 90, precision=0),
		_col("Participación ventas %", "participacion", "Percent", 100),
	]


def columnas_evolucion_producto():
	return [
		_col("Período", "periodo", "Data", 125),
		_col("Producto", "item_code", "Link", 105, "Item"),
		_col("Nombre", "item_name", "Data", 230),
		_col("UM", "uom", "Data", 50),
		_col("Cant. comprada", "compra_qty", "Float", 105, precision=2),
		_col("Compras (sin IVA)", "compra_monto", "Currency", 130, total=True),
		_col("Costo prom. compra", "compra_prom", "Currency", 115),
		_col("Var. costo %", "var_costo", "Percent", 85),
		_col("Cant. vendida", "venta_qty", "Float", 100, precision=2),
		_col("Ventas (sin IVA)", "venta_monto", "Currency", 130, total=True),
		_col("Precio prom. venta", "venta_prom", "Currency", 115),
		_col("Var. precio %", "var_precio", "Percent", 85),
		_col("Costo de lo vendido", "cogs", "Currency", 130, total=True),
		_col("Utilidad bruta", "utilidad", "Currency", 125, total=True),
		_col("Margen %", "margen", "Percent", 85),
		_col("Ajustes / inv. inicial", "ajuste_qty", "Float", 105, precision=2),
		_col("Inventario al cierre", "inv_final_qty", "Float", 105, precision=2),
		_col("Valor inventario al cierre", "inv_final_valor", "Currency", 140),
	]


def columnas_evolucion_total():
	return [
		_col("Período", "periodo", "Data", 130),
		_col("Compras (sin IVA)", "compra_monto", "Currency", 140, total=True),
		_col("Ventas (sin IVA)", "venta_monto", "Currency", 140, total=True),
		_col("Var. ventas %", "var_ventas", "Percent", 90),
		_col("Ventas sin costo confiable", "venta_sin_costo", "Currency", 140, total=True),
		_col("Costo de lo vendido", "cogs", "Currency", 140, total=True),
		_col("Utilidad bruta", "utilidad", "Currency", 135, total=True),
		_col("Margen %", "margen", "Percent", 85),
		_col("Ventas − Compras", "balance_caja", "Currency", 140, total=True),
		_col("Productos vendidos", "n_productos", "Int", 100),
		_col("Valor inventario al cierre", "inv_final_valor", "Currency", 150),
	]


# --------------------------------------------------------------------------- #
# Utilidades de periodos
# --------------------------------------------------------------------------- #
def periodo_clave(fecha, periodo):
	"""Devuelve (inicio, etiqueta) del periodo al que pertenece `fecha`."""
	if periodo == "Diario":
		return fecha, fecha.strftime("%Y-%m-%d")
	if periodo == "Semanal":
		inicio = fecha - datetime.timedelta(days=fecha.weekday())
		iso = inicio.isocalendar()
		return inicio, f"{iso[0]}-S{iso[1]:02d} ({inicio.day:02d} {MESES[inicio.month - 1].lower()})"
	if periodo == "Mensual":
		inicio = fecha.replace(day=1)
		return inicio, f"{fecha.year}-{fecha.month:02d} {MESES[fecha.month - 1]}"
	if periodo == "Trimestral":
		trimestre = (fecha.month - 1) // 3 + 1
		return datetime.date(fecha.year, (trimestre - 1) * 3 + 1, 1), f"{fecha.year}-T{trimestre}"
	return datetime.date(fecha.year, 1, 1), str(fecha.year)


def factor_uom(uom):
	"""Los productos que se manejan en gramos se muestran en kilos."""
	if (uom or "").strip().lower() in UOM_GRAMOS:
		return 1000.0, "Kg"
	return 1.0, uom or ""


def pct(numerador, denominador):
	return (numerador / denominador * 100.0) if abs(denominador) > EPS else None


def variacion(actual, anterior):
	if actual is None or anterior is None or abs(anterior) < EPS:
		return None
	return (actual - anterior) / abs(anterior) * 100.0


def acortar(texto, n=26):
	texto = (texto or "").strip()
	return texto if len(texto) <= n else texto[: n - 1].rstrip() + "…"


# --------------------------------------------------------------------------- #
# Costo de compra (promedio ponderado acumulado)
# --------------------------------------------------------------------------- #
class CostoCompra:
	def __init__(self, compras_por_item):
		self.series = {}
		for item, movs in compras_por_item.items():
			fechas, acum_q, acum_m = [], [], []
			q_total = m_total = 0.0
			primero = None
			for fecha, q, m in sorted(movs):
				q_total += q
				m_total += m
				fechas.append(fecha)
				acum_q.append(q_total)
				acum_m.append(m_total)
				if primero is None and q > EPS and m > 0:
					primero = m / q
			self.series[item] = (fechas, acum_q, acum_m, primero)

	def en(self, item, fecha):
		"""(costo_unitario, es_estimado). `es_estimado` indica que aun no habia
		compras a esa fecha y se uso el costo de la primera compra posterior."""
		serie = self.series.get(item)
		if not serie:
			return None, False
		fechas, acum_q, acum_m, primero = serie
		i = bisect_right(fechas, fecha) - 1
		if i >= 0 and acum_q[i] > EPS and acum_m[i] > 0:
			return acum_m[i] / acum_q[i], False
		if primero is not None:
			return primero, True
		return None, False


def _rec():
	return {"sq": 0.0, "sa": 0.0, "bq": 0.0, "ba": 0.0, "ck": 0.0, "aq": 0.0, "av": 0.0, "mq": 0.0, "mv": 0.0}


# --------------------------------------------------------------------------- #
# Analisis
# --------------------------------------------------------------------------- #
class Analisis:
	def __init__(self, f):
		self.f = f
		self.moneda = frappe.get_cached_value("Company", f.company, "default_currency")
		self.params = {"company": f.company, "from_date": f.from_date, "to_date": f.to_date}
		self.cond_item = self._condiciones_item()

		self.datos = defaultdict(lambda: defaultdict(_rec))  # item -> fecha -> rec
		self.compras_hist = defaultdict(list)  # item -> [(fecha, qty, monto)]
		self.apertura = {}  # item -> (qty, valor)
		self.excluido = {"monto": 0.0, "lineas": 0}
		self._cargar()

		self.info = self._info_items()
		self.costo = CostoCompra(self.compras_hist)
		self.primera_venta = self._primera_venta()
		self.dias_efectivos = max(1, date_diff(f.to_date, max(f.from_date, self.primera_venta or f.from_date)) + 1)

		self._resumen_items = None  # cache: item -> bucket de resumen
		self.sospechosos = set()  # productos con costo que parece un error de datos
		self.forzar_sc = set()  # productos cuyas ventas se tratan como sin costo confiable

	# ---- carga de datos ------------------------------------------------- #
	def _condiciones_item(self):
		f = self.f
		cond = ""
		if f.get("item_code"):
			cond += " AND i.name = %(item_code)s"
			self.params["item_code"] = f.item_code
		if f.get("item_group"):
			lft, rgt = frappe.db.get_value("Item Group", f.item_group, ["lft", "rgt"]) or (0, 0)
			grupos = frappe.get_all("Item Group", filters={"lft": [">=", lft], "rgt": ["<=", rgt]}, pluck="name")
			cond += " AND i.item_group IN %(grupos)s"
			self.params["grupos"] = tuple(grupos or [f.item_group])
		if f.get("warehouse"):
			lft, rgt = frappe.db.get_value("Warehouse", f.warehouse, ["lft", "rgt"]) or (0, 0)
			almacenes = frappe.get_all("Warehouse", filters={"lft": [">=", lft], "rgt": ["<=", rgt]}, pluck="name")
			self.params["almacenes"] = tuple(almacenes or [f.warehouse])
		return cond

	def _filtro_almacen(self, alias):
		return f" AND {alias}.warehouse IN %(almacenes)s" if self.f.get("warehouse") else ""

	def _cargar(self):
		p = self.params
		c = self.cond_item

		# Ventas netas (sin IVA, ya descontados descuentos y devoluciones)
		for r in frappe.db.sql(
			f"""
			SELECT sii.item_code, si.posting_date AS fecha,
				SUM(sii.stock_qty) AS qty, SUM(sii.base_net_amount) AS monto
			FROM `tabSales Invoice Item` sii
			JOIN `tabSales Invoice` si ON si.name = sii.parent
			JOIN `tabItem` i ON i.name = sii.item_code
			WHERE si.docstatus = 1 AND si.company = %(company)s
				AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
				AND i.is_stock_item = 1 {c} {self._filtro_almacen("sii")}
			GROUP BY sii.item_code, si.posting_date
			""",
			p,
			as_dict=True,
		):
			rec = self.datos[r.item_code][r.fecha]
			rec["sq"] += flt(r.qty)
			rec["sa"] += flt(r.monto)

		# Ventas excluidas (productos no inventariables, p.ej. migracion SIIGO)
		if not self.f.get("item_code") and not self.f.get("item_group"):
			ex = frappe.db.sql(
				"""
				SELECT COALESCE(SUM(sii.base_net_amount), 0) AS monto, COUNT(*) AS lineas
				FROM `tabSales Invoice Item` sii
				JOIN `tabSales Invoice` si ON si.name = sii.parent
				LEFT JOIN `tabItem` i ON i.name = sii.item_code
				WHERE si.docstatus = 1 AND si.company = %(company)s
					AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
					AND COALESCE(i.is_stock_item, 0) = 0
				""",
				p,
				as_dict=True,
			)[0]
			self.excluido = {"monto": flt(ex.monto), "lineas": cint(ex.lineas)}

		# Compras netas (todo el historial hasta la fecha final: se necesita para el costo promedio)
		for r in frappe.db.sql(
			f"""
			SELECT pii.item_code, pi.posting_date AS fecha,
				SUM(pii.stock_qty) AS qty, SUM(pii.base_net_amount) AS monto
			FROM `tabPurchase Invoice Item` pii
			JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
			JOIN `tabItem` i ON i.name = pii.item_code
			WHERE pi.docstatus = 1 AND pi.company = %(company)s
				AND pi.posting_date <= %(to_date)s
				AND i.is_stock_item = 1 {c} {self._filtro_almacen("pii")}
			GROUP BY pii.item_code, pi.posting_date
			""",
			p,
			as_dict=True,
		):
			self.compras_hist[r.item_code].append((r.fecha, flt(r.qty), flt(r.monto)))
			if r.fecha >= self.f.from_date:
				rec = self.datos[r.item_code][r.fecha]
				rec["bq"] += flt(r.qty)
				rec["ba"] += flt(r.monto)

		# Kardex dentro del rango: costo de ventas del sistema, ajustes y movimiento total
		for r in frappe.db.sql(
			f"""
			SELECT sle.item_code, sle.posting_date AS fecha,
				CASE
					WHEN sle.voucher_type IN ('Sales Invoice', 'POS Invoice', 'Delivery Note') THEN 'venta'
					WHEN sle.voucher_type IN ('Purchase Invoice', 'Purchase Receipt') THEN 'compra'
					ELSE 'ajuste'
				END AS tipo,
				SUM(sle.actual_qty) AS qty, SUM(sle.stock_value_difference) AS valor
			FROM `tabStock Ledger Entry` sle
			JOIN `tabItem` i ON i.name = sle.item_code
			WHERE sle.is_cancelled = 0 AND sle.company = %(company)s
				AND sle.posting_date BETWEEN %(from_date)s AND %(to_date)s
				AND i.is_stock_item = 1 {c} {self._filtro_almacen("sle")}
			GROUP BY sle.item_code, sle.posting_date, tipo
			""",
			p,
			as_dict=True,
		):
			rec = self.datos[r.item_code][r.fecha]
			rec["mq"] += flt(r.qty)
			rec["mv"] += flt(r.valor)
			if r.tipo == "venta":
				rec["ck"] += -flt(r.valor)
			elif r.tipo == "ajuste":
				rec["aq"] += flt(r.qty)
				rec["av"] += flt(r.valor)

		# Saldo antes del rango
		for r in frappe.db.sql(
			f"""
			SELECT sle.item_code, SUM(sle.actual_qty) AS qty, SUM(sle.stock_value_difference) AS valor
			FROM `tabStock Ledger Entry` sle
			JOIN `tabItem` i ON i.name = sle.item_code
			WHERE sle.is_cancelled = 0 AND sle.company = %(company)s
				AND sle.posting_date < %(from_date)s
				AND i.is_stock_item = 1 {c} {self._filtro_almacen("sle")}
			GROUP BY sle.item_code
			""",
			p,
			as_dict=True,
		):
			self.apertura[r.item_code] = (flt(r.qty), flt(r.valor))

	def _info_items(self):
		f = self.f
		con_ventas = {
			item
			for item, dias in self.datos.items()
			if any(abs(r["sq"]) > EPS or abs(r["sa"]) > EPS for r in dias.values())
		}
		if f.solo_vendidos:
			items = con_ventas
		else:
			items = set()
			for item, dias in self.datos.items():
				if any(abs(r["sq"]) > EPS or abs(r["bq"]) > EPS or abs(r["mq"]) > EPS for r in dias.values()):
					items.add(item)
			for item, (q, _v) in self.apertura.items():
				fin_q = q + sum(r["mq"] for r in self.datos.get(item, {}).values())
				if abs(fin_q) > EPS:
					items.add(item)
		self.items_con_ventas = con_ventas
		if not items:
			return {}

		info = {}
		for r in frappe.get_all(
			"Item",
			filters={"name": ["in", list(items)]},
			fields=["name", "item_name", "item_group", "stock_uom"],
		):
			factor, um = factor_uom(r.stock_uom)
			info[r.name] = frappe._dict(
				nombre=r.item_name, grupo=r.item_group, uom=um, factor=factor, uom_stock=r.stock_uom
			)
		return info

	def _primera_venta(self):
		fechas = [fecha for dias in self.datos.values() for fecha, r in dias.items() if abs(r["sq"]) > EPS]
		return min(fechas) if fechas else None

	# ---- motor: series por producto ------------------------------------- #
	def _valor_inventario(self, item, qty, valor_kardex, fecha):
		"""Valor del inventario segun la base de costo elegida."""
		if item in self.forzar_sc:
			return 0.0  # costo que parece un error de datos: no se valora
		if self.f.base_costo == BASE_KARDEX:
			return valor_kardex
		if qty <= EPS:
			return 0.0
		costo, _est = self.costo.en(item, fecha)
		if costo is None:
			return max(valor_kardex, 0.0)
		return qty * costo

	def _serie(self, item, clave_fn, fecha_cierre=None):
		"""Agrupa los movimientos diarios de un producto en periodos.

		`fecha_cierre` fuerza la fecha con la que se valora el inventario final
		(el resumen lo valora a la fecha final del reporte)."""
		recs = self.datos.get(item, {})
		abre_q, abre_v = self.apertura.get(item, (0.0, 0.0))
		run_q, run_v = abre_q, abre_v
		buckets, actual = [], None

		def cerrar(b):
			b["cierre_q"] = run_q
			b["cierre_v"] = self._valor_inventario(item, run_q, run_v, fecha_cierre or b["fin"])

		for fecha in sorted(recs):
			r = recs[fecha]
			clave = clave_fn(fecha)
			if actual is None or actual["clave"] != clave:
				if actual:
					cerrar(actual)
				actual = {
					"clave": clave,
					"inicio_q": run_q,
					"sq": 0.0, "sa": 0.0, "bq": 0.0, "ba": 0.0, "cogs": 0.0, "ck": 0.0, "aq": 0.0,
					"sa_sc": 0.0, "sq_sc": 0.0, "p_ult": None, "c_ult": None, "estimado": False, "sin_costo": False,
					"fin": fecha,
				}
				buckets.append(actual)
			b = actual
			b["fin"] = fecha
			b["sq"] += r["sq"]
			b["sa"] += r["sa"]
			b["bq"] += r["bq"]
			b["ba"] += r["ba"]
			b["ck"] += r["ck"]
			b["aq"] += r["aq"]
			if r["sq"] > EPS:
				b["p_ult"] = r["sa"] / r["sq"]
			if r["bq"] > EPS:
				b["c_ult"] = r["ba"] / r["bq"]

			if item in self.forzar_sc:
				# Costo que parece un error de datos: las ventas no entran en utilidad ni margen
				b["sa_sc"] += r["sa"]
				b["sq_sc"] += r["sq"]
			elif self.f.base_costo == BASE_KARDEX:
				b["cogs"] += r["ck"]
			elif abs(r["sq"]) > EPS:
				costo, estimado = self.costo.en(item, fecha)
				if costo is None:
					# Sin ninguna compra registrada: el costo es desconocido, no cero.
					# Estas ventas se excluyen del calculo de utilidad y margen.
					b["sa_sc"] += r["sa"]
					b["sq_sc"] += r["sq"]
					b["sin_costo"] = True
				else:
					b["cogs"] += r["sq"] * costo
					b["estimado"] = b["estimado"] or estimado

			run_q += r["mq"]
			run_v += r["mv"]

		if actual:
			cerrar(actual)
		return buckets, (abre_q, abre_v)

	def _bucket_resumen(self):
		"""Un bucket por producto (todo el rango). Se calcula una sola vez."""
		if self._resumen_items is None:
			self._resumen_items = {item: self._bucket_item(item) for item in self.info}

			# Segunda pasada: los productos con costo sospechoso se tratan como "sin costo confiable"
			for item, b in self._resumen_items.items():
				base, utilidad = self._resultado(b)
				if utilidad is not None and base > EPS:
					margen = utilidad / base * 100.0
					if margen < MARGEN_MIN or margen > MARGEN_MAX:
						self.sospechosos.add(item)
			if self.f.excluir_sospechosos and self.sospechosos:
				self.forzar_sc = set(self.sospechosos)
				for item in self.forzar_sc:
					self._resumen_items[item] = self._bucket_item(item)
		return self._resumen_items

	def _bucket_item(self, item):
		buckets, (abre_q, abre_v) = self._serie(item, lambda _f: 0, fecha_cierre=self.f.to_date)
		if buckets:
			b = buckets[0]
		else:  # sin movimientos en el rango: solo saldo inicial
			b = {
				"clave": 0, "inicio_q": abre_q, "sq": 0.0, "sa": 0.0, "bq": 0.0, "ba": 0.0,
				"cogs": 0.0, "ck": 0.0, "aq": 0.0, "sa_sc": 0.0, "sq_sc": 0.0, "p_ult": None, "c_ult": None,
				"estimado": False, "sin_costo": False, "fin": self.f.to_date,
				"cierre_q": abre_q,
				"cierre_v": self._valor_inventario(item, abre_q, abre_v, self.f.to_date),
			}
		b["abre_q"], b["abre_v"] = abre_q, abre_v
		return b

	@staticmethod
	def _resultado(b):
		"""(venta con costo conocido, utilidad). La utilidad es None cuando hay ventas
		pero ninguna tiene costo conocido."""
		base = b["sa"] - b["sa_sc"]
		if abs(b["sa"]) > EPS and abs(base) <= EPS:
			return base, None
		return base, base - b["cogs"]

	def _items_filtrados(self):
		"""Items que cumplen el filtro de resultado (ganancia/perdida/sin costo)."""
		buckets = self._bucket_resumen()
		res = self.f.resultado
		if res == "Todos":
			return list(buckets)
		salida = []
		for item, b in buckets.items():
			_base, utilidad = self._resultado(b)
			if res == "Sin costo confiable":
				ok = utilidad is None
			elif utilidad is None:
				ok = False
			else:
				ok = (res == "Con ganancia" and utilidad > EPS) or (res == "Con pérdida" and utilidad < -EPS)
			if ok:
				salida.append(item)
		return salida

	# ---- vistas ---------------------------------------------------------- #
	def resumen(self):
		buckets = self._bucket_resumen()
		filas = []
		for item in self._items_filtrados():
			b = buckets[item]
			info = self.info[item]
			k = info.factor
			base, utilidad = self._resultado(b)
			vendida = b["sq"]
			q_conocida = vendida - b["sq_sc"]
			compra_prom = (b["ba"] / b["bq"] * k) if b["bq"] > EPS else None
			venta_prom = (b["sa"] / vendida * k) if vendida > EPS else None
			cobertura = None
			if vendida > EPS and b["cierre_q"] > EPS:
				cobertura = b["cierre_q"] / (vendida / self.dias_efectivos)

			if abs(b["sa"]) <= EPS and abs(vendida) <= EPS:
				estado = "Sin ventas"
			elif utilidad is None:
				estado = "Costo sospechoso" if item in self.sospechosos else "Sin costo"
			elif utilidad > EPS:
				estado = "Ganancia"
			elif utilidad < -EPS:
				estado = "Pérdida"
			else:
				estado = "Equilibrio"

			filas.append(
				{
					"item_code": item,
					"item_name": info.nombre,
					"item_group": info.grupo,
					"uom": info.uom,
					"estado": estado,
					"alerta": self._alertas(b, item),
					"abc": "",
					"compra_qty": b["bq"] / k,
					"compra_monto": b["ba"],
					"compra_prom": compra_prom,
					"compra_ultimo": b["c_ult"] * k if b["c_ult"] is not None else None,
					"venta_qty": vendida / k,
					"venta_monto": b["sa"],
					"venta_sin_costo": b["sa_sc"],
					"venta_prom": venta_prom,
					"venta_ultimo": b["p_ult"] * k if b["p_ult"] is not None else None,
					"cogs": b["cogs"] if utilidad is not None or abs(b["sa"]) <= EPS else None,
					"utilidad": utilidad,
					"margen": pct(utilidad, base) if utilidad is not None else None,
					"utilidad_unit": (utilidad / q_conocida * k) if (utilidad is not None and q_conocida > EPS) else None,
					"balance_caja": b["sa"] - b["ba"],
					"inv_inicial_qty": b["abre_q"] / k,
					"ajuste_qty": b["aq"] / k,
					"inv_final_qty": b["cierre_q"] / k,
					"inv_final_valor": b["cierre_v"],
					"cobertura": cobertura,
					"participacion": None,
				}
			)

		total_ventas = sum(r["venta_monto"] for r in filas if r["venta_monto"] > 0)
		filas.sort(key=lambda r: r["venta_monto"], reverse=True)
		acumulado = 0.0
		for r in filas:
			if r["venta_monto"] > 0 and total_ventas > 0:
				r["participacion"] = r["venta_monto"] / total_ventas * 100.0
				acumulado += r["venta_monto"]
				previo = (acumulado - r["venta_monto"]) / total_ventas
				r["abc"] = "A" if previo < 0.80 else ("B" if previo < 0.95 else "C")
		return filas, self._grafico_resumen(filas)

	def _diagnostico(self, b, item):
		"""Banderas de calidad de datos y de negocio para un producto (bucket de resumen)."""
		base, utilidad = self._resultado(b)
		sospechoso = item in self.sospechosos
		d = {
			"stock_negativo": b["cierre_q"] < -EPS,
			"sin_costo": utilidad is None and not sospechoso and b["sa"] > EPS,
			"parcial": utilidad is not None and b["sa_sc"] > EPS,
			"estimado": self.f.base_costo == BASE_COMPRA and bool(b["estimado"]),
			"kardex_dudoso": self.f.base_costo == BASE_KARDEX and b["sa"] > EPS and (b["ck"] <= EPS or b["ck"] > 3 * b["sa"]),
			"sospechoso": sospechoso,
			"bajo_costo": utilidad is not None and utilidad < -EPS,
		}
		return d

	def _alertas(self, b, item):
		d = self._diagnostico(b, item)
		alertas = []
		if d["stock_negativo"]:
			alertas.append("Stock negativo")
		if d["sin_costo"]:
			alertas.append("Sin costo de compra registrado")
		elif d["parcial"]:
			alertas.append("Parte de las ventas sin costo de compra")
		if d["sospechoso"]:
			alertas.append("Costo sospechoso: revise unidad de medida o precio de compra")
		if d["kardex_dudoso"]:
			alertas.append("Costo del kardex dudoso")
		if d["estimado"] and not d["sospechoso"]:
			alertas.append("Costo estimado con compra posterior")
		if d["bajo_costo"] and not d["sospechoso"]:
			alertas.append("Vendido bajo el costo")
		return " · ".join(alertas)

	# ---- evolucion por producto ----------------------------------------- #
	def evolucion_producto(self):
		periodo = self.f.periodo
		clave_fn = lambda fecha: periodo_clave(fecha, periodo)  # noqa: E731
		self._bucket_resumen()
		items = self._items_filtrados()
		orden = sorted(items, key=lambda i: self._resumen_items[i]["sa"], reverse=True)

		filas = []
		for item in orden:
			info = self.info[item]
			k = info.factor
			buckets, _ap = self._serie(item, clave_fn)
			prev_precio = prev_costo = None
			for b in buckets:
				inicio, etiqueta = b["clave"]
				venta_prom = (b["sa"] / b["sq"] * k) if b["sq"] > EPS else None
				compra_prom = (b["ba"] / b["bq"] * k) if b["bq"] > EPS else None
				base, utilidad = self._resultado(b)
				filas.append(
					{
						"periodo": etiqueta,
						"_inicio": inicio,
						"_base": base,
						"_cogs": b["cogs"],
						"item_code": item,
						"item_name": info.nombre,
						"uom": info.uom,
						"compra_qty": b["bq"] / k,
						"compra_monto": b["ba"],
						"compra_prom": compra_prom,
						"var_costo": variacion(compra_prom, prev_costo),
						"venta_qty": b["sq"] / k,
						"venta_monto": b["sa"],
						"venta_prom": venta_prom,
						"var_precio": variacion(venta_prom, prev_precio),
						"cogs": b["cogs"] if utilidad is not None or abs(b["sa"]) <= EPS else None,
						"utilidad": utilidad,
						"margen": pct(utilidad, base) if utilidad is not None else None,
						"ajuste_qty": b["aq"] / k,
						"inv_final_qty": b["cierre_q"] / k,
						"inv_final_valor": b["cierre_v"],
					}
				)
				if venta_prom is not None:
					prev_precio = venta_prom
				if compra_prom is not None:
					prev_costo = compra_prom

		return filas, self._grafico_evolucion_producto(filas, orden)

	# ---- evolucion total -------------------------------------------------- #
	def evolucion_total(self):
		periodo = self.f.periodo
		clave_fn = lambda fecha: periodo_clave(fecha, periodo)  # noqa: E731
		self._bucket_resumen()
		items = self._items_filtrados()

		totales = {}  # clave -> acumulado
		cierres = defaultdict(dict)  # clave -> {item: valor inventario al cierre}
		for item in items:
			buckets, _apertura = self._serie(item, clave_fn)
			for b in buckets:
				t = totales.setdefault(
					b["clave"], {"ba": 0.0, "sa": 0.0, "sc": 0.0, "cogs": 0.0, "productos": set()}
				)
				t["ba"] += b["ba"]
				t["sa"] += b["sa"]
				t["sc"] += b["sa_sc"]
				t["cogs"] += b["cogs"]
				if abs(b["sq"]) > EPS:
					t["productos"].add(item)
				cierres[b["clave"]][item] = b["cierre_v"]

		# Valor de inventario con arrastre: un producto sin movimiento conserva su ultimo valor
		valor_actual = {}
		for item in items:
			abre_q, abre_v = self.apertura.get(item, (0.0, 0.0))
			dia_previo = add_days(self.f.from_date, -1)
			valor_actual[item] = self._valor_inventario(item, abre_q, abre_v, dia_previo)

		filas, anterior = [], None
		for clave in sorted(totales):
			inicio, etiqueta = clave
			for item, valor in cierres[clave].items():
				valor_actual[item] = valor
			t = totales[clave]
			base = t["sa"] - t["sc"]
			utilidad = base - t["cogs"]
			filas.append(
				{
					"periodo": etiqueta,
					"_inicio": inicio,
					"compra_monto": t["ba"],
					"venta_monto": t["sa"],
					"var_ventas": variacion(t["sa"], anterior),
					"venta_sin_costo": t["sc"],
					"cogs": t["cogs"],
					"utilidad": utilidad,
					"margen": pct(utilidad, base),
					"balance_caja": t["sa"] - t["ba"],
					"n_productos": len(t["productos"]),
					"inv_final_valor": sum(valor_actual.values()),
				}
			)
			anterior = t["sa"]
		return filas, self._grafico_evolucion_total(filas)

	# ---- graficos --------------------------------------------------------- #
	def _chart(self, labels, datasets, tipo="bar", colores=None, fieldtype="Currency"):
		return {
			"data": {"labels": labels, "datasets": datasets},
			"type": tipo,
			"colors": colores or [COLOR_VENTAS, COLOR_COSTO, COLOR_UTILIDAD],
			"fieldtype": fieldtype,
			"options": self.moneda if fieldtype == "Currency" else None,
			"axisOptions": {"xIsSeries": 0, "shortenYAxisNumbers": 1},
			"barOptions": {"stacked": 0, "spaceRatio": 0.35},
			"height": 300,
		}

	def _grafico_resumen(self, filas):
		if not filas:
			return None
		g = self.f.grafico if self.f.grafico in GRAFICOS_RESUMEN else G_TOP_UTILIDAD

		con_utilidad = [r for r in filas if r["utilidad"] is not None]
		if g == G_PERDIDAS:
			sel = sorted(con_utilidad, key=lambda r: r["utilidad"])[:15]
		elif g == G_MARGEN:
			sel = sorted(
				[r for r in con_utilidad if r["margen"] is not None], key=lambda r: r["venta_monto"], reverse=True
			)[:15]
		elif g == G_VENTAS_COMPRAS:
			sel = sorted(filas, key=lambda r: r["venta_monto"], reverse=True)[:15]
		else:
			sel = sorted(con_utilidad, key=lambda r: r["utilidad"], reverse=True)[:15]

		if not sel:
			return None
		labels = [acortar(r["item_name"]) for r in sel]
		if g == G_VENTAS_COMPRAS:
			return self._chart(
				labels,
				[
					{"name": "Ventas", "values": [round(r["venta_monto"]) for r in sel]},
					{"name": "Compras", "values": [round(r["compra_monto"]) for r in sel]},
					{"name": "Utilidad bruta", "values": [round(r["utilidad"] or 0) for r in sel]},
				],
				colores=[COLOR_VENTAS, COLOR_COMPRAS, COLOR_UTILIDAD],
			)
		if g == G_MARGEN:
			return self._chart(
				labels,
				[{"name": "Margen %", "values": [round(r["margen"] or 0, 1) for r in sel]}],
				colores=[COLOR_UTILIDAD],
				fieldtype="Percent",
			)
		return self._chart(
			labels,
			[
				{"name": "Ventas", "values": [round(r["venta_monto"]) for r in sel]},
				{"name": "Costo de lo vendido", "values": [round(r["cogs"] or 0) for r in sel]},
				{"name": "Utilidad bruta", "values": [round(r["utilidad"] or 0) for r in sel]},
			],
		)

	def _agrupar_periodos(self, filas):
		por_periodo = {}
		for r in filas:
			p = por_periodo.setdefault(
				r["_inicio"], {"periodo": r["periodo"], "ventas": 0.0, "compras": 0.0, "utilidad": 0.0}
			)
			p["ventas"] += r["venta_monto"]
			p["compras"] += r["compra_monto"]
			p["utilidad"] += r["_base"] - r["_cogs"]
		return [por_periodo[k] for k in sorted(por_periodo)]

	def _grafico_evolucion_producto(self, filas, orden):
		if not filas:
			return None
		g = self.f.grafico if self.f.grafico in GRAFICOS_EVOLUCION else G_DINERO
		un_producto = len(orden) == 1

		if g == G_PRECIOS and un_producto:
			filas_o = sorted(filas, key=lambda r: r["_inicio"])
			return self._chart(
				[r["periodo"] for r in filas_o],
				[
					{"name": "Precio prom. venta", "values": [round(r["venta_prom"] or 0, 2) for r in filas_o]},
					{"name": "Costo prom. compra", "values": [round(r["compra_prom"] or 0, 2) for r in filas_o]},
				],
				tipo="line",
				colores=[COLOR_VENTAS, COLOR_COMPRAS],
			)
		if g == G_INVENTARIO and un_producto:
			filas_o = sorted(filas, key=lambda r: r["_inicio"])
			return self._chart(
				[r["periodo"] for r in filas_o],
				[{"name": "Valor del inventario al cierre", "values": [round(r["inv_final_valor"]) for r in filas_o]}],
				tipo="line",
				colores=[COLOR_COMPRAS],
			)

		grupos = self._agrupar_periodos(filas)
		return self._chart(
			[p["periodo"] for p in grupos],
			[
				{"name": "Ventas", "values": [round(p["ventas"]) for p in grupos]},
				{"name": "Compras", "values": [round(p["compras"]) for p in grupos]},
				{"name": "Utilidad bruta", "values": [round(p["utilidad"]) for p in grupos]},
			],
			colores=[COLOR_VENTAS, COLOR_COMPRAS, COLOR_UTILIDAD],
		)

	def _grafico_evolucion_total(self, filas):
		if not filas:
			return None
		g = self.f.grafico if self.f.grafico in GRAFICOS_EVOLUCION else G_DINERO
		labels = [r["periodo"] for r in filas]
		if g == G_INVENTARIO:
			return self._chart(
				labels,
				[{"name": "Valor del inventario al cierre", "values": [round(r["inv_final_valor"]) for r in filas]}],
				tipo="line",
				colores=[COLOR_COMPRAS],
			)
		return self._chart(
			labels,
			[
				{"name": "Ventas", "values": [round(r["venta_monto"]) for r in filas]},
				{"name": "Compras", "values": [round(r["compra_monto"]) for r in filas]},
				{"name": "Utilidad bruta", "values": [round(r["utilidad"]) for r in filas]},
			],
			colores=[COLOR_VENTAS, COLOR_COMPRAS, COLOR_UTILIDAD],
		)

	# ---- totales, tarjetas y mensajes ---------------------------------------- #
	def totales(self):
		"""Totales del rango para los productos que muestra el reporte."""
		buckets = self._bucket_resumen()
		items = self._items_filtrados()
		t = {
			"ventas": 0.0, "compras": 0.0, "cogs": 0.0, "inventario": 0.0, "sin_costo_monto": 0.0,
			"ganando": 0, "perdiendo": 0, "sin_costo": 0, "alertas": 0, "productos": len(items),
			"sospechosos": 0, "sospechosos_monto": 0.0,
		}
		utilidad_total = base_total = 0.0
		for item in items:
			b = buckets[item]
			base, utilidad = self._resultado(b)
			t["ventas"] += b["sa"]
			t["compras"] += b["ba"]
			t["cogs"] += b["cogs"]
			t["inventario"] += b["cierre_v"]
			t["sin_costo_monto"] += b["sa_sc"]
			if utilidad is None:
				t["sin_costo"] += 1
			else:
				utilidad_total += utilidad
				base_total += base
				if utilidad > EPS:
					t["ganando"] += 1
				elif utilidad < -EPS:
					t["perdiendo"] += 1
			d = self._diagnostico(b, item)
			if d["stock_negativo"] or d["sin_costo"] or d["sospechoso"] or d["kardex_dudoso"]:
				t["alertas"] += 1
			if d["sospechoso"]:
				t["sospechosos"] += 1
				t["sospechosos_monto"] += b["sa"]
		t["utilidad"] = utilidad_total
		t["margen"] = pct(utilidad_total, base_total)
		return t

	def tarjetas(self):
		if not self.info:
			return []
		t = self.totales()
		moneda = self.moneda
		return [
			{"value": t["ventas"], "label": "Ventas (sin IVA)", "datatype": "Currency", "currency": moneda, "indicator": "Blue"},
			{"value": t["compras"], "label": "Compras (sin IVA)", "datatype": "Currency", "currency": moneda, "indicator": "Orange"},
			{"value": t["cogs"], "label": "Costo de lo vendido", "datatype": "Currency", "currency": moneda, "indicator": "Gray"},
			{
				"value": t["utilidad"], "label": "Utilidad bruta", "datatype": "Currency", "currency": moneda,
				"indicator": "Green" if t["utilidad"] >= 0 else "Red",
			},
			{
				"value": t["margen"] or 0, "label": "Margen bruto", "datatype": "Percent",
				"indicator": "Green" if (t["margen"] or 0) >= 0 else "Red",
			},
			{"value": t["sin_costo_monto"], "label": "Ventas sin costo confiable", "datatype": "Currency", "currency": moneda, "indicator": "Yellow"},
			{"value": t["inventario"], "label": "Valor del inventario", "datatype": "Currency", "currency": moneda, "indicator": "Purple"},
			{"value": t["ganando"], "label": "Productos con ganancia", "datatype": "Int", "indicator": "Green"},
			{"value": t["perdiendo"], "label": "Productos con pérdida", "datatype": "Int", "indicator": "Red"},
		]

	def mensaje(self):
		f = self.f
		moneda = self.moneda
		avisos = []

		def dinero(valor):
			return frappe.format_value(valor, {"fieldtype": "Currency", "options": moneda})

		if f.base_costo == BASE_COMPRA:
			avisos.append(
				"<b>Base de costo: compras.</b> El costo de lo vendido es la cantidad vendida por el "
				"promedio ponderado de todas las compras del producto hasta la fecha de cada venta. "
				"Si un producto no tiene ninguna compra registrada, su costo es desconocido y no se calcula utilidad."
			)
		else:
			avisos.append(
				"<b>Base de costo: kardex del sistema (FIFO).</b> Es el valor contable. Solo es confiable si el "
				"inventario inicial y los ajustes se cargaron con su costo real."
			)
		if self.excluido["lineas"]:
			avisos.append(
				f"Excluidas {self.excluido['lineas']} líneas de venta por {dinero(self.excluido['monto'])} "
				"de productos no inventariables (por ejemplo, ventas migradas de SIIGO sin detalle de producto)."
			)
		if self.info:
			t = self.totales()
			sin_costo_real = t["sin_costo_monto"] - (t["sospechosos_monto"] if f.excluir_sospechosos else 0)
			if f.base_costo == BASE_COMPRA and sin_costo_real > 1:
				avisos.append(
					f"<b>{dinero(sin_costo_real)} en ventas no tienen costo de compra conocido</b> "
					"(productos sin ninguna compra registrada). No entran en la utilidad ni en el margen."
				)
			if t["sospechosos"]:
				if f.excluir_sospechosos:
					avisos.append(
						f"<b>{t['sospechosos']} productos tienen un costo que parece un error de datos</b> "
						f"(ventas por {dinero(t['sospechosos_monto'])}, margen fuera de {MARGEN_MIN:.0f}% a {MARGEN_MAX:.0f}%). "
						"Se excluyeron de la utilidad, el margen y el valor del inventario. "
						"Desmarque «Excluir costos sospechosos» para verlos."
					)
				else:
					avisos.append(
						f"<b>{t['sospechosos']} productos tienen un costo que parece un error de datos</b> "
						f"(ventas por {dinero(t['sospechosos_monto'])}). Están incluidos y distorsionan la utilidad total."
					)
			if t["alertas"]:
				avisos.append(
					f"{t['alertas']} productos tienen alertas (stock negativo, sin costo o costo dudoso). "
					"Revise la columna «Alertas» antes de decidir sobre ellos."
				)
		elif f.solo_vendidos:
			avisos.append("No hay productos vendidos con estos filtros.")
		return "<br>".join(avisos)


# --------------------------------------------------------------------------- #
# API para tarjetas numericas del dashboard (Number Card tipo Custom)
# --------------------------------------------------------------------------- #


def _rango_fechas(rango):
	hoy = getdate(nowdate())
	if rango == "Hoy":
		return hoy, hoy
	if rango == "Mes anterior":
		fin = hoy.replace(day=1) - datetime.timedelta(days=1)
		return fin.replace(day=1), fin
	if rango == "Últimos 30 días":
		return hoy - datetime.timedelta(days=29), hoy
	if rango == "Año actual":
		return datetime.date(hoy.year, 1, 1), hoy
	if rango == "Todo el historial":
		return datetime.date(2000, 1, 1), hoy
	return hoy.replace(day=1), hoy


@frappe.whitelist()
def tarjeta(filters=None):
	"""Valor para una Number Card. filters: {"kpi": ..., "rango": ..., "base_costo": ...}"""
	if not frappe.has_permission("Item", "read") or not frappe.get_doc("Report", "Balance por Producto").is_permitted():
		frappe.throw("No tiene permiso para ver el Balance por Producto.", frappe.PermissionError)

	args = frappe._dict(frappe.parse_json(filters) if isinstance(filters, str) else (filters or {}))
	if isinstance(filters, list):  # formato de filtros de documento: no aplica
		args = frappe._dict()

	desde, hasta = _rango_fechas(args.rango)
	f = normalizar_filtros(
		{
			"from_date": desde,
			"to_date": hasta,
			"base_costo": args.base_costo,
			"solo_vendidos": 1,
		}
	)

	clave = f"balance_producto_tarjeta:{f.company}:{f.from_date}:{f.to_date}:{f.base_costo}"
	t = frappe.cache.get_value(clave)
	if not t:
		t = Analisis(f).totales()
		frappe.cache.set_value(clave, t, expires_in_sec=300)

	kpi = args.kpi or "ventas"
	valor = {
		"ventas": t["ventas"],
		"compras": t["compras"],
		"utilidad": t["utilidad"],
		"margen": t["margen"] or 0,
		"inventario": t["inventario"],
		"perdiendo": t["perdiendo"],
		"alertas": t["alertas"],
		"sin_costo": t["sin_costo_monto"],
	}.get(kpi, 0)
	tipo = {"margen": "Percent", "perdiendo": "Int", "alertas": "Int"}.get(kpi, "Currency")

	return {
		"value": valor,
		"fieldtype": tipo,
		"route": ["query-report", "Balance por Producto"],
		"route_options": {
			"from_date": str(f.from_date),
			"to_date": str(f.to_date),
			"base_costo": f.base_costo,
			"resultado": "Con pérdida" if kpi == "perdiendo" else "Todos",
		},
	}
