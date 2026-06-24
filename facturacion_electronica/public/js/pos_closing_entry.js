function fe_cerrar_actualizar(frm) {
	if (frm.doc.docstatus !== 0) {
		return;
	}
	frappe.call({
		method: "facturacion_electronica.events.pos_closing_entry.get_pendientes_fe",
		args: { name: frm.doc.name },
		callback: function (r) {
			if (!r || !r.message) {
				return;
			}
			var count = r.message.count;
			if (count > 0) {
				frm.dashboard.add_indicator(
					__("{0} factura(s) pendiente(s) de enviar a la DIAN", [count]),
					"red"
				);
				frm.add_custom_button(__("Enviar pendientes a DIAN"), function () {
					frappe.call({
						method: "facturacion_electronica.events.pos_closing_entry.enviar_pendientes_fe",
						args: { name: frm.doc.name },
						freeze: true,
						callback: function (rr) {
							if (rr && rr.message) {
								var m = rr.message;
								if (m.ok) {
									frappe.show_alert({
										message: m.message,
										indicator: "green"
									}, 6);
								} else {
									frappe.msgprint({
										title: __("Envio a DIAN"),
										message: m.message + "<br><br>" + (m.errores || []).join("<br>"),
										indicator: "red"
									});
								}
								frm.reload_doc();
							}
						}
					});
				}).addClass("btn-primary");
			} else {
				frm.dashboard.add_indicator(
					__("Facturas electronicas al dia. Puede cerrar caja."),
					"green"
				);
			}
		}
	});
}

frappe.ui.form.on("POS Closing Entry", {
	refresh: fe_cerrar_actualizar
});
