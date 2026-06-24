frappe.ui.form.on("Dueno Fiscal", {
	onload: function (frm) {
		frm.set_df_property("municipality_code", "description", "Codigo DIVIPOLA del municipio (ej: 50001 Villa del Rosario).");
	},
	refresh: function (frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Probar Conexion"), function () {
				frappe.call({
					method: "facturacion_electronica.facturacion_electronica.doctype.dueno_fiscal.dueno_fiscal.probar_conexion",
					args: { name: frm.doc.name },
					freeze: true,
					callback: function (r) {
						if (r.message) {
							frappe.msgprint(r.message.message, r.message.ok ? __("OK") : __("Error"));
						}
					}
				});
			});
		}
	}
});
