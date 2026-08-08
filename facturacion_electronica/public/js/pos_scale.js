// =============================================================================
// POS Scale Integration — Web Serial API
// Báscula MORESCO MAVIN HY918 (RS232 serial)
//
// CONFIGURACIÓN: Editar estos parámetros cuando se tenga la báscula conectada
// =============================================================================

var POS_SCALE_CONFIG = {
	// Puerto serial (Web Serial API no usa COM3 directamente, el usuario selecciona)
	baudRate: 9600,
	dataBits: 8,
	stopBits: 1,
	parity: "none",
	flowControl: "none",

	// Modo de lectura:
	// "continuous" — la báscula envía datos constantemente
	// "on_demand" — hay que enviar un comando para que responda
	mode: "continuous",

	// Comando para solicitar peso (solo si mode = "on_demand")
	// Comunes: "W\r\n", "R\r\n", "\x05" (ENQ), "P\r\n"
	requestCommand: "W\r\n",

	// Función para parsear el peso del string recibido de la báscula.
	// Recibe la línea de texto cruda y debe retornar el peso como número (en kg).
	// AJUSTAR ESTE PARSER cuando se conozca el formato real de la báscula.
	//
	// Ejemplos comunes de formatos de básculas:
	//   "ST,GS,  0.325 kg"       → parseFloat("0.325")
	//   "  +  0.500 kg  "        → parseFloat("0.500")
	//   "0325"                   → parseInt("0325") / 1000
	//   "W: 1.250 KG\r\n"       → parseFloat("1.250")
	//   "00000325"               → parseInt("00000325") / 1000
	//
	parseWeight: function (raw_line) {
		// Estrategia genérica: extraer el primer número decimal de la línea
		var cleaned = raw_line.replace(/[^\d.\-]/g, " ").trim();
		var match = cleaned.match(/(\d+\.?\d*)/);
		if (match) {
			var value = parseFloat(match[1]);
			// Si el valor es > 100, probablemente está en gramos → convertir a kg
			// Ajustar este umbral según la báscula
			if (value > 100) {
				value = value / 1000;
			}
			return value;
		}
		return null;
	},

	// Peso mínimo para considerar válido (evita lecturas de ruido)
	minWeight: 0.005, // 5 gramos mínimo

	// Intervalo de lectura en ms (para modo continuous, cada cuánto procesar)
	readInterval: 300,

	// Carácter(es) de fin de línea que separan las lecturas
	lineEnding: "\n",
};

// =============================================================================
// IMPLEMENTACIÓN (no modificar a menos que se necesite)
// =============================================================================

(function () {
	"use strict";

	var scale_port = null;
	var scale_reader = null;
	var scale_connected = false;
	var last_stable_weight = 0;
	var weight_buffer = "";
	var reading_active = false;

	// Check if Web Serial API is available
	function is_serial_supported() {
		return "serial" in navigator;
	}

	// Connect to the scale
	async function connect_scale() {
		if (!is_serial_supported()) {
			frappe.msgprint({
				title: __("Báscula no soportada"),
				message: __("Tu navegador no soporta la conexión serial. Usa Google Chrome o Microsoft Edge."),
				indicator: "red",
			});
			return false;
		}

		try {
			// Request port from user (browser shows a picker dialog)
			scale_port = await navigator.serial.requestPort();

			await scale_port.open({
				baudRate: POS_SCALE_CONFIG.baudRate,
				dataBits: POS_SCALE_CONFIG.dataBits,
				stopBits: POS_SCALE_CONFIG.stopBits,
				parity: POS_SCALE_CONFIG.parity,
				flowControl: POS_SCALE_CONFIG.flowControl,
			});

			scale_connected = true;
			reading_active = true;

			frappe.show_alert({
				message: __("Báscula conectada correctamente"),
				indicator: "green",
			}, 5);

			// Start reading
			read_scale_loop();

			return true;
		} catch (err) {
			if (err.name === "NotFoundError") {
				// User cancelled the port selection
				return false;
			}
			frappe.msgprint({
				title: __("Error de conexión"),
				message: __("No se pudo conectar a la báscula: ") + err.message,
				indicator: "red",
			});
			console.error("Scale connection error:", err);
			return false;
		}
	}

	// Disconnect from the scale
	async function disconnect_scale() {
		reading_active = false;
		try {
			if (scale_reader) {
				await scale_reader.cancel();
				scale_reader = null;
			}
			if (scale_port) {
				await scale_port.close();
				scale_port = null;
			}
		} catch (err) {
			console.error("Scale disconnect error:", err);
		}
		scale_connected = false;
		last_stable_weight = 0;
		frappe.show_alert({
			message: __("Báscula desconectada"),
			indicator: "orange",
		}, 3);
	}

	// Continuous reading loop
	async function read_scale_loop() {
		if (!scale_port || !scale_port.readable) return;

		var decoder = new TextDecoderStream();
		var readableStreamClosed = scale_port.readable.pipeTo(decoder.writable);
		scale_reader = decoder.readable.getReader();

		try {
			while (reading_active) {
				var { value, done } = await scale_reader.read();
				if (done) break;
				if (value) {
					process_scale_data(value);
				}
			}
		} catch (err) {
			if (err.name !== "NetworkError" && reading_active) {
				console.error("Scale read error:", err);
			}
		} finally {
			scale_reader.releaseLock();
		}
	}

	// Send command to scale (for on_demand mode)
	async function request_weight() {
		if (!scale_port || !scale_port.writable) return;

		var encoder = new TextEncoder();
		var writer = scale_port.writable.getWriter();
		try {
			await writer.write(encoder.encode(POS_SCALE_CONFIG.requestCommand));
		} finally {
			writer.releaseLock();
		}
	}

	// Process incoming data from scale
	function process_scale_data(data) {
		weight_buffer += data;

		// Split by line ending
		var lines = weight_buffer.split(POS_SCALE_CONFIG.lineEnding);

		// Keep the last incomplete line in the buffer
		weight_buffer = lines.pop() || "";

		// Process complete lines
		for (var i = 0; i < lines.length; i++) {
			var line = lines[i].trim();
			if (!line) continue;

			var weight = POS_SCALE_CONFIG.parseWeight(line);
			if (weight !== null && weight >= POS_SCALE_CONFIG.minWeight) {
				last_stable_weight = weight;
				update_weight_display(weight);
			}
		}
	}

	// Update the weight display in the POS
	function update_weight_display(weight) {
		var $display = $(".pos-scale-weight-display");
		if ($display.length) {
			$display.text(weight.toFixed(3) + " kg");
		}
	}

	// Get the current weight reading
	function get_current_weight() {
		if (POS_SCALE_CONFIG.mode === "on_demand") {
			request_weight();
			// Wait a bit for the response
			return new Promise(function (resolve) {
				setTimeout(function () {
					resolve(last_stable_weight);
				}, 500);
			});
		}
		return Promise.resolve(last_stable_weight);
	}

	// Apply weight to the current cart item's qty
	async function apply_weight_to_cart() {
		var weight = await get_current_weight();

		if (!weight || weight < POS_SCALE_CONFIG.minWeight) {
			frappe.show_alert({
				message: __("No se detecta peso en la báscula. Coloque el producto."),
				indicator: "orange",
			}, 3);
			return;
		}

		if (!window.cur_pos || !window.cur_pos.frm) return;

		var frm = window.cur_pos.frm;
		var items = frm.doc.items;
		if (!items || !items.length) {
			frappe.show_alert({
				message: __("Agregue un producto al carrito primero."),
				indicator: "orange",
			}, 3);
			return;
		}

		// Apply to the last added item (most recent)
		var last_item = items[items.length - 1];

		await frappe.model.set_value(last_item.doctype, last_item.name, "qty", weight);
		window.cur_pos.update_cart_html(last_item);
		window.cur_pos.cart.update_totals_section(frm);

		frappe.show_alert({
			message: __("Peso aplicado: {0} kg a {1}", [weight.toFixed(3), last_item.item_name]),
			indicator: "green",
		}, 4);
	}

	// =============================================================================
	// UI Integration — Add scale button to POS
	// =============================================================================

	function inject_scale_ui() {
		// Wait for POS to be ready
		var $pos = $(".point-of-sale-app");
		if (!$pos.length) {
			setTimeout(inject_scale_ui, 1000);
			return;
		}

		// Don't inject twice
		if ($(".pos-scale-controls").length) return;

		// Add CSS
		$("head").append(`
			<style>
				.pos-scale-controls {
					display: flex;
					align-items: center;
					gap: 8px;
					padding: 8px 12px;
					background: var(--subtle-fg);
					border-radius: 8px;
					margin: 8px 0;
				}
				.pos-scale-controls .scale-btn {
					padding: 6px 12px;
					border-radius: 6px;
					border: 1px solid var(--border-color);
					cursor: pointer;
					font-size: 12px;
					font-weight: 500;
					background: var(--control-bg);
					color: var(--text-color);
				}
				.pos-scale-controls .scale-btn:hover {
					background: var(--bg-color);
				}
				.pos-scale-controls .scale-btn.connected {
					border-color: var(--green-500);
					color: var(--green-600);
				}
				.pos-scale-controls .scale-btn.weigh {
					background: var(--primary);
					color: white;
					border-color: var(--primary);
				}
				.pos-scale-controls .scale-btn.weigh:hover {
					opacity: 0.9;
				}
				.pos-scale-weight-display {
					font-family: monospace;
					font-size: 16px;
					font-weight: bold;
					color: var(--text-color);
					min-width: 100px;
					text-align: center;
				}
				.pos-scale-controls .scale-status {
					width: 8px;
					height: 8px;
					border-radius: 50%;
					background: var(--red-500);
				}
				.pos-scale-controls .scale-status.connected {
					background: var(--green-500);
				}
			</style>
		`);

		// Add scale controls below the cart header
		var $cart_container = $(".cart-container .cart-header");
		if (!$cart_container.length) {
			$cart_container = $(".cart-container");
		}

		var scale_html = `
			<div class="pos-scale-controls">
				<div class="scale-status" title="Desconectada"></div>
				<button class="scale-btn connect-scale-btn">Conectar Báscula</button>
				<button class="scale-btn weigh weigh-btn" style="display:none;">Pesar</button>
				<span class="pos-scale-weight-display">-- kg</span>
			</div>
		`;

		$cart_container.after(scale_html);

		// Event: Connect/Disconnect
		$(".connect-scale-btn").on("click", async function () {
			if (scale_connected) {
				await disconnect_scale();
				$(this).text("Conectar Báscula").removeClass("connected");
				$(".scale-status").removeClass("connected").attr("title", "Desconectada");
				$(".weigh-btn").hide();
				$(".pos-scale-weight-display").text("-- kg");
			} else {
				var success = await connect_scale();
				if (success) {
					$(this).text("Desconectar").addClass("connected");
					$(".scale-status").addClass("connected").attr("title", "Conectada");
					$(".weigh-btn").show();
				}
			}
		});

		// Event: Weigh (apply weight to cart)
		$(".weigh-btn").on("click", function () {
			apply_weight_to_cart();
		});

		// Keyboard shortcut: F9 to weigh
		$(document).on("keydown", function (e) {
			if (e.key === "F9" && scale_connected) {
				e.preventDefault();
				apply_weight_to_cart();
			}
		});
	}

	// Initialize when POS page loads
	if (is_serial_supported()) {
		setTimeout(inject_scale_ui, 2000);
	}
})();
