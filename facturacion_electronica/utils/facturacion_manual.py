"""Facturacion electronica manual.

Permite generar una factura electronica Factus en cualquier momento, para un
dueño fiscal especifico, consolidando las ventas pendientes de facturar
(las que no fueron incluidas todavia en ninguna factura Factus, sea por el
canal inmediato B2B, el resumen automatico del cierre de caja, o una factura
manual anterior) y dejando que el usuario decida cuantas unidades de cada
producto incluir.

Flujo:
  1. get_duenos_fiscales_activos() -> lista de Dueno Fiscal activos, para el
     selector en la UI.
  2. get_pendientes(dueno_fiscal) -> tabla agrupada por producto con la
     cantidad pendiente de facturar (ventas no facturadas desde la ultima
     factura electronica emitida para ese dueño).
  3. generar_factura_manual(dueno_fiscal, selecciones) -> el usuario elige,
     por producto, cuantas unidades desea facturar (selecciones parciales
     permitidas, hasta el maximo pendiente). Se consume FIFO de las lineas de
     venta mas antiguas.
"""

import json

import frappe
from frappe import _
from frappe.utils import flt

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
	calcular_total_con_impuestos,
)
from facturacion_electronica.utils.pendientes import (
	get_pendientes_agrupado,
	registrar_consumo,
	seleccionar_lineas_para_facturar,
)
from frappe.utils import now_datetime


@frappe.whitelist()
def get_duenos_fiscales_activos():
	return frappe.get_all(
		"Dueno Fiscal",
		filters={"activo": 1},
		fields=["name", "razon_social", "nit"],
		order_by="nombre asc",
	)


@frappe.whitelist()
def get_pendientes(dueno_fiscal):
	if not dueno_fiscal:
		frappe.throw(_("Debe indicar un dueño fiscal"))
	return get_pendientes_agrupado(dueno_fiscal)


def _total_con_impuestos(items_obj):
	return calcular_total_con_impuestos(items_obj)


@frappe.whitelist()
def generar_factura_manual(dueno_fiscal, selecciones, customer=None, send_email=None):
	"""selecciones: dict o JSON string {item_code: qty_a_facturar}"""
	if not dueno_fiscal:
		frappe.throw(_("Debe indicar un dueño fiscal"))
	if isinstance(selecciones, str):
		selecciones = json.loads(selecciones)
	selecciones = {k: flt(v) for k, v in (selecciones or {}).items() if flt(v) > 0}
	if not selecciones:
		frappe.throw(_("Debe seleccionar al menos un producto con cantidad mayor a cero"))

	config = get_config()
	customer = customer or config.cliente_consumidor_final
	if not customer:
		frappe.throw(
			_(
				"No hay cliente configurado para la factura manual. Configure"
				" 'Cliente Consumidor Final' en Configuracion API FE o indique un cliente."
			)
		)

	items_payload, consumo_rows = seleccionar_lineas_para_facturar(dueno_fiscal, selecciones)
	if not items_payload:
		frappe.throw(_("No hay cantidad pendiente disponible para la selección indicada"))

	fecha_str = frappe.utils.nowdate()
	suffix = frappe.generate_hash(length=6)
	reference_code = f"MANUAL-{dueno_fiscal}-{fecha_str}-{suffix}".replace(" ", "")[:60]

	customer_obj = _get_customer_obj(customer)
	items_obj = [_get_item_obj(it, config) for it in items_payload]
	total = _total_con_impuestos(items_obj)

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
		"send_email": bool(config.enviar_email_automatico) if send_email is None else bool(send_email),
		"customer": customer_obj,
		"items": items_obj,
		"observation": f"Factura manual - {dueno_fiscal} - {fecha_str}",
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
		# Solo se registra el consumo (se "gasta" la cantidad pendiente) si
		# Factus aceptó el documento. Si algo falla antes de este punto, la
		# excepción se propaga y la cantidad sigue disponible como pendiente.
		registrar_consumo(dueno_fiscal, consumo_rows, log_name=log_name, tipo_operacion="Manual")
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
		frappe.throw(_("Error al emitir la factura manual: {0}").format(str(e)))
