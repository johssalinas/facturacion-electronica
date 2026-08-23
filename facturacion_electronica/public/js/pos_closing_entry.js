function fe_cerrar_actualizar(frm) {
	if (frm.doc.docstatus !== 0) {
		return;
	}
	// Don't call the endpoint on new (unsaved) documents
	if (frm.is_new()) {
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
	refresh: function (frm) {
		set_grid_page_length(frm);
		// Fill Modo de Pago / Estado for EVERY closing on display, including
		// submitted (old) closings whose saved rows predate those custom fields.
		if (!frm.is_new()) {
			fill_mode_of_payment(frm);
		}
		fe_cerrar_actualizar(frm);
	},

	// When the user picks the POS Opening Entry on a new closing, the invoices
	// are loaded asynchronously by the standard get_invoices flow (freeze +
	// add_child + refresh_field). Wait for the rows to be present before
	// applying the no-limit pagination and filling the custom columns, so the
	// whole table is visible right away.
	pos_opening_entry: function (frm) {
		apply_when_invoices_loaded(frm);
	}
});

function set_grid_page_length(frm) {
	// Remove the default 50-row pagination from both child tables.
	// Frappe v15+ keeps the pagination state in grid.grid_pagination (not in
	// the grid itself), so we must set both to work across versions.
	["pos_invoices", "sales_invoices"].forEach(function (fieldname) {
		var field = frm.get_field(fieldname);
		if (field && field.grid) {
			if (field.grid.grid_pagination) {
				field.grid.grid_pagination.page_length = 10000;
			}
			field.grid.page_length = 10000;
			field.grid.refresh();
		}
	});
}

function has_invoices(frm) {
	return (frm.doc.pos_invoices || []).length > 0 || (frm.doc.sales_invoices || []).length > 0;
}

function apply_when_invoices_loaded(frm) {
	var attempts = 0;
	var apply = function () {
		attempts++;
		set_grid_page_length(frm);
		if (has_invoices(frm) || attempts > 60) {
			fill_mode_of_payment(frm);
			return;
		}
		setTimeout(apply, 500);
	};
	setTimeout(apply, 500);
}

function fill_mode_of_payment(frm) {
	// Collect all invoice names from both tables
	var invoices = [];
	(frm.doc.pos_invoices || []).forEach(function (row) {
		if (row.pos_invoice) invoices.push(row.pos_invoice);
	});
	(frm.doc.sales_invoices || []).forEach(function (row) {
		if (row.sales_invoice) invoices.push(row.sales_invoice);
	});

	if (!invoices.length) return;

	// Remove pagination limit before filling rows
	set_grid_page_length(frm);

	frappe.call({
		method: "facturacion_electronica.events.pos_closing_entry.get_mode_of_payment_map",
		args: { invoice_names: invoices },
		async: true,
		callback: function (r) {
			if (!r || !r.message) return;
			var info_map = r.message;

			(frm.doc.pos_invoices || []).forEach(function (row) {
				var info = row.pos_invoice && info_map[row.pos_invoice];
				if (info) {
					row.custom_modo_de_pago = info.modo_de_pago || "";
					row.custom_estado_pago  = info.estado_pago  || "";
				}
			});
			(frm.doc.sales_invoices || []).forEach(function (row) {
				var info = row.sales_invoice && info_map[row.sales_invoice];
				if (info) {
					row.custom_modo_de_pago = info.modo_de_pago || "";
					row.custom_estado_pago  = info.estado_pago  || "";
				}
			});

			frm.refresh_field("pos_invoices");
			frm.refresh_field("sales_invoices");

			// Ensure pagination limit stays removed after refresh
			set_grid_page_length(frm);
		}
	});
}
