import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password


class DuenoFiscal(Document):
	def validate(self):
		if self.nit:
			self.nit = "".join(ch for ch in str(self.nit) if ch.isdigit())
		if self.nit and not self.dv:
			try:
				from facturacion_electronica.utils.validacion import calcular_dv

				self.dv = calcular_dv(self.nit)
			except Exception:
				pass
		if self.numbering_range_id:
			self.numbering_range_id = int(self.numbering_range_id)


def get_credenciales(dueno_name):
	dueno = frappe.get_cached_doc("Dueno Fiscal", dueno_name)
	if not dueno.activo:
		frappe.throw(_("El dueño fiscal {0} no esta activo").format(dueno_name))
	secret = get_decrypted_password("Dueno Fiscal", dueno.name, "client_secret", raise_exception=False) or ""
	password = get_decrypted_password("Dueno Fiscal", dueno.name, "password", raise_exception=False) or ""
	return {
		"nombre": dueno.name,
		"nit": dueno.nit,
		"dv": dueno.dv,
		"razon_social": dueno.razon_social,
		"direccion": dueno.direccion,
		"telefono": dueno.telefono,
		"email": dueno.email,
		"municipality_code": dueno.municipality_code,
		"numbering_range_id": dueno.numbering_range_id,
		"client_id": dueno.client_id,
		"client_secret": secret,
		"username": dueno.username,
		"password": password,
	}


@frappe.whitelist()
def probar_conexion(name):
	from facturacion_electronica.utils.api_fe import FacturacionElectronicaAPI

	api = FacturacionElectronicaAPI(name)
	token = api.autenticar()
	if token:
		return {"ok": True, "message": _("Conexion exitosa con Factus para {0}").format(name)}
	return {"ok": False, "message": _("No se pudo autenticar con Factus")}
