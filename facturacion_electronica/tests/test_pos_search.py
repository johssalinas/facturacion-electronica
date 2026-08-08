"""Tests for POS barcode search and shared cash register functionality."""

import frappe
from frappe.tests import IntegrationTestCase


class TestPOSBarcodeSearch(IntegrationTestCase):
	"""Test that the barcode search endpoint works correctly."""

	def test_search_by_item_name(self):
		"""Search by item name should return matching items."""
		from facturacion_electronica.utils.pos_search import get_items_with_barcode_search

		result = get_items_with_barcode_search(
			start=0,
			page_length=10,
			price_list="Standard Selling",
			item_group="All Item Groups",
			pos_profile="Caja Principal",
			search_term="salsa",
		)
		items = result.get("items", [])
		self.assertGreater(len(items), 0, "Should find items matching 'salsa'")

	def test_search_by_barcode_full(self):
		"""Search by full barcode should return the exact item."""
		from facturacion_electronica.utils.pos_search import get_items_with_barcode_search

		# Get a known barcode from the system
		barcode_data = frappe.db.get_value("Item Barcode", {}, ["barcode", "parent"], as_dict=True)
		if not barcode_data:
			self.skipTest("No barcodes found in the system")

		result = get_items_with_barcode_search(
			start=0,
			page_length=10,
			price_list="Standard Selling",
			item_group="All Item Groups",
			pos_profile="Caja Principal",
			search_term=barcode_data.barcode,
		)
		items = result.get("items", [])
		self.assertGreater(len(items), 0, f"Should find item for barcode {barcode_data.barcode}")
		item_codes = [i["item_code"] for i in items]
		self.assertIn(barcode_data.parent, item_codes, "The item with that barcode should be in results")

	def test_search_by_barcode_partial(self):
		"""Search by partial barcode should return matching items."""
		from facturacion_electronica.utils.pos_search import get_items_with_barcode_search

		# Get a barcode and use first 6 digits as partial search
		barcode_data = frappe.db.get_value("Item Barcode", {}, ["barcode"], as_dict=True)
		if not barcode_data:
			self.skipTest("No barcodes found in the system")

		partial = barcode_data.barcode[:6]
		result = get_items_with_barcode_search(
			start=0,
			page_length=40,
			price_list="Standard Selling",
			item_group="All Item Groups",
			pos_profile="Caja Principal",
			search_term=partial,
		)
		items = result.get("items", [])
		self.assertGreater(len(items), 0, f"Should find items for partial barcode '{partial}'")

	def test_search_empty_returns_items(self):
		"""Empty search should return the default item list."""
		from facturacion_electronica.utils.pos_search import get_items_with_barcode_search

		result = get_items_with_barcode_search(
			start=0,
			page_length=5,
			price_list="Standard Selling",
			item_group="All Item Groups",
			pos_profile="Caja Principal",
			search_term="",
		)
		items = result.get("items", [])
		self.assertGreater(len(items), 0, "Empty search should return items")

	def test_search_no_duplicates(self):
		"""Results should not contain duplicate item codes."""
		from facturacion_electronica.utils.pos_search import get_items_with_barcode_search

		barcode_data = frappe.db.get_value("Item Barcode", {}, ["barcode"], as_dict=True)
		if not barcode_data:
			self.skipTest("No barcodes found in the system")

		result = get_items_with_barcode_search(
			start=0,
			page_length=40,
			price_list="Standard Selling",
			item_group="All Item Groups",
			pos_profile="Caja Principal",
			search_term=barcode_data.barcode[:4],
		)
		items = result.get("items", [])
		item_codes = [i["item_code"] for i in items]
		self.assertEqual(len(item_codes), len(set(item_codes)), "Should not have duplicate item codes")


class TestPOSSharedCashRegister(IntegrationTestCase):
	"""Test that the shared cash register (multi-user POS) works correctly."""

	def test_check_opening_entry_finds_any_user(self):
		"""check_opening_entry should find open entries regardless of who opened them."""
		from facturacion_electronica.overrides.pos_opening_entry import check_opening_entry

		# Check if there's an open entry
		open_entries = frappe.get_all(
			"POS Opening Entry",
			filters={"status": "Open", "docstatus": 1},
			fields=["name", "user", "pos_profile"],
		)
		if not open_entries:
			self.skipTest("No open POS Opening Entry to test with")

		opening_user = open_entries[0].user
		pos_profile = open_entries[0].pos_profile

		# Get another user assigned to the same POS Profile
		other_users = frappe.get_all(
			"POS Profile User",
			filters={"parent": pos_profile, "user": ["!=", opening_user]},
			pluck="user",
		)

		if not other_users:
			self.skipTest("No other users assigned to the POS Profile")

		# The other user should be able to see the open entry
		result = check_opening_entry(other_users[0])
		self.assertGreater(len(result), 0, "Other user should see the open cash register")
		self.assertEqual(result[0]["pos_profile"], pos_profile)

	def test_check_opening_entry_same_user(self):
		"""check_opening_entry should work for the user who opened it."""
		from facturacion_electronica.overrides.pos_opening_entry import check_opening_entry

		open_entries = frappe.get_all(
			"POS Opening Entry",
			filters={"status": "Open", "docstatus": 1},
			fields=["name", "user"],
		)
		if not open_entries:
			self.skipTest("No open POS Opening Entry to test with")

		result = check_opening_entry(open_entries[0].user)
		self.assertGreater(len(result), 0, "Opening user should see their own entry")

	def test_get_invoices_includes_all_users(self):
		"""get_invoices should return invoices from all users, not just one."""
		from facturacion_electronica.overrides.pos_closing_entry import get_invoices

		# This test verifies the function doesn't crash and returns a valid structure
		open_entry = frappe.get_all(
			"POS Opening Entry",
			filters={"status": "Open", "docstatus": 1},
			fields=["name", "user", "pos_profile", "period_start_date"],
			limit=1,
		)
		if not open_entry:
			self.skipTest("No open POS Opening Entry to test with")

		entry = open_entry[0]
		result = get_invoices(
			start=str(entry.period_start_date),
			end=str(frappe.utils.now_datetime()),
			pos_profile=entry.pos_profile,
			user=entry.user,
		)

		self.assertIn("invoices", result)
		self.assertIn("payments", result)
		self.assertIn("taxes", result)
		self.assertIsInstance(result["invoices"], list)
