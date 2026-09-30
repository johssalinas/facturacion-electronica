"""Trazabilidad de cantidades facturadas vs. pendientes por producto y dueno fiscal.

Este modulo es el unico punto donde se calcula y se registra qué cantidad de
cada linea de venta (Sales Invoice Item / POS Invoice Item) ya fue incluida en
una factura electronica Factus, sin importar si el envio fue:

 - Inmediato B2B (factura individual, consume el 100% de sus propias lineas)
 - Resumen Diario CCF (agrupado automatico al cerrar caja, consume el 100%
   de las lineas de las facturas incluidas en el cierre)
 - Manual (el usuario elige cuanto de la cantidad pendiente facturar)

El ledger es la tabla "FE Consumo Item". La cantidad pendiente de un producto
para un dueno fiscal es siempre:

    pendiente_de_una_linea = linea.qty - SUM(FE Consumo Item.qty_consumida
                                              WHERE invoice_item = linea.name)

Nunca se resta directamente de la factura de venta original: así el mismo
dato sirve para cualquier canal de envio y no se puede perder trazabilidad.
"""

import frappe
from frappe import _
from frappe.utils import flt, now_datetime


def _pending_rows_query(dueno_fiscal):
	"""Todas las lineas de venta (Sales/POS Invoice Item) de items cuyo
	Item.dueno_fiscal == dueno_fiscal, en orden FIFO (mas antiguas primero).
	Excluye devoluciones (is_return) y documentos no sometidos.
	"""
	rows = []
	for doctype in ("Sales Invoice", "POS Invoice"):
		data = frappe.db.sql(
			f"""
			SELECT
				inv.name AS invoice_name,
				%(doctype)s AS invoice_doctype,
				inv.posting_date AS posting_date,
				inv.posting_time AS posting_time,
				ii.name AS invoice_item,
				ii.item_code AS item_code,
				ii.item_name AS item_name,
				ii.qty AS qty,
				ii.net_rate AS net_rate,
				ii.uom AS uom
			FROM `tab{doctype} Item` ii
			INNER JOIN `tab{doctype}` inv ON inv.name = ii.parent
			INNER JOIN `tabItem` it ON it.name = ii.item_code
			WHERE inv.docstatus = 1
				AND IFNULL(inv.is_return, 0) = 0
				AND it.dueno_fiscal = %(dueno)s
			ORDER BY inv.posting_date ASC, inv.posting_time ASC, ii.idx ASC
			""",
			{"dueno": dueno_fiscal, "doctype": doctype},
			as_dict=True,
		)
		rows.extend(data)
	rows.sort(key=lambda r: (r.posting_date or "", r.posting_time or ""))
	return rows


def _consumido_por_linea(dueno_fiscal):
	data = frappe.get_all(
		"FE Consumo Item",
		filters={"dueno_fiscal": dueno_fiscal},
		fields=["invoice_item", "qty_consumida"],
	)
	consumo = {}
	for d in data:
		consumo[d.invoice_item] = flt(consumo.get(d.invoice_item, 0)) + flt(d.qty_consumida)
	return consumo


def get_pendientes_detalle(dueno_fiscal):
	"""Lineas de venta con cantidad pendiente > 0, en orden FIFO."""
	rows = _pending_rows_query(dueno_fiscal)
	consumo = _consumido_por_linea(dueno_fiscal)
	result = []
	for r in rows:
		consumido = consumo.get(r.invoice_item, 0)
		pendiente = flt(flt(r.qty) - flt(consumido), 4)
		if pendiente > 0.0001:
			r["qty_pendiente"] = pendiente
			result.append(r)
	return result


def get_pendientes_agrupado(dueno_fiscal):
	"""Pendientes agrupados por producto, para mostrar en la tabla de
	facturacion manual: [{item_code, item_name, uom, qty_pendiente}, ...]
	"""
	detalle = get_pendientes_detalle(dueno_fiscal)
	grouped = {}
	for r in detalle:
		g = grouped.setdefault(
			r.item_code,
			{
				"item_code": r.item_code,
				"item_name": r.item_name,
				"uom": r.uom,
				"qty_pendiente": 0.0,
			},
		)
		g["qty_pendiente"] = flt(g["qty_pendiente"] + r.qty_pendiente, 2)
	return sorted(grouped.values(), key=lambda x: (x["item_name"] or x["item_code"] or ""))


def seleccionar_lineas_para_facturar(dueno_fiscal, selecciones):
	"""Consume FIFO las lineas pendientes de cada item_code hasta cubrir la
	cantidad solicitada por el usuario.

	selecciones: dict {item_code: qty_a_facturar}

	Devuelve:
	  items_payload: lista de dicts {item_code, item_name, net_rate, uom, qty}
	                  agrupados por (item_code, net_rate), listos para pasar a
	                  _get_item_obj() de api_fe.py.
	  consumo_rows:   lista de dicts con el detalle de que linea origen se
	                  consumio y cuanto, para registrar en el ledger SOLO si
	                  el envio a Factus es exitoso.
	"""
	detalle = get_pendientes_detalle(dueno_fiscal)
	by_item = {}
	for r in detalle:
		by_item.setdefault(r.item_code, []).append(r)

	items_payload = []
	consumo_rows = []

	for item_code, qty_deseada in (selecciones or {}).items():
		qty_deseada = flt(qty_deseada, 4)
		if qty_deseada <= 0:
			continue
		rows = by_item.get(item_code, [])
		restante = qty_deseada
		rate_groups = {}
		for row in rows:
			if restante <= 0.0001:
				break
			tomar = min(flt(row.qty_pendiente), restante)
			if tomar <= 0:
				continue
			restante = flt(restante - tomar, 4)
			consumo_rows.append(
				{
					"invoice_item": row.invoice_item,
					"invoice_doctype": row.invoice_doctype,
					"invoice_name": row.invoice_name,
					"qty": tomar,
					"item_code": item_code,
					"item_name": row.item_name,
					"net_rate": row.net_rate,
					"uom": row.uom,
				}
			)
			key = flt(row.net_rate, 4)
			g = rate_groups.setdefault(
				key,
				{
					"item_code": item_code,
					"item_name": row.item_name,
					"net_rate": row.net_rate,
					"uom": row.uom,
					"qty": 0.0,
				},
			)
			g["qty"] = flt(g["qty"] + tomar, 2)
		if restante > 0.0001:
			frappe.throw(
				_("La cantidad solicitada para {0} ({1}) excede lo pendiente disponible.").format(
					item_code, qty_deseada
				)
			)
		items_payload.extend(rate_groups.values())

	return items_payload, consumo_rows


def registrar_consumo(dueno_fiscal, consumo_rows, log_name=None, tipo_operacion=None):
	"""Persiste en el ledger FE Consumo Item las lineas efectivamente
	facturadas. Debe llamarse SOLO despues de una emision exitosa a Factus
	(no importa si el estado final es 'Enviada' o 'Validada' — en ambos casos
	el documento quedo registrado en Factus y esa cantidad ya no debe volver
	a ofrecerse como pendiente).
	"""
	fecha = now_datetime()
	for row in consumo_rows or []:
		qty = flt(row.get("qty"))
		if qty <= 0:
			continue
		doc = frappe.get_doc(
			{
				"doctype": "FE Consumo Item",
				"dueno_fiscal": dueno_fiscal,
				"item_code": row.get("item_code"),
				"item_name": row.get("item_name"),
				"net_rate": row.get("net_rate"),
				"uom": row.get("uom"),
				"qty_consumida": qty,
				"invoice_doctype": row.get("invoice_doctype"),
				"invoice_name": row.get("invoice_name"),
				"invoice_item": row.get("invoice_item"),
				"tipo_operacion": tipo_operacion,
				"log_factura_electronica": log_name,
				"fecha": fecha,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()


def consumo_rows_desde_filas_reales(items):
	"""Construye consumo_rows (full qty) a partir de filas reales de child
	table (Sales Invoice Item / POS Invoice Item), para los flujos que
	facturan la linea completa (Inmediata B2B, Reintento, Manual clasico
	sobre una factura puntual). Solo procesa filas que tengan los atributos
	esperados; ignora silenciosamente cualquier otra cosa (p.ej. dicts
	sinteticos del flujo de resumen agrupado).
	"""
	rows = []
	for it in items or []:
		name = getattr(it, "name", None) or (it.get("name") if hasattr(it, "get") else None)
		parent = getattr(it, "parent", None) or (it.get("parent") if hasattr(it, "get") else None)
		parenttype = getattr(it, "parenttype", None) or (
			it.get("parenttype") if hasattr(it, "get") else None
		)
		if not (name and parent and parenttype):
			continue
		item_code = getattr(it, "item_code", None) or (it.get("item_code") if hasattr(it, "get") else None)
		item_name = getattr(it, "item_name", None) or (it.get("item_name") if hasattr(it, "get") else None)
		qty = getattr(it, "qty", None) if hasattr(it, "qty") else (it.get("qty") if hasattr(it, "get") else None)
		net_rate = getattr(it, "net_rate", None) if hasattr(it, "net_rate") else (
			it.get("net_rate") if hasattr(it, "get") else None
		)
		uom = getattr(it, "uom", None) if hasattr(it, "uom") else (it.get("uom") if hasattr(it, "get") else None)
		rows.append(
			{
				"invoice_item": name,
				"invoice_doctype": parenttype,
				"invoice_name": parent,
				"qty": qty,
				"item_code": item_code,
				"item_name": item_name,
				"net_rate": net_rate,
				"uom": uom,
			}
		)
	return rows
