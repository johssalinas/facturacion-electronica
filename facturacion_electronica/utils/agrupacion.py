import frappe
from frappe.utils import flt, now_datetime

from facturacion_electronica.facturacion_electronica.doctype.configuracion_api_fe.configuracion_api_fe import (
	get_config,
)
from facturacion_electronica.facturacion_electronica.doctype.log_factura_electronica.log_factura_electronica import (
	actualizar_log,
	crear_log,
)
from facturacion_electronica.utils.api_fe import (
	FacturacionElectronicaAPI,
	_get_customer_obj,
	_get_item_obj,
)

PENDIENTES = (None, "", "Pendiente", "Error")


def agrupar_y_enviar_ccf(pos_invoice_names, fecha_str, ref_suffix=""):
	config = get_config()
	ccf_customer = config.cliente_consumidor_final
	grupos = {}
	invoice_duenos = {}
	if not ccf_customer:
		return {"enviadas": 0, "errores": ["No hay cliente 'Consumidor Final' configurado"]}
	for name in pos_invoice_names:
		doc = frappe.get_doc("POS Invoice", name)
		if doc.docstatus != 1:
			continue
		if doc.get("estado_fe") not in PENDIENTES:
			continue
		cust = frappe.get_cached_doc("Customer", doc.customer)
		if cust.get("requiere_factura_inmediata"):
			continue
		for row in doc.items:
			item = frappe.get_cached_doc("Item", row.item_code)
			d = item.get("dueno_fiscal")
			if not d:
				continue
			invoice_duenos.setdefault(name, set()).add(d)
			key = (row.item_code, flt(row.net_rate, 4))
			grupos.setdefault(d, {})
			agg = grupos[d].get(key)
			if not agg:
				agg = {
					"item_code": row.item_code,
					"item_name": row.item_name,
					"net_rate": flt(row.net_rate, 2),
					"qty": 0.0,
				}
				grupos[d][key] = agg
			agg["qty"] = flt(agg["qty"] + flt(row.qty), 2)
	enviadas = 0
	errores = []
	exitosos = set()
	suffix = (ref_suffix or "")[-8:].replace(" ", "")
	for dueno, items_map in grupos.items():
		try:
			_emitir_resumen(dueno, fecha_str, list(items_map.values()), ccf_customer, config, suffix)
			enviadas += 1
			exitosos.add(dueno)
		except Exception as e:
			errores.append(f"{dueno}: {e}")
			frappe.log_error(title=f"Resumen CCF {dueno} {fecha_str}", message=str(e))
	for name, duenos in invoice_duenos.items():
		if duenos and duenos.issubset(exitosos):
			frappe.db.set_value("POS Invoice", name, "estado_fe", "Agrupada", update_modified=False)
	return {"enviadas": enviadas, "errores": errores}


def _emitir_resumen(dueno, fecha_str, items, ccf_customer, config, suffix=""):
	total = sum(flt(i["qty"]) * flt(i["net_rate"]) for i in items)
	if not items:
		return
	payload = _build_resumen_payload(dueno, fecha_str, items, total, ccf_customer, config, suffix)
	log_name = crear_log(
		reference_doctype="POS Invoice",
		reference_name=f"RESUMEN-{dueno}-{fecha_str}-{suffix}".replace("  ", " ").strip(),
		dueno_fiscal=dueno,
		tipo_operacion="Resumen Diario CCF",
		reference_code=payload["reference_code"],
		estado="Pendiente",
		payload=payload,
	)
	api = FacturacionElectronicaAPI(dueno)
	try:
		resp = api.emitir_factura(payload)
		data = resp.get("data", {}) if isinstance(resp, dict) else {}
		links = data.get("links", {}) or {}
		estado = "Validada" if data.get("is_validated") else "Enviada"
		actualizar_log(
			log_name,
			estado=estado,
			respuesta=resp,
			cufe=data.get("cufe"),
			qr_url=links.get("qr"),
			public_url=links.get("public_url"),
			numero_factus=data.get("number"),
			is_validated=1 if data.get("is_validated") else 0,
			validated_at=now_datetime() if data.get("is_validated") else None,
			mensaje=resp.get("message"),
			errores=data.get("errors"),
		)
	except Exception as e:
		actualizar_log(log_name, estado="Error", errores={"error": str(e)}, mensaje=str(e))
		raise


def _build_resumen_payload(dueno, fecha_str, items, total, ccf_customer, config, suffix=""):
	customer = _get_customer_obj(ccf_customer)
	items_payload = [_get_item_obj(it, config) for it in items]
	cred = frappe.get_cached_doc("Dueno Fiscal", dueno)
	ref = f"RESUMEN-{dueno}-{fecha_str}-{suffix}".replace(" ", "")
	payload = {
		"reference_code": ref[:60],
		"document": "01",
		"operation_type": "10",
		"payment_details": [
			{
				"payment_form": "1",
				"payment_method_code": "ZZZ",
				"amount": str(flt(total, 2)),
			}
		],
		"cash_rounding_amount": "0.00",
		"send_email": bool(config.enviar_email_automatico),
		"customer": customer,
		"items": items_payload,
		"observation": f"Resumen diario de ventas - {dueno} - {fecha_str}",
	}
	if cred and cred.numbering_range_id:
		payload["numbering_range_id"] = int(cred.numbering_range_id)
	return payload
