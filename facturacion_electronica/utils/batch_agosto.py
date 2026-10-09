"""Generación batch de facturas consolidadas de agosto 2026 para testing sandbox"""
import frappe
import json
from frappe.utils import flt, getdate
from facturacion_electronica.facturacion_electronica.doctype.configuracion_api_fe.configuracion_api_fe import get_config
from facturacion_electronica.facturacion_electronica.doctype.log_factura_electronica.log_factura_electronica import (
	actualizar_log,
	crear_log,
)
from facturacion_electronica.utils.api_fe import (
	FacturacionElectronicaAPI,
	_get_customer_obj,
	_get_item_obj,
	calcular_total_con_impuestos,
)
from frappe.utils import now_datetime


def get_ventas_por_dia_agosto():
	"""Agrupa las ventas de agosto con IVA 19% o 5% por día y producto"""
	month_start = "2026-08-01"
	month_end = "2026-08-31"
	
	# Query para obtener items de facturas con IVA
	sql = """
		SELECT 
			si.posting_date,
			sii.item_code,
			sii.item_name,
			sii.uom,
			SUM(sii.qty) as qty,
			sii.rate as net_rate
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		INNER JOIN `tabSales Taxes and Charges` stc ON stc.parent = si.name AND stc.parenttype='Sales Invoice'
		WHERE si.posting_date >= %s AND si.posting_date <= %s 
		AND si.docstatus = 1
		AND IFNULL(si.is_return,0) = 0
		AND stc.account_head LIKE '%%ventas por pagar%%'
		AND stc.rate IN (19, 5)
		GROUP BY si.posting_date, sii.item_code, sii.rate
		ORDER BY si.posting_date, sii.item_code
	"""
	
	rows = frappe.db.sql(sql, (month_start, month_end), as_dict=True)
	
	# Agrupar por día
	by_day = {}
	for row in rows:
		fecha = str(row["posting_date"])
		by_day.setdefault(fecha, [])
		by_day[fecha].append({
			"item_code": row["item_code"],
			"item_name": row["item_name"],
			"qty": flt(row["qty"]),
			"net_rate": flt(row["net_rate"]),
			"uom": row["uom"],
		})
	
	return by_day


@frappe.whitelist()
def generar_facturas_agosto_sandbox(dueno_fiscal="Lorena", limite=None, dry_run=False):
	"""
	Genera facturas consolidadas de agosto en sandbox, una por día.
	
	Args:
		dueno_fiscal: Dueño fiscal a usar
		limite: Número máximo de facturas a generar (None = todas)
		dry_run: Si es True, solo muestra el plan sin emitir
	"""
	config = get_config()
	customer = config.cliente_consumidor_final
	
	if not customer:
		frappe.throw("Configure 'Cliente Consumidor Final' en Configuracion API FE")
	
	ventas_por_dia = get_ventas_por_dia_agosto()
	dias_ordenados = sorted(ventas_por_dia.keys())
	
	if limite:
		dias_ordenados = dias_ordenados[:int(limite)]
	
	resultados = []
	
	for idx, fecha in enumerate(dias_ordenados, 1):
		items = ventas_por_dia[fecha]
		
		if dry_run:
			total_items = sum(flt(i["qty"]) for i in items)
			resultados.append({
				"fecha": fecha,
				"items_count": len(items),
				"qty_total": total_items,
				"status": "dry_run",
			})
			continue
		
		# Emitir factura para este día
		try:
			result = _emitir_factura_consolidada(
				dueno_fiscal=dueno_fiscal,
				fecha=fecha,
				items=items,
				customer=customer,
				config=config,
			)
			resultados.append({
				"fecha": fecha,
				"items_count": len(items),
				"status": "exitosa" if result.get("ok") else "error",
				"log": result.get("log"),
				"numero_factus": result.get("numero_factus"),
				"cufe": result.get("cufe"),
				"error": result.get("error"),
			})
			frappe.db.commit()
			
		except Exception as e:
			resultados.append({
				"fecha": fecha,
				"items_count": len(items),
				"status": "error",
				"error": str(e),
			})
			frappe.log_error(
				title=f"Error batch agosto {fecha}",
				message=str(e),
			)
	
	return {
		"total_dias": len(dias_ordenados),
		"exitosas": len([r for r in resultados if r.get("status") == "exitosa"]),
		"errores": len([r for r in resultados if r.get("status") == "error"]),
		"resultados": resultados,
	}


def _emitir_factura_consolidada(dueno_fiscal, fecha, items, customer, config):
	"""Emite una factura consolidada para un día específico"""
	
	# Construir reference_code con la fecha real
	fecha_obj = getdate(fecha)
	suffix = frappe.generate_hash(length=6)
	reference_code = f"AGO-{dueno_fiscal}-{fecha_obj.strftime('%Y%m%d')}-{suffix}"[:60]
	
	customer_obj = _get_customer_obj(customer)
	items_obj = [_get_item_obj(it, config) for it in items]
	total = calcular_total_con_impuestos(items_obj)
	
	cred = frappe.get_cached_doc("Dueno Fiscal", dueno_fiscal)
	payload = {
		"reference_code": reference_code,
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
		"send_email": False,  # No enviar emails en sandbox
		"customer": customer_obj,
		"items": items_obj,
		"observation": f"Consolidado ventas día {fecha} - Agosto 2026 (Sandbox Test)",
	}
	
	if cred and cred.numbering_range_id:
		payload["numbering_range_id"] = int(cred.numbering_range_id)
	
	log_name = crear_log(
		reference_doctype="Dueno Fiscal",
		reference_name=dueno_fiscal,
		dueno_fiscal=dueno_fiscal,
		tipo_operacion="Manual",
		reference_code=payload["reference_code"],
		estado="Pendiente",
		payload=payload,
	)
	
	api = FacturacionElectronicaAPI(dueno_fiscal)
	
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
		
		return {
			"ok": True,
			"estado": estado,
			"log": log_name,
			"cufe": data.get("cufe"),
			"numero_factus": data.get("number"),
			"public_url": links.get("public_url"),
		}
		
	except Exception as e:
		actualizar_log(log_name, estado="Error", errores={"error": str(e)}, mensaje=str(e))
		return {
			"ok": False,
			"error": str(e),
			"log": log_name,
		}
