frappe.after_ajax(function () {
	if (!(frappe.pages && frappe.pages["pos"] && frappe.pages["pos"].pos_app)) {
		return;
	}
	$(document).on("click", ".pos-bill-header", function () {
		setTimeout(function () {
			var customer = $(".pos-customer-search input").val();
			if (customer && window.__fe_b2b_customers && window.__fe_b2b_customers.indexOf(customer) !== -1) {
				frappe.show_alert({
					message: __("Cliente empresa: se emitira factura electronica inmediata."),
					indicator: "blue"
				}, 5);
			}
		}, 500);
	});
});
