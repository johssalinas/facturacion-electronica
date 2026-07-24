// POS customizations: barcode search + auto-focus on search input
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
});
