app_name = "facturacion_electronica"
app_title = "Facturacion Electronica"
app_publisher = "Salsamentaria"
app_description = "Facturacion electronica Colombia (Factus API) para ERPNext"
app_icon = "octicon octicon-file-pdf"
app_color = "#2962ff"
app_email = "admin@salsamentaria.com"
app_license = "MIT"
app_version = "0.0.1"

required_apps = ["erpnext"]

boot_session = "facturacion_electronica.events.auth.boot_session"
on_login = "facturacion_electronica.events.auth.on_login"

override_doctype_class = {
	"POS Invoice": "facturacion_electronica.overrides.pos_invoice.CustomPOSInvoice",
	"POS Opening Entry": "facturacion_electronica.overrides.pos_opening_entry.CustomPOSOpeningEntry",
	"POS Closing Entry": "facturacion_electronica.overrides.pos_closing_entry.CustomPOSClosingEntry",
	"Sales Invoice": "facturacion_electronica.overrides.sales_invoice.CustomSalesInvoice",
}

override_whitelisted_methods = {
	"erpnext.selling.page.point_of_sale.point_of_sale.check_opening_entry": "facturacion_electronica.overrides.pos_opening_entry.check_opening_entry",
	"erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry.get_invoices": "facturacion_electronica.overrides.pos_closing_entry.get_invoices",
}

doc_events = {
	"Sales Invoice": {
		"before_submit": "facturacion_electronica.events.sales_invoice.before_submit",
		"on_submit": "facturacion_electronica.events.sales_invoice.on_submit",
	},
	"POS Invoice": {
		"on_cancel": "facturacion_electronica.events.pos_invoice.on_cancel",
	},
	"POS Closing Entry": {
		"before_submit": "facturacion_electronica.events.pos_closing_entry.before_submit",
	},
	"Purchase Invoice": {
		"before_validate": "facturacion_electronica.events.purchase_invoice.apply_purchase_tax_template",
	},
}

scheduler_events = {
	"hourly": [
		"facturacion_electronica.utils.retry.reintentar_facturas_fallidas",
	],
}

fixtures = [
	[
		"Custom Field",
		{
			"filters": [
				[
					"name",
					"in",
					[
						"Item-dueno_fiscal",
						"Item-purchase_tax_template",
						"Account-fe_tax_code",
						"Account-fe_is_excluded",
						"UOM-fe_unit_measure_code",
						"Customer-requiere_factura_inmediata",
						"Customer-fe_identification_document_code",
						"Customer-fe_numero_documento",
						"Customer-fe_dv",
						"Customer-fe_tribute_code",
						"Customer-fe_municipality_code",
						"Sales Invoice-fe_section",
						"Sales Invoice-dueno_fiscal_fe",
						"Sales Invoice-estado_fe",
						"Sales Invoice-custom_enviar_dian",
						"Sales Invoice-es_resumen_diario_ccf",
						"Sales Invoice-cufe_fe",
						"POS Invoice-fe_section",
						"POS Invoice-dueno_fiscal_fe",
						"POS Invoice-estado_fe",
						"POS Invoice-custom_enviar_dian",
						"POS Invoice-es_resumen_diario_ccf",
						"POS Invoice-cufe_fe",
						"Mode of Payment-fe_tipo_medio_pago",
						"POS Closing Entry-salidas_de_dinero",
					],
				]
			]
		},
	],
	["Tipo Documento Identidad FE", {}],
	["Tributo FE", {}],
	["Municipio FE", {}],
	["Codigo Impuesto FE", {}],
	["Unidad Medida FE", {}],
	["Tipo Medio Pago FE", {}],
]

doctype_js = {
	"Sales Invoice": "public/js/sales_invoice.js",
	"POS Invoice": "public/js/sales_invoice.js",
	"POS Closing Entry": "public/js/pos_closing_entry.js",
}

page_js = {
	"point-of-sale": ["public/js/pos_custom.js", "public/js/pos_scale.js"],
}

app_include_js = ["public/js/desktop_redirect.js"]
