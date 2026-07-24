import frappe
from frappe.query_builder import DocType, Order
from frappe.utils import cint, today
from frappe.utils.nestedset import get_root_of


@frappe.whitelist()
def get_items_with_barcode_search(
	start, page_length, price_list, item_group, pos_profile, search_term=""
):
	"""POS get_items wrapper that also searches by barcode (partial match).

	First calls the standard ERPNext get_items (which handles exact barcode
	match via scan_barcode, plus item_code/item_name LIKE search), then
	supplements with items whose barcode partially matches the search term.
	"""
	from erpnext.selling.page.point_of_sale.point_of_sale import (
		get_items as _original_get_items,
	)

	result = _original_get_items(
		start, page_length, price_list, item_group, pos_profile, search_term
	)

	if not result or isinstance(result, list):
		result = {"items": []}

	items = result.get("items", [])

	if search_term:
		existing_codes = {item.get("item_code") for item in items}
		barcode_items = _search_items_by_barcode(
			search_term, price_list, pos_profile, item_group, existing_codes
		)
		if barcode_items:
			items.extend(barcode_items)
			result["items"] = items

	return result


def _search_items_by_barcode(search_term, price_list, pos_profile, item_group, existing_codes):
	"""Search items by barcode (partial LIKE match) and return full item data.

	Returns items in the same format as the standard POS get_items so the
	frontend can render them without modification.
	"""
	from erpnext.accounts.doctype.pos_invoice.pos_invoice import get_stock_availability
	from erpnext.stock.get_item_details import get_conversion_factor
	from erpnext.selling.page.point_of_sale.point_of_sale import get_item_group_condition

	warehouse, hide_unavailable_items = frappe.db.get_value(
		"POS Profile", pos_profile, ["warehouse", "hide_unavailable_items"]
	)

	if not frappe.db.exists("Item Group", item_group):
		item_group = get_root_of("Item Group")

	lft, rgt = frappe.db.get_value("Item Group", item_group, ["lft", "rgt"])

	bin_join_selection = ""
	bin_join_condition = ""
	if hide_unavailable_items:
		bin_join_selection = "LEFT JOIN `tabBin` bin ON bin.item_code = item.name"
		bin_join_condition = (
			"AND (item.is_stock_item = 0 OR "
			"(item.is_stock_item = 1 AND bin.warehouse = %(warehouse)s AND bin.actual_qty > 0))"
		)

	items_data = frappe.db.sql(
		"""
		SELECT DISTINCT
			item.name AS item_code,
			item.item_name,
			item.description,
			item.stock_uom,
			item.image AS item_image,
			item.is_stock_item,
			item.sales_uom
		FROM `tabItem` item
		INNER JOIN `tabItem Barcode` barb ON barb.parent = item.name
		{bin_join_selection}
		WHERE item.disabled = 0
			AND item.has_variants = 0
			AND item.is_sales_item = 1
			AND item.is_fixed_asset = 0
			AND barb.barcode LIKE %(search_term)s
			AND item.item_group in (SELECT name FROM `tabItem Group` WHERE lft >= {lft} AND rgt <= {rgt})
			{item_group_condition}
			{bin_join_condition}
		LIMIT 40
		""".format(
			lft=cint(lft),
			rgt=cint(rgt),
			item_group_condition=get_item_group_condition(pos_profile),
			bin_join_selection=bin_join_selection,
			bin_join_condition=bin_join_condition,
		),
		{"search_term": "%" + search_term + "%", "warehouse": warehouse},
		as_dict=1,
	)

	if not items_data:
		return []

	items_data = [item for item in items_data if item["item_code"] not in existing_codes]
	if not items_data:
		return []

	current_date = today()
	result = []

	for item in items_data:
		item.actual_qty, _, _ = get_stock_availability(item.item_code, warehouse)

		ItemPrice = DocType("Item Price")
		item_prices = (
			frappe.qb.from_(ItemPrice)
			.select(
				ItemPrice.price_list_rate,
				ItemPrice.currency,
				ItemPrice.uom,
				ItemPrice.batch_no,
				ItemPrice.valid_from,
				ItemPrice.valid_upto,
			)
			.where(ItemPrice.price_list == price_list)
			.where(ItemPrice.item_code == item.item_code)
			.where(ItemPrice.selling == 1)
			.where((ItemPrice.valid_from <= current_date) | (ItemPrice.valid_from.isnull()))
			.where((ItemPrice.valid_upto >= current_date) | (ItemPrice.valid_upto.isnull()))
			.orderby(ItemPrice.valid_from, order=Order.desc)
		).run(as_dict=True)

		stock_uom_price = next((d for d in item_prices if d.get("uom") == item.stock_uom), {})
		item_uom = item.stock_uom
		item_uom_price = stock_uom_price

		if item.sales_uom and item.sales_uom != item.stock_uom:
			item_uom = item.sales_uom
			sales_uom_price = next((d for d in item_prices if d.get("uom") == item.sales_uom), {})
			if sales_uom_price:
				item_uom_price = sales_uom_price

		if item_prices and not item_uom_price:
			item_uom = item_prices[0].get("uom")
			item_uom_price = item_prices[0]

		item_conversion_factor = get_conversion_factor(item.item_code, item_uom).get("conversion_factor")

		if item.stock_uom != item_uom:
			item.actual_qty = item.actual_qty // item_conversion_factor

		if item_uom_price and item_uom != item_uom_price.get("uom"):
			item_uom_price.price_list_rate = item_uom_price.price_list_rate * item_conversion_factor

		result.append(
			{
				**item,
				"price_list_rate": item_uom_price.get("price_list_rate"),
				"currency": item_uom_price.get("currency"),
				"uom": item_uom,
				"batch_no": item_uom_price.get("batch_no"),
			}
		)

	return result
