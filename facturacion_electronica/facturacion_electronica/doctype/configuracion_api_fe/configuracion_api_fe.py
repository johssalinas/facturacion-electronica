import frappe
from frappe.model.document import Document

URL_SANDBOX = "https://api-sandbox.factus.com.co"
URL_PRODUCCION = "https://api.factus.com.co"


class ConfiguracionAPIFE(Document):
	def validate(self):
		if not self.url_sandbox:
			self.url_sandbox = URL_SANDBOX
		if not self.url_produccion:
			self.url_produccion = URL_PRODUCCION
		if not self.cliente_consumidor_final:
			frappe.msgprint(
				frappe._(
					"Configure un cliente 'Consumidor Final' para el agrupado diario de ventas CCF."
				),
				indicator="orange",
			)


def get_config():
	doc = frappe.get_cached_doc("Configuracion API FE")
	if not doc.url_sandbox:
		doc.url_sandbox = URL_SANDBOX
	if not doc.url_produccion:
		doc.url_produccion = URL_PRODUCCION
	return doc


def get_url_base():
	config = get_config()
	return URL_PRODUCCION if config.ambiente == "Produccion" else URL_SANDBOX


def get_timeout():
	return int(get_config().timeout or 30)
