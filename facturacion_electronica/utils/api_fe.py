import json
from datetime import timedelta

import frappe
import requests
from frappe import _
from frappe.utils import flt, now_datetime, cstr, getdate, get_datetime

from facturacion_electronica.facturacion_electronica.doctype.configuracion_api_fe.configuracion_api_fe import (
	get_config,
	get_timeout,
	get_url_base,
)
from facturacion_electronica.facturacion_electronica.doctype.dueno_fiscal.dueno_fiscal import (
	get_credenciales,
)
from facturacion_electronica.facturacion_electronica.doctype.log_factura_electronica.log_factura_electronica import (
	actualizar_log,
	crear_log,
)

MODO_PAGO_MAP = {
	"efectivo": "10",
	"cash": "10",
	"transferencia": "47",
	"nequi": "47",
	"daviplata": "47",
	"pse": "47",
	"banco": "47",
	"tarjeta de credito": "48",
	"tarjeta credito": "48",
	"credito": "48",
	"tarjeta de debito": "49",
	"tarjeta debito": "49",
	"debito": "49",
	"cheque": "20",
	"consignacion": "42",
}


class FacturacionElectronicaAPI:
	def __init__(self, dueno_fiscal):
		self.dueno = dueno_fiscal
		self.cred = get_credenciales(dueno_fiscal)
		self.base_url = get_url_base().rstrip("/")
		self.timeout = get_timeout()

	def autenticar(self):
		cached = self._get_cached_token()
		if cached and cached.get("expires") and now_datetime() < get_datetime(cached["expires"]):
			return cached.get("access_token")
		if cached and cached.get("refresh_token"):
			try:
				return self._refresh(cached["refresh_token"])
			except Exception:
				frappe.cache().hdel("factus_token", self.dueno)
		return self._password_auth()

	def _get_cached_token(self):
		raw = frappe.cache().hget("factus_token", self.dueno)
		if not raw:
			return None
		try:
			return json.loads(raw)
		except Exception:
			return None

	def _password_auth(self):
		data = {
			"grant_type": "password",
			"client_id": self.cred["client_id"],
			"client_secret": self.cred["client_secret"],
			"username": self.cred["username"],
			"password": self.cred["password"],
		}
		resp = requests.post(
			f"{self.base_url}/oauth/token",
			data=data,
			headers={"Accept": "application/json"},
			timeout=self.timeout,
		)
		if resp.status_code != 200:
			frappe.log_error(
				title=f"Factus auth error {self.dueno}",
				message=resp.text,
			)
			return None
		body = resp.json()
		self._cache_token(body)
		return body.get("access_token")

	def _refresh(self, refresh_token):
		data = {
			"grant_type": "refresh_token",
			"client_id": self.cred["client_id"],
			"client_secret": self.cred["client_secret"],
			"refresh_token": refresh_token,
		}
		resp = requests.post(
			f"{self.base_url}/oauth/token",
			data=data,
			headers={"Accept": "application/json"},
			timeout=self.timeout,
		)
		if resp.status_code != 200:
			return self._password_auth()
		body = resp.json()
		self._cache_token(body)
		return body.get("access_token")

	def _cache_token(self, body):
		expires_in = int(body.get("expires_in") or 3600)
		expires = (now_datetime() + timedelta(seconds=max(expires_in - 60, 60))).isoformat()
		frappe.cache().hset(
			"factus_token",
			self.dueno,
			json.dumps(
				{
					"access_token": body.get("access_token"),
					"refresh_token": body.get("refresh_token"),
					"expires": expires,
				}
			),
		)

	def _headers(self):
		token = self.autenticar()
		if not token:
			frappe.throw(_("No se pudo autenticar con Factus para {0}").format(self.dueno))
		return {
			"Authorization": f"Bearer {token}",
			"Content-Type": "application/json",
			"Accept": "application/json",
		}

	def emitir_factura(self, payload):
		url = f"{self.base_url}/v2/bills/validate"
		resp = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
		if resp.status_code in (200, 201):
			return resp.json()
		if resp.status_code == 409:
			self.eliminar_factura(payload.get("reference_code"))
			resp = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
			if resp.status_code in (200, 201):
				return resp.json()
		try:
			body = resp.json()
		except Exception:
			body = {"raw": resp.text}
		frappe.log_error(
			title=f"Factus emitir error {self.dueno} {payload.get('reference_code')}",
			message=json.dumps(body, ensure_ascii=False, indent=2, default=str),
		)
		frappe.throw(
			_("Error al emitir factura en Factus: {0}").format(
				body.get("message") or resp.text[:500]
			)
		)

	def descargar_pdf(self, number):
		url = f"{self.base_url}/v2/bills/{number}/download-pdf"
		resp = requests.get(url, headers=self._headers(), timeout=self.timeout)
		if resp.status_code != 200:
			frappe.throw(_("No se pudo descargar el PDF de Factus"))
		return resp.json()

	def eliminar_factura(self, reference_code):
		url = f"{self.base_url}/v2/bills/destroy/reference/{reference_code}"
		resp = requests.delete(url, headers=self._headers(), timeout=self.timeout)
		return resp.status_code in (200, 204)


def build_reference_code(doc, dueno, tipo):
	prefix = "RESUMEN" if tipo == "Resumen Diario CCF" else "FE"
	base = f"{prefix}-{doc.name}-{dueno}".replace(" ", "")
	if len(base) > 60:
		base = base[:60]
	return base


def _get_customer_address(cust):
	addr_name = cust.get("customer_primary_address")
	if not addr_name:
		rows = frappe.get_all(
			"Dynamic Link",
			filters={"link_doctype": "Customer", "link_name": cust.name, "parenttype": "Address"},
			pluck="parent",
			limit=1,
		)
		addr_name = rows[0] if rows else None
	if not addr_name:
		return {}
	a = frappe.get_cached_doc("Address", addr_name)
	addr = " ".join([x for x in [a.address_line1, a.address_line2] if x]).strip()
	return {"address": addr, "phone": a.phone or "", "email": a.email_id or ""}


def _get_customer_obj(customer):
	cust = frappe.get_cached_doc("Customer", customer)
	is_company = cust.customer_type == "Company"
	id_doc = cstr(cust.get("fe_identification_document_code")) or ("31" if is_company else "13")
	identification = cstr(cust.tax_id or "").replace("-", "").strip()
	if not identification:
		identification = "22222222222" if not is_company else cust.name
	obj = {
		"identification_document_code": id_doc,
		"identification": identification,
		"legal_organization_code": "1" if is_company else "2",
		"tribute_code": cstr(cust.get("fe_tribute_code")) or "ZZ",
	}
	if is_company:
		obj["company"] = cust.customer_name
		obj["trade_name"] = cust.customer_name
	else:
		obj["names"] = cust.customer_name
	if cust.get("fe_dv"):
		obj["dv"] = cstr(cust.get("fe_dv"))
	email = cust.email_id or ""
	phone = cust.phone or ""
	addr = _get_customer_address(cust)
	if addr:
		if not email:
			email = addr.get("email", "")
		if not phone:
			phone = addr.get("phone", "")
		if addr.get("address"):
			obj["address"] = addr["address"]
	if email:
		obj["email"] = email
	if phone:
		obj["phone"] = phone
	muni = cstr(cust.get("fe_municipality_code"))
	if muni:
		obj["municipality_code"] = muni
	return obj


def _get_metodo_pago(mode_of_payment):
	if not mode_of_payment:
		return "ZZZ"
	key = mode_of_payment.lower().strip()
	if key in MODO_PAGO_MAP:
		return MODO_PAGO_MAP[key]
	for k, v in MODO_PAGO_MAP.items():
		if k in key or key in k:
			return v
	return "ZZZ"


def _get_payment_details(doc):
	details = []
	payments = doc.get("payments") or []
	for p in payments:
		amount = flt(p.amount, 2)
		if amount <= 0:
			continue
		details.append(
			{
				"payment_form": "1",
				"payment_method_code": _get_metodo_pago(p.mode_of_payment),
				"amount": str(amount),
			}
		)
	if not details:
		is_credit = flt(doc.get("outstanding_amount") or 0) > 0.5 and not doc.get("is_pos")
		form = "2" if is_credit else "1"
		entry = {
			"payment_form": form,
			"payment_method_code": "ZZZ",
			"amount": str(flt(doc.grand_total or doc.base_grand_total or 0, 2)),
		}
		if form == "2" and doc.get("due_date"):
			entry["due_date"] = cstr(getdate(doc.due_date))
		details.append(entry)
	return details


def _get_item_taxes(item, config):
	taxes = []
	for row in (item.get("taxes") or []):
		template_name = row.get("item_tax_template") if hasattr(row, "get") else getattr(row, "item_tax_template", None)
		if not template_name:
			continue
		try:
			template = frappe.get_cached_doc("Item Tax Template", template_name)
		except Exception:
			continue
		for tr in (template.taxes or []):
			if not tr.tax_type:
				continue
			acc = frappe.get_cached_doc("Account", tr.tax_type)
			code = cstr(acc.get("fe_tax_code"))
			if not code:
				continue
			rate = flt(tr.tax_rate if tr.tax_rate is not None else 0, 2)
			tax = {"code": code, "rate": str(rate)}
			if acc.get("fe_is_excluded"):
				tax["is_excluded"] = True
				tax["rate"] = "0.00"
			taxes.append(tax)
	if not taxes:
		code = config.tax_code_default or "01"
		rate = config.tax_rate_default if config.tax_rate_default is not None else 19
		tax = {"code": code, "rate": str(flt(rate, 2))}
		if config.tax_excluido_default:
			tax["is_excluded"] = True
			tax["rate"] = "0.00"
		taxes.append(tax)
	return taxes


def _get_item_obj(row, config):
	item_code = row.get("item_code") if hasattr(row, "get") else getattr(row, "item_code", None)
	item = frappe.get_cached_doc("Item", item_code)
	net_rate = row.get("net_rate") if hasattr(row, "get") else getattr(row, "net_rate", None)
	rate = row.get("rate") if hasattr(row, "get") else getattr(row, "rate", None)
	price = flt(net_rate if net_rate is not None else rate, 2)
	qty = row.get("qty") if hasattr(row, "get") else getattr(row, "qty", 0)
	item_name = row.get("item_name") if hasattr(row, "get") else getattr(row, "item_name", None)
	return {
		"code_reference": item_code or "SN",
		"name": item_name or item.item_name,
		"quantity": str(flt(qty, 2)),
		"discount_rate": "0.00",
		"price": str(price),
		"unit_measure_code": cstr(item.get("fe_unit_measure_code")) or config.unidad_medida_default or "94",
		"standard_code": cstr(item.get("fe_standard_code")) or config.standard_code_default or "999",
		"taxes": _get_item_taxes(item, config),
	}


def _construir_payload(doc, dueno, items, tipo_operacion, config, send_email=None):
	customer = _get_customer_obj(doc.customer)
	payment_details = _get_payment_details(doc)
	items_payload = [_get_item_obj(it, config) for it in items]
	payload = {
		"reference_code": build_reference_code(doc, dueno, tipo_operacion),
		"document": "01",
		"operation_type": "10",
		"numbering_range_id": int(get_credenciales(dueno)["numbering_range_id"] or 0) or None,
		"payment_details": payment_details,
		"cash_rounding_amount": "0.00",
		"customer": customer,
		"items": items_payload,
	}
	if payload["numbering_range_id"] is None:
		payload.pop("numbering_range_id")
	if send_email is None:
		send_email = bool(config.enviar_email_automatico)
	payload["send_email"] = send_email
	if tipo_operacion == "Resumen Diario CCF":
		payload["observation"] = f"Resumen diario de ventas - {dueno}"
	return payload


def enviar_factura_fe(doc, dueno, items, tipo_operacion="Manual", send_email=None):
	config = get_config()
	if not items:
		frappe.throw(_("No hay items para facturar para el dueño {0}").format(dueno))
	payload = _construir_payload(doc, dueno, items, tipo_operacion, config, send_email)
	log_name = crear_log(
		reference_doctype=doc.doctype,
		reference_name=doc.name,
		dueno_fiscal=dueno,
		tipo_operacion=tipo_operacion,
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
		doc.db_set("estado_fe", estado)
		if data.get("is_validated"):
			doc.db_set("cufe_fe", data.get("cufe") or "")
		return data
	except Exception as e:
		actualizar_log(log_name, estado="Error", errores={"error": str(e)}, mensaje=str(e))
		doc.db_set("estado_fe", "Error")
		raise


@frappe.whitelist()
def enviar_factura_dian(name, doctype="Sales Invoice"):
	doc = frappe.get_doc(doctype, name)
	dueno = doc.get("dueno_fiscal_fe")
	if dueno:
		items = _items_por_dueno(doc, dueno)
		enviar_factura_fe(doc, dueno, items, tipo_operacion="Manual")
	else:
		duenos = _duenos_en_factura(doc)
		if not duenos:
			frappe.throw(_("La factura no tiene items con dueño fiscal asignado"))
		for dueno, items in duenos.items():
			enviar_factura_fe(doc, dueno, items, tipo_operacion="Manual")
	doc.reload()
	return {"ok": True, "estado": doc.get("estado_fe")}


def _ultimo_log(doctype, name):
	logs = frappe.get_all(
		"Log Factura Electronica",
		filters={"reference_doctype": doctype, "reference_name": name, "estado": ["in", ["Validada", "Enviada"]]},
		fields=["name", "estado", "cufe", "public_url", "numero_factus", "dueno_fiscal"],
		order_by="creation desc",
		limit=1,
	)
	return logs[0] if logs else None


@frappe.whitelist()
def get_info_fe(name, doctype="Sales Invoice"):
	log = _ultimo_log(doctype, name)
	if not log:
		return {"ok": False}
	return {
		"ok": True,
		"estado": log.estado,
		"cufe": log.cufe,
		"public_url": log.public_url,
		"numero_factus": log.numero_factus,
		"dueno_fiscal": log.dueno_fiscal,
	}


@frappe.whitelist()
def descargar_pdf_factura(name, doctype="Sales Invoice"):
	log = _ultimo_log(doctype, name)
	if not log or not log.numero_factus:
		frappe.throw(_("No hay una factura electronica valida para descargar el PDF"))
	api = FacturacionElectronicaAPI(log.dueno_fiscal)
	return api.descargar_pdf(log.numero_factus)


def _items_por_dueno(doc, dueno):
	result = []
	for row in doc.items:
		item = frappe.get_cached_doc("Item", row.item_code)
		item_dueno = item.get("dueno_fiscal")
		if item_dueno == dueno:
			result.append(row)
	return result


def _duenos_en_factura(doc):
	duenos = {}
	for row in doc.items:
		item = frappe.get_cached_doc("Item", row.item_code)
		d = item.get("dueno_fiscal")
		if not d:
			continue
		duenos.setdefault(d, []).append(row)
	return duenos


def _numero_a_letras(total):
	total = int(round(flt(total)))
	return _convertir(total) + " PESOS M/CTE"


_UNID = ["", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve"]
_ESP = {
	10: "diez",
	11: "once",
	12: "doce",
	13: "trece",
	14: "catorce",
	15: "quince",
	20: "veinte",
	100: "cien",
}
_DEC = ["", "", "veinti", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa"]


def _convertir(n):
	if n == 0:
		return "cero"
	if n in _ESP:
		return _ESP[n]
	if n < 10:
		return _UNID[n]
	if n < 30:
		if n == 20:
			return "veinte"
		return "veinti" + _UNID[n - 20]
	if n < 100:
		d, u = divmod(n, 10)
		return _DEC[d] + (" y " + _UNID[u] if u else "")
	if n < 200:
		return "ciento " + _convertir(n - 100) if n != 100 else "cien"
	if n < 1000:
		c, r = divmod(n, 100)
		return _UNID[c] + "cientos" + (" " + _convertir(r) if r else "")
	if n < 2000:
		return "mil" + (" " + _convertir(n - 1000) if n - 1000 else "")
	if n < 1000000:
		m, r = divmod(n, 1000)
		return _convertir(m) + " mil" + (" " + _convertir(r) if r else "")
	if n < 2000000:
		return "un millon" + (" " + _convertir(n - 1000000) if n - 1000000 else "")
	if n < 1000000000000:
		m, r = divmod(n, 1000000)
		return _convertir(m) + " millones" + (" " + _convertir(r) if r else "")
	return str(n)
