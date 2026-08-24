// POS customizations: barcode search + auto-focus + inline cart editing
// Loaded via page_js hook on the "point-of-sale" page

frappe.require("point-of-sale.bundle.js", function () {
	if (!erpnext.PointOfSale || !erpnext.PointOfSale.ItemSelector) return;

	var ItemSelector = erpnext.PointOfSale.ItemSelector;

	// 1. Override get_items to use our barcode-aware endpoint
	ItemSelector.prototype.get_items = function ({ start, page_length, search_term }) {
		start = start || 0;
		page_length = page_length || 40;
		search_term = search_term || "";

		var doc = this.events.get_frm().doc;
		var price_list = (doc && doc.selling_price_list) || this.price_list;
		var item_group = this.item_group;
		var pos_profile = this.pos_profile;

		return frappe.call({
			method: "facturacion_electronica.utils.pos_search.get_items_with_barcode_search",
			freeze: true,
			args: {
				start: start,
				page_length: page_length,
				price_list: price_list,
				item_group: item_group,
				search_term: search_term,
				pos_profile: pos_profile,
			},
		});
	};

	// 2. Refocus search input after auto-adding item to cart
	var original_add_filtered = ItemSelector.prototype.add_filtered_item_to_cart;
	ItemSelector.prototype.add_filtered_item_to_cart = function () {
		original_add_filtered.call(this);
		var me = this;
		setTimeout(function () {
			if (me.search_field && me.$component && me.$component.is(":visible")) {
				me.search_field.set_focus();
			}
		}, 200);
	};

	// 3. Override attach_shortcuts to refocus after Enter key adds an item
	var original_attach_shortcuts = ItemSelector.prototype.attach_shortcuts;
	ItemSelector.prototype.attach_shortcuts = function () {
		var me = this;
		var ctrl_label = frappe.utils.is_mac() ? "\u2318" : "Ctrl";

		this.search_field.parent.attr("title", ctrl_label + "+I");
		frappe.ui.keys.add_shortcut({
			shortcut: "ctrl+i",
			action: function () {
				me.search_field.set_focus();
			},
			condition: function () {
				return me.$component.is(":visible");
			},
			description: __("Focus on search input"),
			ignore_inputs: true,
			page: cur_page.page.page,
		});

		this.item_group_field.parent.attr("title", ctrl_label + "+G");
		frappe.ui.keys.add_shortcut({
			shortcut: "ctrl+g",
			action: function () {
				me.item_group_field.set_focus();
			},
			condition: function () {
				return me.$component.is(":visible");
			},
			description: __("Focus on Item Group filter"),
			ignore_inputs: true,
			page: cur_page.page.page,
		});

		frappe.ui.keys.on("enter", function () {
			var selector_is_visible = me.$component.is(":visible");
			if (!selector_is_visible || me.search_field.get_value() === "") return;

			if (me.items.length == 1) {
				me.$items_container.find(".item-wrapper").click();
				frappe.utils.play_sound("submit");
				me.set_search_value("");
				setTimeout(function () {
					if (me.$component.is(":visible")) me.search_field.set_focus();
				}, 200);
			} else if (me.items.length == 0 && me.barcode_scanned) {
				frappe.show_alert({
					message: __("No items found. Scan barcode again."),
					indicator: "orange",
				});
				frappe.utils.play_sound("error");
				me.barcode_scanned = false;
				me.set_search_value("");
				setTimeout(function () {
					if (me.$component.is(":visible")) me.search_field.set_focus();
				}, 200);
			}
		});
	};

	// 4. Auto-focus search input on POS page load
	function try_focus_search() {
		if (
			window.cur_pos &&
			window.cur_pos.item_selector &&
			window.cur_pos.item_selector.search_field
		) {
			if (
				window.cur_pos.item_selector.$component &&
				window.cur_pos.item_selector.$component.is(":visible")
			) {
				window.cur_pos.item_selector.search_field.set_focus();
				return true;
			}
		}
		return false;
	}

	var attempts = 0;
	var focus_interval = setInterval(function () {
		attempts++;
		if (try_focus_search() || attempts > 150) {
			clearInterval(focus_interval);
		}
	}, 200);

	// 5. Refocus search input when components are toggled on (e.g. "New Invoice")
	if (erpnext.PointOfSale.Controller) {
		var Controller = erpnext.PointOfSale.Controller;
		var original_toggle = Controller.prototype.toggle_components;
		Controller.prototype.toggle_components = function (show) {
			original_toggle.call(this, show);
			if (show) {
				var me = this;
				setTimeout(function () {
					if (
						me.item_selector &&
						me.item_selector.search_field &&
						me.item_selector.$component &&
						me.item_selector.$component.is(":visible")
					) {
						me.item_selector.search_field.set_focus();
					}
				}, 200);
			}
		};

		// ===================================================================
		// PATCH: Allow items with rate == 0 or undefined to be added to cart.
		//
		// ERPNext core (pos_controller.js) blocks adding an item to the cart
		// when its rate is 0 or undefined, showing "Price is not set for the
		// item." and returning early.  This prevents selling items that have
		// no price list entry or a price of $0.
		//
		// The check is inside update_item_field (core, line ~685):
		//   if (rate == undefined || rate == 0) { show_alert; return; }
		//
		// Our fix: override update_item_field so that when an item has no
		// rate we pass rate=0 to force-add it to the cart, bypassing the
		// early-return.  We do this by patching the item object before the
		// core executes the check.
		//
		// The backend accepts zero-rate items because our CustomPOSInvoice
		// .before_submit() sets allow_zero_valuation_rate=1 on every item
		// row before the stock ledger runs.
		// ===================================================================
		var _orig_update_item_field = Controller.prototype.update_item_field;
		Controller.prototype.update_item_field = async function (item, field_or_action, value) {
			// Only patch the "add new item to cart" path (item_row does NOT exist yet)
			if (field_or_action !== "checkout") {
				var item_row = this.get_item_from_frm ? this.get_item_from_frm(item) : null;
				var is_new_item = !(item_row && item_row.item_code);
				if (is_new_item && (item.rate == undefined || item.rate == 0)) {
					// Set rate to 0 explicitly so the core block fires but we set the
					// item up properly. We also need to neutralize the early-return block.
					// Strategy: replace the rate on the item object (which is what the core
					// destructures) with a tiny non-zero value is wrong. Instead, we
					// directly call our own add-to-cart logic for zero-rate items.
					if (!this.frm.doc.customer) return this.raise_customer_selection_alert();
					var { item_code, batch_no, serial_no, uom, stock_uom } = item;
					if (!item_code) return;

					// Add the item with rate=0 directly, bypassing core check
					var new_item = { item_code, batch_no, rate: 0, uom, [field_or_action]: value, stock_uom };
					if (serial_no) {
						await this.check_serial_no_availablilty(item_code, this.frm.doc.set_warehouse, serial_no);
						new_item["serial_no"] = serial_no;
					}
					new_item["use_serial_batch_fields"] = 1;
					new_item["warehouse"] = this.settings.warehouse;
					if (field_or_action === "serial_no") new_item["qty"] = value.split("\n").length || 0;

					var item_row_new = this.frm.add_child("items", new_item);

					if (field_or_action === "qty" && value !== 0 && !this.allow_negative_stock) {
						var qty_needed = value * item_row_new.conversion_factor;
						await this.check_stock_availability(item_row_new, qty_needed, this.frm.doc.set_warehouse);
					}

					await this.trigger_new_item_events(item_row_new);
					this.update_cart_html(item_row_new);

					if (this.item_details.$component.is(":visible")) this.edit_item_details_of(item_row_new);
					if (
						this.check_serial_batch_selection_needed(item_row_new) &&
						!this.item_details.$component.is(":visible")
					) {
						this.edit_item_details_of(item_row_new);
					}
					return;
				}
			}
			return _orig_update_item_field.call(this, item, field_or_action, value);
		};
	}

	// ===================================================================
	// 6. INLINE CART EDITING: qty input + delete button directly in cart
	// Uses MutationObserver to intercept cart renders reliably
	// ===================================================================

	// Inject CSS
	$("head").append(`
		<style>
			.cart-item-wrapper .inline-cart-controls {
				display: flex;
				align-items: center;
				gap: 4px;
				min-width: 90px;
			}
			.cart-item-wrapper .inline-qty-input {
				width: 50px;
				text-align: center;
				border: 1px solid var(--border-color);
				border-radius: 4px;
				padding: 2px 4px;
				font-size: 13px;
				font-weight: bold;
				background: var(--control-bg);
				color: var(--text-color);
			}
			.cart-item-wrapper .inline-qty-input:focus {
				border-color: var(--primary);
				outline: none;
				box-shadow: 0 0 0 1px var(--primary);
			}
			.cart-item-wrapper .inline-delete-btn {
				cursor: pointer;
				color: var(--red-500);
				font-size: 18px;
				font-weight: bold;
				padding: 2px 6px;
				line-height: 1;
				border-radius: 4px;
				opacity: 0.7;
				flex-shrink: 0;
			}
			.cart-item-wrapper .inline-delete-btn:hover {
				opacity: 1;
				background: var(--red-50);
			}
		</style>
	`);

	function enhance_cart_items() {
		$(".cart-item-wrapper").each(function () {
			var $item = $(this);
			var row_name = $item.attr("data-row-name");
			if (!row_name) return;

			// Skip if already enhanced
			if ($item.find(".inline-qty-input").length) return;

			var $qty_span = $item.find(".item-qty span");
			if (!$qty_span.length) return;

			// Parse current qty from text like "3 Unit"
			var qty_text = $qty_span.text().trim();
			var qty = parseFloat(qty_text) || 1;

			// Replace qty span with editable input
			$item.find(".item-qty").html(
				'<div class="inline-cart-controls">' +
					'<input type="number" class="inline-qty-input" data-row="' + row_name + '" value="' + qty + '" min="1" step="1">' +
				'</div>'
			);

			// Add delete button at the start of the item row
			if (!$item.find(".inline-delete-btn").length) {
				$item.prepend(
					'<span class="inline-delete-btn" data-row="' + row_name + '" title="Eliminar">&times;</span>'
				);
			}
		});
	}

	// Use MutationObserver to detect when cart items are rendered/updated
	function setup_cart_observer() {
		var $cart_section = $(".cart-items-section");
		if (!$cart_section.length) {
			// Retry until the cart section exists
			setTimeout(setup_cart_observer, 500);
			return;
		}

		// Enhance existing items
		enhance_cart_items();

		// Observe for new items being added/changed
		var observer = new MutationObserver(function () {
			enhance_cart_items();
		});
		observer.observe($cart_section[0], { childList: true, subtree: true, characterData: true });

		// Event delegation for qty change
		var qty_timeout = null;
		$cart_section.on("input", ".inline-qty-input", function (e) {
			e.stopPropagation();
			var $input = $(this);
			var row_name = $input.data("row");
			var new_qty = parseFloat($input.val());

			clearTimeout(qty_timeout);
			qty_timeout = setTimeout(function () {
				if (!new_qty || new_qty <= 0) {
					new_qty = 1;
					$input.val(1);
				}
				if (!window.cur_pos) return;
				var frm = window.cur_pos.frm;
				var item_row = frm.doc.items.find(function (i) { return i.name === row_name; });
				if (!item_row) return;

				frappe.model.set_value(item_row.doctype, item_row.name, "qty", new_qty)
					.then(function () {
						item_row = frm.doc.items.find(function (i) { return i.name === row_name; });
						if (item_row && window.cur_pos) {
							window.cur_pos.cart.update_totals_section(frm);
						}
					});
			}, 400);
		});

		// Event delegation for delete
		$cart_section.on("click", ".inline-delete-btn", function (e) {
			e.stopPropagation();
			var row_name = $(this).data("row");
			if (!window.cur_pos) return;
			var frm = window.cur_pos.frm;
			var item_row = frm.doc.items.find(function (i) { return i.name === row_name; });
			if (!item_row) return;

			frappe.dom.freeze();
			frappe.model.set_value(item_row.doctype, item_row.name, "qty", 0)
				.then(function () {
					frappe.model.clear_doc(item_row.doctype, item_row.name);
					window.cur_pos.update_cart_html(item_row, true);
					if (window.cur_pos.item_details) {
						window.cur_pos.item_details.toggle_item_details_section(null);
					}
					frappe.dom.unfreeze();
				})
				.catch(function () { frappe.dom.unfreeze(); });
		});

		// Prevent clicks on controls from opening item details panel
		$cart_section.on("click", ".inline-qty-input, .inline-delete-btn", function (e) {
			e.stopPropagation();
		});

		// Block cart-item click from opening details panel (only name click opens it)
		$cart_section.on("click", ".cart-item-wrapper", function (e) {
			if (!$(e.target).closest(".item-name").length) {
				e.stopImmediatePropagation();
			}
		});

		// Select all on focus
		$cart_section.on("focus", ".inline-qty-input", function () {
			$(this).select();
		});
	}

	// Start observing once the POS page is ready
	setTimeout(setup_cart_observer, 1000);
});


// =============================================================================
// 7. BOTON "PAGAR" en pedidos recientes para facturas pendientes de pago
// Reemplaza "Email Receipt" por "Pagar" cuando la factura está pendiente
// =============================================================================

frappe.require("point-of-sale.bundle.js", function () {
	if (!erpnext.PointOfSale || !erpnext.PointOfSale.PastOrderSummary) return;

	var PastOrderSummary = erpnext.PointOfSale.PastOrderSummary;

	// Override get_condition_btn_map to add "Pagar" button
	var original_get_map = PastOrderSummary.prototype.get_condition_btn_map;
	PastOrderSummary.prototype.get_condition_btn_map = function (after_submission) {
		if (after_submission) {
			return [{ condition: true, visible_btns: ["Print Receipt", "Email Receipt", "New Order"] }];
		}

		return [
			{ condition: this.doc.docstatus === 0, visible_btns: ["Edit Order", "Delete Order"] },
			{
				condition: ["Partly Paid", "Overdue", "Unpaid"].includes(this.doc.status),
				visible_btns: ["Print Receipt", "Pagar", "Open in Form View"],
			},
			{
				condition:
					!this.doc.is_return &&
					this.doc.docstatus === 1 &&
					!["Partly Paid", "Overdue", "Unpaid"].includes(this.doc.status),
				visible_btns: ["Print Receipt", "Email Receipt", "Return"],
			},
			{
				condition: this.doc.is_return && this.doc.docstatus === 1,
				visible_btns: ["Print Receipt", "Email Receipt"],
			},
		];
	};

	// Override bind_events to add "Pagar" button handler
	var original_bind = PastOrderSummary.prototype.bind_events;
	PastOrderSummary.prototype.bind_events = function () {
		original_bind.call(this);
		var me = this;

		this.$summary_container.on("click", ".pagar-btn", function () {
			if (!me.doc) return;

			var outstanding = me.doc.outstanding_amount || me.doc.grand_total;
			var doctype = me.doc.doctype;
			var docname = me.doc.name;

			// Create Payment Entry dialog directly in POS
			var d = new frappe.ui.Dialog({
				title: __("Registrar Pago") + " - " + docname,
				fields: [
					{
						fieldname: "mode_of_payment",
						fieldtype: "Link",
						options: "Mode of Payment",
						label: __("Modo de Pago"),
						reqd: 1,
						default: "Efectivo",
					},
					{
						fieldname: "amount",
						fieldtype: "Currency",
						label: __("Monto a Pagar"),
						reqd: 1,
						default: outstanding,
						description: __("Pendiente: ") + format_currency(outstanding, me.doc.currency),
					},
					{
						fieldname: "reference_date",
						fieldtype: "Date",
						label: __("Fecha"),
						default: frappe.datetime.get_today(),
						reqd: 1,
					},
				],
				primary_action_label: __("Pagar"),
				primary_action: function (values) {
					frappe.call({
						method: "erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry",
						args: {
							dt: doctype,
							dn: docname,
							party_amount: values.amount,
						},
						freeze: true,
						freeze_message: __("Creando pago..."),
						callback: function (r) {
							if (r.message) {
								var pe = r.message;
								pe.mode_of_payment = values.mode_of_payment;
								pe.reference_date = values.reference_date;
								pe.paid_amount = values.amount;
								pe.received_amount = values.amount;

								// Save and submit the payment entry
								frappe.call({
									method: "frappe.client.save",
									args: { doc: pe },
									freeze: true,
									callback: function (save_r) {
										if (save_r.message) {
											frappe.call({
												method: "frappe.client.submit",
												args: { doc: save_r.message },
												freeze: true,
												callback: function (submit_r) {
													if (submit_r.message) {
														d.hide();
														frappe.show_alert({
															message: __("Pago registrado: {0}", [submit_r.message.name]),
															indicator: "green",
														}, 5);
														frappe.utils.play_sound("submit");
														// Reload the order summary
														me.load_summary_of(me.doc);
													}
												},
											});
										}
									},
								});
							}
						},
					});
				},
			});
			d.show();
		});
	};
});



// =============================================================================
// 8. SKIP SUBMIT CONFIRMATION + CART ITEMS NEWEST ON TOP
// =============================================================================

frappe.require("point-of-sale.bundle.js", function () {
	if (!erpnext.PointOfSale || !erpnext.PointOfSale.Controller) return;

	var Controller = erpnext.PointOfSale.Controller;

	// Override init_payments to skip the submit confirmation dialog
	var original_init_payments = Controller.prototype.init_payments;
	Controller.prototype.init_payments = function () {
		original_init_payments.call(this);

		// Replace the submit_invoice event to skip confirmation
		if (this.payment && this.payment.events) {
			var me = this;
			this.payment.events.submit_invoice = function () {
				// Save first, then submit without confirmation
				me.frm.save().then(function () {
					frappe.xcall("frappe.client.submit", { doc: me.frm.doc }).then(function (r) {
						me.frm.doc = r;
						me.frm.dirty(false);
						me.toggle_components(false);
						me.toggle_submitted_invoice_summary(true);
						frappe.show_alert({
							indicator: "green",
							message: __("POS invoice {0} created successfully", [r.name]),
						});
					});
				});
			};
		}
	};

	// Override update_cart_html to prepend new items instead of append
	var ItemCart = erpnext.PointOfSale.ItemCart;
	if (ItemCart) {
		var original_render_cart_item = ItemCart.prototype.render_cart_item;
		ItemCart.prototype.render_cart_item = function (item_data, $item_to_update) {
			if (!$item_to_update.length) {
				// New item: prepend instead of append
				this.$cart_items_wrapper.prepend(
					'<div class="cart-item-wrapper" data-row-name="' +
						frappe.utils.escape_html(item_data.name) +
						'"></div><div class="seperator"></div>'
				);
				$item_to_update = this.get_cart_item(item_data);
			}
			// Call original render with the positioned element
			original_render_cart_item.call(this, item_data, $item_to_update);

			// Show the line TOTAL (precio unitario * cantidad) for every product.
			// ERPNext only prints the total when item.amount != item.rate; we
			// recompute it directly from qty * rate so it ALWAYS appears, e.g.
			//   $ 20.000,00      (total)
			//   $ 4.000,00 x 5   (precio unitario x cantidad)
			var frm = this.events.get_frm();
			var currency = frm.doc.currency;
			this.$cart_items_wrapper.find(".cart-item-wrapper").each(function () {
				var $w = $(this);
				var row_name = $w.attr("data-row-name");
				var item = frm.doc.items.find(function (r) { return r.name === row_name; });
				if (!item) return;

				var qty = flt(item.qty);
				var rate = flt(item.rate);
				var total = qty * rate;

				var $rate = $w.find(".item-rate-amount .item-rate");
				var $amount = $w.find(".item-rate-amount .item-amount");
				if ($rate.length) {
					$rate.html(format_currency(total, currency));
				}
				if ($amount.length) {
					$amount.html(format_currency(rate, currency) + " x " + qty);
				}
			});

			// Realign the price column after the content changes
			var $all = this.$cart_items_wrapper.find(".item-rate-amount");
			this.$cart_header.find(".rate-amount-header").css("width", "");
			$all.css("width", "");
			var max_w = 0;
			$all.each(function () {
				max_w = Math.max(max_w, $(this).width());
			});
			max_w += 1;
			if (max_w > 1) {
				this.$cart_header.find(".rate-amount-header").css("width", max_w);
				$all.css("width", max_w);
			}
		};
	}
});



// =============================================================================
// 9. DISABLE OUTDATED POS OPENING ENTRY CHECK
// Allows the cash register to stay open across midnight
// =============================================================================

// Patch immediately without waiting for bundle (it may already be loaded)
(function() {
	function disable_outdated_check() {
		if (erpnext && erpnext.PointOfSale && erpnext.PointOfSale.Controller) {
			erpnext.PointOfSale.Controller.prototype.check_outdated_pos_opening_entry = function () {};
			return true;
		}
		return false;
	}
	// Try immediately
	if (!disable_outdated_check()) {
		// Retry every 200ms until available
		var attempts = 0;
		var interval = setInterval(function() {
			if (disable_outdated_check() || attempts > 50) clearInterval(interval);
			attempts++;
		}, 200);
	}
	// Also override after require in case it loads later
	frappe.require("point-of-sale.bundle.js", function () {
		disable_outdated_check();
	});
})();
