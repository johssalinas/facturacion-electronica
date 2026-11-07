// Copyright (c) 2026, Salsamentaria and contributors
// License: MIT

const BPP_VISTA_RESUMEN = "Resumen por producto";
const BPP_VISTA_EVOL_PRODUCTO = "Evolución por producto";
const BPP_VISTA_EVOL_TOTAL = "Evolución total";

frappe.query_reports["Balance por Producto"] = {
	filters: [
		{
			fieldname: "company",
			label: "Empresa",
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: "Desde",
			fieldtype: "Date",
			default: frappe.datetime.year_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: "Hasta",
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "vista",
			label: "Vista",
			fieldtype: "Select",
			options: [BPP_VISTA_RESUMEN, BPP_VISTA_EVOL_PRODUCTO, BPP_VISTA_EVOL_TOTAL].join("\n"),
			default: BPP_VISTA_RESUMEN,
			reqd: 1,
		},
		{
			fieldname: "periodo",
			label: "Período",
			fieldtype: "Select",
			options: ["Diario", "Semanal", "Mensual", "Trimestral", "Anual"].join("\n"),
			default: "Mensual",
			depends_on: `eval: doc.vista != "${BPP_VISTA_RESUMEN}"`,
		},
		{
			fieldname: "item_group",
			label: "Grupo de producto",
			fieldtype: "Link",
			options: "Item Group",
		},
		{
			fieldname: "item_code",
			label: "Producto",
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "warehouse",
			label: "Almacén",
			fieldtype: "Link",
			options: "Warehouse",
		},
		{
			fieldname: "base_costo",
			label: "Base de costo",
			fieldtype: "Select",
			options: ["Costo de compra (promedio)", "Kardex del sistema (FIFO)"].join("\n"),
			default: "Costo de compra (promedio)",
			reqd: 1,
		},
		{
			fieldname: "resultado",
			label: "Resultado",
			fieldtype: "Select",
			options: ["Todos", "Con ganancia", "Con pérdida", "Sin costo confiable"].join("\n"),
			default: "Todos",
		},
		{
			fieldname: "grafico",
			label: "Gráfico",
			fieldtype: "Select",
			options: [
				"Top 15 por utilidad",
				"15 con menor utilidad",
				"Top 15: compras vs ventas",
				"Top 15: margen %",
			].join("\n"),
			default: "Top 15 por utilidad",
			depends_on: `eval: doc.vista == "${BPP_VISTA_RESUMEN}"`,
		},
		{
			fieldname: "grafico_evol",
			label: "Gráfico",
			fieldtype: "Select",
			options: [
				"Dinero: ventas, compras y utilidad",
				"Precios: venta vs costo (un producto)",
				"Inventario: valor al cierre",
			].join("\n"),
			default: "Dinero: ventas, compras y utilidad",
			depends_on: `eval: doc.vista != "${BPP_VISTA_RESUMEN}"`,
		},
		{
			fieldname: "formato",
			label: "Columnas",
			fieldtype: "Select",
			options: ["Completo", "Compacto (para imprimir o PDF)"].join("\n"),
			default: "Completo",
		},
		{
			fieldname: "solo_vendidos",
			label: "Solo productos vendidos en el rango",
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "excluir_sospechosos",
			label: "Excluir costos sospechosos",
			fieldtype: "Check",
			default: 1,
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;

		// Fila TOTAL: negrita
		if (data.es_total) {
			return `<b>${value}</b>`;
		}

		const campo = column.fieldname;
		const crudo = data[campo];
		const verde = "var(--green-600)";
		const rojo = "var(--red-600)";

		// Dinero y porcentajes: verde si es positivo, rojo si es negativo
		if (["utilidad", "margen", "utilidad_unit", "balance_caja", "var_precio", "var_ventas"].includes(campo)) {
			if (crudo !== null && crudo !== undefined && crudo !== 0) {
				const fuerte = ["utilidad", "margen"].includes(campo) ? "600" : "400";
				value = `<span style="color:${crudo < 0 ? rojo : verde};font-weight:${fuerte}">${value}</span>`;
			}
		}

		// Si el costo sube es malo
		if (campo === "var_costo" && crudo) {
			value = `<span style="color:${crudo > 0 ? rojo : verde}">${value}</span>`;
		}

		// Stock negativo
		if (["inv_final_qty", "inv_final_valor"].includes(campo) && crudo < 0) {
			value = `<span style="color:${rojo}">${value}</span>`;
		}

		if (campo === "estado" && crudo) {
			const colores = {
				Ganancia: "green",
				"Pérdida": "red",
				"Sin costo": "orange",
				"Costo sospechoso": "orange",
				"Sin ventas": "gray",
				Equilibrio: "gray",
			};
			value = `<span class="indicator-pill ${colores[crudo] || "gray"} ellipsis">${crudo}</span>`;
		}

		if (campo === "alerta" && crudo) {
			value = `<span style="color:var(--orange-600)" title="${frappe.utils.escape_html(crudo)}">${value}</span>`;
		}

		if (campo === "abc" && crudo) {
			const color = { A: "green", B: "blue", C: "gray" }[crudo];
			value = `<span class="indicator-pill ${color} ellipsis">${crudo}</span>`;
		}

		return value;
	},

	onload(report) {
		const cambiar_vista = (vista, periodo) => {
			const valores = { vista: vista };
			if (periodo) valores.periodo = periodo;
			frappe.query_report.set_filter_value(valores);
		};

		report.page.add_inner_button("Resumen por producto", () => cambiar_vista(BPP_VISTA_RESUMEN), "Vistas");
		report.page.add_inner_button(
			"Evolución mensual total",
			() => cambiar_vista(BPP_VISTA_EVOL_TOTAL, "Mensual"),
			"Vistas"
		);
		report.page.add_inner_button(
			"Evolución semanal total",
			() => cambiar_vista(BPP_VISTA_EVOL_TOTAL, "Semanal"),
			"Vistas"
		);
		report.page.add_inner_button(
			"Evolución semanal por producto",
			() => cambiar_vista(BPP_VISTA_EVOL_PRODUCTO, "Semanal"),
			"Vistas"
		);

		report.page.add_inner_button("Panel de balance", () => frappe.set_route("balance-de-productos"));
	},
};
