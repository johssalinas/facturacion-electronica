frappe.ui.form.on("Configuracion API FE", {
	onload: function (frm) {
		frm.set_df_property("url_sandbox", "description", "Base sandbox: https://api-sandbox.factus.com.co");
		frm.set_df_property("url_produccion", "description", "Base produccion: https://api.factus.com.co");
	}
});
