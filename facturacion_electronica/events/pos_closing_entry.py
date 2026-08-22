import frappe
from frappe import _

from facturacion_electronica.utils.agrupacion import PENDIENTES, agrupar_y_enviar_ccf
from facturacion_electronica.utils.api_fe import _duenos_en_factura, enviar_factura_fe


def _invoices_en_cierre(doc):
	pairs = []
	for r in doc.pos_invoices:
		if r.pos_invoice:
			pairs.append(("POS Invoice", r.pos_invoice))
	for r in doc.sales_invoices:
		if r.sales_invoice:
			pairs.append(("Sales Invoice", r.sales_invoice))
	return pairs


def _pendientes_en_cierre(doc):
	pend = []
	for dt, name in _invoices_en_cierre(doc):
		estado = frappe.db.get_value(dt, name, "estado_fe")
		if estado in PENDIENTES:
			pend.append((dt, name))
	return pend


def before_submit(doc, method=None):
	pend = _pendientes_en_cierre(doc)
	if pend:
		frappe.throw(
			_(
				"Tiene {0} factura(s) pendiente(s) de enviar a la DIAN. Use el boton"
				" 'Enviar pendientes a DIAN' antes de cerrar caja."
			).format(frappe.bold(len(pend))),
			title=_("Facturas pendientes en DIAN"),
		)


@frappe.whitelist()
def get_pendientes_fe(name):
	doc = frappe.get_doc("POS Closing Entry", name)
	pend = _pendientes_en_cierre(doc)
	return {
		"count": len(pend),
		"invoices": [{"doctype": dt, "name": n} for dt, n in pend],
	}


@frappe.whitelist()
def enviar_pendientes_fe(name):
	doc = frappe.get_doc("POS Closing Entry", name)
	pend = _pendientes_en_cierre(doc)
	if not pend:
		return {"ok": True, "enviadas": 0, "errores": [], "message": _("No hay facturas pendientes")}
	ccf_pos = []
	enviadas = 0
	errores = []
	for dt, n in pend:
		inv = frappe.get_doc(dt, n)
		cust = frappe.get_cached_doc("Customer", inv.customer)
		if cust.get("requiere_factura_inmediata"):
			duenos = _duenos_en_factura(inv)
			if not duenos:
				frappe.db.set_value(dt, n, "estado_fe", "No Aplica", update_modified=False)
				continue
			for dueno, items in duenos.items():
				try:
					enviar_factura_fe(inv, dueno, items, tipo_operacion="Reintento")
					enviadas += 1
				except Exception as e:
					errores.append(f"{n}/{dueno}: {e}")
		elif dt == "POS Invoice":
			ccf_pos.append(n)
		else:
			duenos = _duenos_en_factura(inv)
			if not duenos:
				frappe.db.set_value(dt, n, "estado_fe", "No Aplica", update_modified=False)
				continue
			for dueno, items in duenos.items():
				try:
					enviar_factura_fe(inv, dueno, items, tipo_operacion="Manual")
					enviadas += 1
				except Exception as e:
					errores.append(f"{n}/{dueno}: {e}")
	if ccf_pos:
		fecha_str = str(doc.posting_date)
		res = agrupar_y_enviar_ccf(ccf_pos, fecha_str, ref_suffix=doc.name)
		enviadas += res.get("enviadas", 0)
		errores.extend(res.get("errores", []))
	if errores:
		return {
			"ok": False,
			"enviadas": enviadas,
			"errores": errores,
			"message": _("Algunas facturas no pudieron enviarse a la DIAN. Revise el Log."),
		}
	return {"ok": True, "enviadas": enviadas, "errores": [], "message": _("Facturas enviadas a la DIAN")}



@frappe.whitelist()
def get_mode_of_payment_map(invoice_names):
	"""Return a dict mapping invoice name -> {modo_de_pago, estado_pago}."""
	import json
	if isinstance(invoice_names, str):
		invoice_names = json.loads(invoice_names)

	if not invoice_names:
		return {}

	# Fetch payments grouped by invoice
	payments = frappe.db.sql("""
		SELECT parent, mode_of_payment, amount
		FROM `tabSales Invoice Payment`
		WHERE parent IN %(names)s AND amount > 0
		ORDER BY amount DESC
	""", {"names": invoice_names}, as_dict=True)

	mop_map = {}
	for p in payments:
		if p.parent not in mop_map:
			mop_map[p.parent] = []
		if p.mode_of_payment not in mop_map[p.parent]:
			mop_map[p.parent].append(p.mode_of_payment)

	# Fetch outstanding_amount to compute payment status
	outstanding_rows = frappe.db.sql("""
		SELECT name, grand_total, outstanding_amount
		FROM `tabSales Invoice`
		WHERE name IN %(names)s
	""", {"names": invoice_names}, as_dict=True)

	outstanding_map = {r.name: r for r in outstanding_rows}

	result = {}
	for name in invoice_names:
		mop = ", ".join(mop_map.get(name, []))
		row = outstanding_map.get(name)
		if row:
			outstanding = row.outstanding_amount or 0
			grand_total = row.grand_total or 0
			if outstanding <= 0:
				estado = "Pagada"
			elif grand_total and outstanding >= grand_total:
				estado = "Sin Pago"
			else:
				estado = "Pago Parcial"
		else:
			estado = "Pagada"
		result[name] = {"modo_de_pago": mop, "estado_pago": estado}

	return result
