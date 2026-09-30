frappe.pages["facturacion-manual-fe"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Facturacion Manual FE"),
		single_column: true,
	});
	new FacturacionManualFE(page);
};

class FacturacionManualFE {
	constructor(page) {
		this.page = page;
		this.wrapper = $(page.body);
		this.pendientes = [];
		this.cantidades = {};
		this.make();
	}

	make() {
		this.wrapper.html(`
			<div class="fe-manual-container">
				<div class="row" style="margin-bottom: 15px;">
					<div class="col-md-4">
						<label class="control-label">${__("Dueño Fiscal")}</label>
						<div id="fe-dueno-select"></div>
					</div>
					<div class="col-md-4" style="padding-top: 24px;">
						<button class="btn btn-default btn-sm" id="fe-btn-refrescar">
							${__("Actualizar Pendientes")}
						</button>
					</div>
				</div>
				<div id="fe-pendientes-alert"></div>
				<table class="table table-bordered" id="fe-pendientes-table" style="display:none;">
					<thead>
						<tr>
							<th>${__("Producto")}</th>
							<th>${__("Unidad")}</th>
							<th class="text-right">${__("Cantidad Pendiente")}</th>
							<th class="text-right" style="width: 160px;">${__("Cantidad a Facturar")}</th>
						</tr>
					</thead>
					<tbody id="fe-pendientes-body"></tbody>
				</table>
				<div id="fe-generar-container" style="margin-top: 15px; display:none;">
					<button class="btn btn-primary" id="fe-btn-generar">
						${__("Generar Factura Electronica")}
					</button>
				</div>
			</div>
		`);

		this.dueno_field = frappe.ui.form.make_control({
			parent: this.wrapper.find("#fe-dueno-select"),
			df: {
				fieldtype: "Link",
				fieldname: "dueno_fiscal",
				options: "Dueno Fiscal",
				placeholder: __("Seleccione un dueño fiscal"),
				get_query: () => ({ filters: { activo: 1 } }),
				onchange: () => this.cargar_pendientes(),
			},
			render_input: true,
		});
		this.dueno_field.refresh();

		this.wrapper.find("#fe-btn-refrescar").on("click", () => this.cargar_pendientes());
		this.wrapper.find("#fe-btn-generar").on("click", () => this.generar_factura());
	}

	cargar_pendientes() {
		var dueno = this.dueno_field.get_value();
		this.cantidades = {};
		if (!dueno) {
			this.wrapper.find("#fe-pendientes-table").hide();
			this.wrapper.find("#fe-generar-container").hide();
			this.wrapper.find("#fe-pendientes-alert").html("");
			return;
		}
		frappe.call({
			method: "facturacion_electronica.utils.facturacion_manual.get_pendientes",
			args: { dueno_fiscal: dueno },
			freeze: true,
			callback: (r) => {
				this.pendientes = (r && r.message) || [];
				this.render_tabla();
			},
		});
	}

	render_tabla() {
		var body = this.wrapper.find("#fe-pendientes-body");
		body.empty();
		var alertBox = this.wrapper.find("#fe-pendientes-alert");

		if (!this.pendientes.length) {
			this.wrapper.find("#fe-pendientes-table").hide();
			this.wrapper.find("#fe-generar-container").hide();
			alertBox.html(
				`<div class="alert alert-info">${__(
					"No hay ventas pendientes de facturar para este dueño fiscal."
				)}</div>`
			);
			return;
		}

		alertBox.html("");
		this.wrapper.find("#fe-pendientes-table").show();
		this.wrapper.find("#fe-generar-container").show();

		var self = this;
		this.pendientes.forEach(function (row) {
			var tr = $(`
				<tr data-item-code="${frappe.utils.escape_html(row.item_code)}">
					<td>${frappe.utils.escape_html(row.item_name || row.item_code)}</td>
					<td>${frappe.utils.escape_html(row.uom || "")}</td>
					<td class="text-right">${row.qty_pendiente}</td>
					<td class="text-right">
						<input type="number" class="form-control fe-qty-input text-right"
							min="0" step="0.01" max="${row.qty_pendiente}"
							value="${row.qty_pendiente}" />
					</td>
				</tr>
			`);
			tr.find(".fe-qty-input").on("input", function () {
				var val = flt($(this).val());
				var max = flt(row.qty_pendiente);
				if (val > max) {
					val = max;
					$(this).val(max);
				}
				if (val < 0) {
					val = 0;
					$(this).val(0);
				}
				self.cantidades[row.item_code] = val;
			});
			self.cantidades[row.item_code] = flt(row.qty_pendiente);
			body.append(tr);
		});
	}

	generar_factura() {
		var dueno = this.dueno_field.get_value();
		if (!dueno) {
			frappe.msgprint(__("Seleccione un dueño fiscal"));
			return;
		}
		var selecciones = {};
		Object.keys(this.cantidades).forEach((item_code) => {
			var qty = flt(this.cantidades[item_code]);
			if (qty > 0) {
				selecciones[item_code] = qty;
			}
		});
		if (!Object.keys(selecciones).length) {
			frappe.msgprint(__("Indique al menos una cantidad mayor a cero"));
			return;
		}

		frappe.confirm(
			__("¿Confirma generar la factura electronica para {0} con las cantidades indicadas?", [dueno]),
			() => {
				frappe.call({
					method: "facturacion_electronica.utils.facturacion_manual.generar_factura_manual",
					args: {
						dueno_fiscal: dueno,
						selecciones: selecciones,
					},
					freeze: true,
					freeze_message: __("Enviando factura a Factus..."),
					callback: (r) => {
						if (r && r.message && r.message.ok) {
							frappe.show_alert(
								{
									message: __("Factura electronica generada. Estado: {0}", [
										r.message.estado,
									]),
									indicator: "green",
								},
								8
							);
							this.cargar_pendientes();
						}
					},
				});
			}
		);
	}
}

function flt(val) {
	var n = parseFloat(val);
	return isNaN(n) ? 0 : n;
}
