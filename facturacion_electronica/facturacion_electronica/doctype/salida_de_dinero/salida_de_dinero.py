# -*- coding: utf-8 -*-
# Copyright (c) 2026, Salsamentaria and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document


class SalidaDeDinero(Document):
	def autoname(self):
		self.name = self.make_autoname(self.naming_series)

	def validate(self):
		if self.amount <= 0:
			frappe.throw(_("El monto debe ser mayor a cero."))

		# Sanity: the opening entry must exist
		if not frappe.db.exists("POS Opening Entry", self.pos_opening_entry):
			frappe.throw(_("La apertura de caja seleccionada no existe."))

	def get_company(self):
		return frappe.db.get_value("POS Opening Entry", self.pos_opening_entry, "company")

	def get_pos_profile(self):
		return frappe.db.get_value("POS Opening Entry", self.pos_opening_entry, "pos_profile")

	def on_submit(self):
		self.status = "Submitted"
		if self.create_accounting_entry and not self.journal_entry:
			self.journal_entry = self.make_journal_entry()
		self.db_set("status", "Submitted")
		self.db_set("journal_entry", self.journal_entry)

	def on_cancel(self):
		self.status = "Cancelled"
		# Cancel the linked journal entry if it exists and is not yet cancelled
		if self.journal_entry and frappe.db.exists("Journal Entry", self.journal_entry):
			je = frappe.get_doc("Journal Entry", self.journal_entry)
			if je.docstatus == 1:
				je.cancel()
		self.db_set("status", "Cancelled")

	def get_cash_account(self):
		"""Return the cash/bank account for the selected mode of payment."""
		company = self.get_company()
		pos_profile = self.get_pos_profile()

		# 1) From the POS Profile payment method mapping
		account = frappe.db.get_value(
			"POS Payment Method",
			{"parent": pos_profile, "mode_of_payment": self.mode_of_payment},
			"default_account",
		)
		if account:
			return account

		# 2) From the Mode of Payment accounts (per company)
		account = frappe.db.get_value(
			"Mode of Payment Account",
			{"parent": self.mode_of_payment, "company": company},
			"default_account",
		)
		if account:
			return account

		# 3) Fallback: company default cash account
		account = frappe.db.get_value("Company", company, "default_cash_account")
		if account:
			return account

		frappe.throw(
			_("No se encontro cuenta de caja para el modo de pago {0} en la compania {1}.").format(
				frappe.bold(self.mode_of_payment), frappe.bold(company)
			)
		)

	def get_debit_account(self):
		"""Return the account to debit.

		- If a Supplier/Customer/Employee is selected, use the party account
		  (payable/receivable/employee payable).
		- Otherwise use debit_account if set, else the company default expense.
		"""
		company = self.get_company()

		if self.party_type and self.party:
			try:
				from erpnext.accounts.party import get_party_account

				return get_party_account(self.party_type, self.party, company)
			except Exception:
				pass

		if self.debit_account:
			return self.debit_account

		account = frappe.db.get_value("Company", company, "default_expense_account")
		if account:
			return account

		frappe.throw(_("No se encontro cuenta para debitar la salida de dinero."))

	def make_journal_entry(self):
		company = self.get_company()
		cash_account = self.get_cash_account()
		debit_account = self.get_debit_account()
		remarks = "Salida de Dinero {0}".format(self.name)
		if self.description:
			remarks += " - {0}".format(self.description)

		debit_row = {
			"account": debit_account,
			"debit_in_account_currency": self.amount,
			"cost_center": self.get_cost_center(),
		}
		# Party-linked accounts (payable/receivable) require the party reference
		if self.party_type and self.party:
			debit_row["party_type"] = self.party_type
			debit_row["party"] = self.party

		je = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"voucher_type": "Journal Entry",
				"posting_date": self.posting_date or frappe.utils.today(),
				"company": company,
				"remark": remarks,
				"user_remark": remarks,
				"accounts": [
					debit_row,
					{
						"account": cash_account,
						"credit_in_account_currency": self.amount,
						"cost_center": self.get_cost_center(),
					},
				],
			}
		)
		# The cashier may not have Journal Entry permissions; the accounting
		# entry is created on their behalf.
		je.flags.ignore_permissions = True
		je.insert()
		je.submit()
		return je.name

	def get_cost_center(self):
		pos_profile = self.get_pos_profile()
		cost_center = frappe.db.get_value("POS Profile", pos_profile, "cost_center")
		if not cost_center:
			cost_center = frappe.db.get_value("Company", self.get_company(), "cost_center")
		return cost_center
