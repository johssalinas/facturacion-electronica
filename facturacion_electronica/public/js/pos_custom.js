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
	}

	// ===================================================================
	// 6. INLINE CART EDITING: qty input + delete button directly in cart
	// ===================================================================
	if (erpnext.PointOfSale.ItemCart) {
		var ItemCart = erpnext.PointOfSale.ItemCart;

		// Inject CSS for inline cart controls
		var cart_css = `
			<style>
				.cart-item-wrapper .inline-cart-controls {
					display: flex;
					align-items: center;
					gap: 4px;
					min-width: 100px;
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
					font-size: 16px;
					font-weight: bold;
					padding: 0 6px;
					line-height: 1;
					border-radius: 4px;
					opacity: 0.7;
				}
				.cart-item-wrapper .inline-delete-btn:hover {
					opacity: 1;
					background: var(--red-50);
				}
				.cart-item-wrapper .item-qty-rate {
					display: flex;
					align-items: center;
					gap: 8px;
				}
			</style>
		`;
		$("head").append(cart_css);

		// Override render_cart_item to add inline controls
		var original_render = ItemCart.prototype.render_cart_item;
		ItemCart.prototype.render_cart_item = function (item_data, $item_to_update) {
			// Call original render first
			original_render.call(this, item_data, $item_to_update);

			// Now replace the qty display with an inline input + delete button
			var $item = $item_to_update.length ? $item_to_update : this.get_cart_item(item_data);
			if (!$item || !$item.length) return;

			var $qty_div = $item.find(".item-qty");
			if (!$qty_div.length) return;

			var qty = item_data.qty || 0;
			var row_name = $item.attr("data-row-name");

			// Replace qty text with input + delete button
			$qty_div.html(
				'<div class="inline-cart-controls">' +
					'<span class="inline-delete-btn" data-row="' + row_name + '" title="Eliminar">&times;</span>' +
					'<input type="number" class="inline-qty-input" data-row="' + row_name + '" value="' + qty + '" min="0" step="1">' +
				'</div>'
			);
		};

		// Override make_cart_items_section to add event handlers for inline controls
		var original_make = ItemCart.prototype.make_cart_items_section;
		ItemCart.prototype.make_cart_items_section = function () {
			original_make.call(this);
			var me = this;

			// Handle qty input change
			this.$cart_items_wrapper.on("change", ".inline-qty-input", function (e) {
				e.stopPropagation();
				var row_name = $(this).data("row");
				var new_qty = flt($(this).val());
				var frm = me.events.get_frm();

				if (new_qty <= 0) {
					// Remove item
					frappe.model.set_value("POS Invoice Item", row_name, "qty", 0).then(function () {
						frappe.model.clear_doc("POS Invoice Item", row_name);
						var item_row = frm.doc.items.find(function (i) { return i.name === row_name; });
						if (window.cur_pos) {
							window.cur_pos.update_cart_html(item_row || { name: row_name }, true);
						}
					});
				} else {
					frappe.model.set_value("POS Invoice Item", row_name, "qty", new_qty).then(function () {
						var item_row = frm.doc.items.find(function (i) { return i.name === row_name; });
						if (window.cur_pos && item_row) {
							window.cur_pos.update_cart_html(item_row);
						}
					});
				}
			});

			// Handle delete button click
			this.$cart_items_wrapper.on("click", ".inline-delete-btn", function (e) {
				e.stopPropagation();
				var row_name = $(this).data("row");
				var frm = me.events.get_frm();

				frappe.model.set_value("POS Invoice Item", row_name, "qty", 0).then(function () {
					frappe.model.clear_doc("POS Invoice Item", row_name);
					var item_row = frm.doc.items.find(function (i) { return i.name === row_name; });
					if (window.cur_pos) {
						window.cur_pos.update_cart_html(item_row || { name: row_name }, true);
					}
				});
			});

			// Prevent click on input/delete from triggering cart_item_clicked (opening details panel)
			this.$cart_items_wrapper.on("click", ".inline-qty-input, .inline-delete-btn", function (e) {
				e.stopPropagation();
			});

			// Select all text on focus for quick typing
			this.$cart_items_wrapper.on("focus", ".inline-qty-input", function () {
				$(this).select();
			});
		};
	}
});
