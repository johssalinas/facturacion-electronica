function fe_call(method, args, opts) {
	return frappe.call({
		method: method,
		args: args,
		freeze: opts && opts.freeze !== undefined ? opts.freeze : true,
		callback: opts && opts.callback
	});
}

function fe_descargar_pdf(frm) {
	fe_call("facturacion_electronica.utils.api_fe.descargar_pdf_factura", {
		name: frm.doc.name,
		doctype: frm.doctype
	}, {
		callback: function (r) {
			if (r && r.message && r.message.pdf_base_64_encoded) {
				var byteChars = atob(r.message.pdf_base_64_encoded);
				var byteNumbers = new Array(byteChars.length);
				for (var i = 0; i < byteChars.length; i++) {
					byteNumbers[i] = byteChars.charCodeAt(i);
				}
				var byteArray = new Uint8Array(byteNumbers);
				var blob = new Blob([byteArray], { type: "application/pdf" });
				var url = URL.createObjectURL(blob);
				var a = document.createElement("a");
				a.href = url;
				a.download = r.message.file_name || (frm.doc.name + ".pdf");
				document.body.appendChild(a);
				a.click();
				document.body.removeChild(a);
				URL.revokeObjectURL(url);
			}
		}
	});
}

function fe_ver_pdf(frm) {
	fe_call("facturacion_electronica.utils.api_fe.get_info_fe", {
		name: frm.doc.name,
		doctype: frm.doctype
	}, {
		callback: function (r) {
			if (r && r.message && r.message.public_url) {
				window.open(r.message.public_url, "_blank");
			} else {
				frappe.msgprint(__("No hay PDF electronico disponible para esta factura."));
			}
		}
	});
}

function fe_reenviar(frm) {
	fe_call("facturacion_electronica.utils.api_fe.enviar_factura_dian", {
		name: frm.doc.name,
		doctype: frm.doctype
	}, {
		callback: function (r) {
			if (r && r.message) {
				frappe.msgprint(__("Estado DIAN: {0}").format(r.message.estado), __("Reenvio"));
				frm.reload_doc();
			}
		}
	});
}

function setup_fe_buttons(frm) {
	if (frm.doc.docstatus !== 1) {
		return;
	}
	var estado = frm.doc.estado_fe;
	if (!estado || estado === "Error" || estado === "No Aplica") {
		frm.add_custom_button(__("Reenviar a DIAN"), function () {
			fe_reenviar(frm);
		}, __("Facturacion Electronica"));
	}
	if (estado === "Validada" || estado === "Enviada") {
		frm.add_custom_button(__("Ver PDF DIAN"), function () {
			fe_ver_pdf(frm);
		}, __("Facturacion Electronica"));
		frm.add_custom_button(__("Descargar PDF DIAN"), function () {
			fe_descargar_pdf(frm);
		}, __("Facturacion Electronica"));
	}
}

frappe.ui.form.on("Sales Invoice", {
	refresh: setup_fe_buttons
});

frappe.ui.form.on("POS Invoice", {
	refresh: setup_fe_buttons
});
