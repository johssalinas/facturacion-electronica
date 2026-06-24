import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class LogFacturaElectronica(Document):
	def before_insert(self):
		if not self.fecha:
			self.fecha = now_datetime()


def crear_log(
	reference_doctype,
	reference_name,
	dueno_fiscal,
	tipo_operacion,
	reference_code=None,
	estado="Pendiente",
	payload=None,
	respuesta=None,
	cufe=None,
	qr_url=None,
	public_url=None,
	numero_factus=None,
	is_validated=0,
	validated_at=None,
	mensaje=None,
	errores=None,
):
	log = frappe.get_doc(
		{
			"doctype": "Log Factura Electronica",
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"dueno_fiscal": dueno_fiscal,
			"tipo_operacion": tipo_operacion,
			"reference_code": reference_code,
			"estado": estado,
			"fecha": now_datetime(),
			"cufe": cufe,
			"qr_url": qr_url,
			"public_url": public_url,
			"numero_factus": numero_factus,
			"is_validated": 1 if is_validated else 0,
			"validated_at": validated_at,
			"mensaje": mensaje,
		}
	)
	if payload is not None:
		log.payload_enviado = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
	if respuesta is not None:
		log.respuesta = json.dumps(respuesta, ensure_ascii=False, indent=2, default=str)
	if errores is not None:
		log.errores = json.dumps(errores, ensure_ascii=False, indent=2, default=str)
	log.flags.ignore_permissions = True
	log.insert()
	return log.name


def actualizar_log(log_name, **kwargs):
	log = frappe.get_doc("Log Factura Electronica", log_name)
	for key, value in kwargs.items():
		if key in ("payload", "respuesta", "errores"):
			setattr(
				log,
				{"payload": "payload_enviado", "respuesta": "respuesta", "errores": "errores"}[key],
				json.dumps(value, ensure_ascii=False, indent=2, default=str),
			)
		else:
			setattr(log, key, value)
	log.flags.ignore_permissions = True
	log.save()
	return log
