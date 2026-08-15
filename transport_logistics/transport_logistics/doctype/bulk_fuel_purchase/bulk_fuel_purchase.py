# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class BulkFuelPurchase(Document):
	def validate(self):
		self.total_amount = flt(self.qty_litres) * flt(self.rate_per_litre)


def create_stock_receipt(doc, method=None):
	create_receipt_stock_entry(doc)


def create_receipt_stock_entry(doc):
	tank = frappe.get_doc("Fuel Tank", doc.tank)

	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Receipt"
	se.company = doc.company
	se.posting_date = doc.date
	se.append("items", {
		"item_code": tank.fuel_item,
		"qty": doc.qty_litres,
		"t_warehouse": tank.warehouse,
		"basic_rate": doc.rate_per_litre,
	})
	se.insert(ignore_permissions=True)
	se.submit()

	doc.db_set("stock_entry", se.name, update_modified=False)


def cancel_stock_receipt(doc, method=None):
	if doc.stock_entry and frappe.db.exists("Stock Entry", doc.stock_entry):
		se = frappe.get_doc("Stock Entry", doc.stock_entry)
		if se.docstatus == 1:
			se.cancel()
