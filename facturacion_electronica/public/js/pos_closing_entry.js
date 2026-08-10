function fe_cerrar_actualizar(frm) {
	if (frm.doc.docstatus !== 0) {
		return;
	}
	// Don't call the endpoint on new (unsaved) documents
	if (frm.is_new()) {
		return;
	}

	// Fill mode of payment column
	fill_mode_of_payment(frm);

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
	refresh: fe_cerrar_actualizar,

	// After invoices are loaded, fill mode_of_payment in each row
	pos_opening_entry: function (frm) {
		// This fires when the closing entry loads data from opening entry
		// Wait for get_invoices to finish and then fill the mode_of_payment
		setTimeout(function () {
			fill_mode_of_payment(frm);
		}, 2000);
	}
});

function fill_mode_of_payment(frm) {
	// Collect all invoice names from both tables
	var invoices = [];
	(frm.doc.pos_invoices || []).forEach(function (row) {
		if (row.pos_invoice && !row.custom_modo_de_pago) invoices.push(row);
	});
	(frm.doc.sales_invoices || []).forEach(function (row) {
		if (row.sales_invoice && !row.custom_modo_de_pago) invoices.push(row);
	});

	if (!invoices.length) return;

	// Fetch mode of payment for each invoice
	var names = invoices.map(function (r) { return r.pos_invoice || r.sales_invoice; });

	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Sales Invoice Payment",
			filters: { parent: ["in", names], amount: [">", 0] },
			fields: ["parent", "mode_of_payment", "amount"],
			order_by: "amount desc",
			limit_page_length: 0
		},
		async: false,
		callback: function (r) {
			if (!r || !r.message) return;

			// Group by parent
			var mop_map = {};
			r.message.forEach(function (p) {
				if (!mop_map[p.parent]) mop_map[p.parent] = [];
				if (mop_map[p.parent].indexOf(p.mode_of_payment) === -1) {
					mop_map[p.parent].push(p.mode_of_payment);
				}
			});

			// Fill the custom_modo_de_pago field
			(frm.doc.pos_invoices || []).forEach(function (row) {
				var key = row.pos_invoice;
				if (key && mop_map[key]) {
					row.custom_modo_de_pago = mop_map[key].join(", ");
				}
			});
			(frm.doc.sales_invoices || []).forEach(function (row) {
				var key = row.sales_invoice;
				if (key && mop_map[key]) {
					row.custom_modo_de_pago = mop_map[key].join(", ");
				}
			});

			frm.refresh_field("pos_invoices");
			frm.refresh_field("sales_invoices");
		}
	});
}
