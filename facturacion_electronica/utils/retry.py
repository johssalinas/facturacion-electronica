import json

import frappe
from frappe.utils import now_datetime

from facturacion_electronica.utils.api_fe import FacturacionElectronicaAPI
from facturacion_electronica.facturacion_electronica.doctype.log_factura_electronica.log_factura_electronica import (
	actualizar_log,
)


def _es_rechazo(errores_raw):
	"""Determina si el ultimo error registrado es un RECHAZO real de la DIAN
	(hay que eliminar el documento y corregir) o una simple demora de
	validacion (no hay que eliminar, solo reintentar el mismo reference_code).

	Segun la documentacion oficial de Factus (manejo de errores): solo se
	debe eliminar la factura cuando el campo "errors" contiene la palabra
	"rechazo". Si la DIAN simplemente esta demorada en responder, se reintenta
	sin eliminar para no perder el consecutivo ni duplicar esfuerzo.
	"""
	if not errores_raw:
		return False
	try:
		data = json.loads(errores_raw) if isinstance(errores_raw, str) else errores_raw
	except Exception:
		data = errores_raw
	texto = json.dumps(data, ensure_ascii=False, default=str) if not isinstance(data, str) else data
	return "rechazo" in texto.lower()


def reintentar_facturas_fallidas():
	config = frappe.get_cached_doc("Configuracion API FE")
	max_intentos = int(config.reintentos_maximos or 3)
	logs = frappe.get_all("Log Factura Electronica", filters={"estado": "Error"}, pluck="name")
	for log_name in logs:
		log = frappe.get_doc("Log Factura Electronica", log_name)
		if not log.payload_enviado:
			continue
		if (log.intentos or 0) >= max_intentos:
			continue
		_reintentar_log(log, max_intentos)


def _reintentar_log(log, max_intentos):
	try:
		payload = json.loads(log.payload_enviado)
		api = FacturacionElectronicaAPI(log.dueno_fiscal)
		if _es_rechazo(log.errores):
			try:
				api.eliminar_factura(log.reference_code)
			except Exception:
				pass
		resp = api.emitir_factura(payload)
		data = resp.get("data", {}) if isinstance(resp, dict) else {}
		links = data.get("links", {}) or {}
		estado = "Validada" if data.get("is_validated") else "Enviada"
		actualizar_log(
			log.name,
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
			intentos=(log.intentos or 0) + 1,
		)
		if log.reference_doctype in ("Sales Invoice", "POS Invoice"):
			try:
				frappe.db.set_value(log.reference_doctype, log.reference_name, "estado_fe", estado)
				if data.get("is_validated") and data.get("cufe"):
					frappe.db.set_value(log.reference_doctype, log.reference_name, "cufe_fe", data.get("cufe"))
			except Exception:
				pass
	except Exception as e:
		actualizar_log(
			log.name,
			intentos=(log.intentos or 0) + 1,
			errores={"error": str(e)},
			mensaje=str(e),
		)
		frappe.log_error(title=f"Reintento FE {log.name}", message=str(e))
