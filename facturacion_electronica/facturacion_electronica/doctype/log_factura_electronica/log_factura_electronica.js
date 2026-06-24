frappe.ui.form.on("Log Factura Electronica", {
	refresh: function (frm) {
		if (frm.doc.public_url) {
			frm.add_custom_button(__("Ver PDF DIAN"), function () {
				window.open(frm.doc.public_url, "_blank");
			});
		}
	}
});
