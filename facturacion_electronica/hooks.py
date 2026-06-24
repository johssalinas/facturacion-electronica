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

override_doctype_class = {
	"POS Invoice": "facturacion_electronica.overrides.pos_invoice.CustomPOSInvoice",
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
						"Item-fe_tax_code",
						"Item-fe_tax_rate",
						"Item-fe_is_excluded",
						"Item-fe_unit_measure_code",
						"Item-fe_standard_code",
						"Customer-requiere_factura_inmediata",
						"Customer-fe_identification_document_code",
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
					],
				]
			]
		},
	]
]

doctype_js = {
	"Sales Invoice": "public/js/sales_invoice.js",
	"POS Invoice": "public/js/sales_invoice.js",
	"POS Closing Entry": "public/js/pos_closing_entry.js",
}

app_include_js = []
