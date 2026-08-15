# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FuelTank(Document):
	pass


@frappe.whitelist()
def get_stock_level(tank_name):
	"""Live stock qty and valuation rate from ERPNext's own Bin (stock
	balance) doctype — deliberately not stored redundantly on Fuel Tank
	itself, so it can never go stale."""
	tank = frappe.get_doc("Fuel Tank", tank_name)
	bin_data = frappe.db.get_value(
		"Bin",
		{"item_code": tank.fuel_item, "warehouse": tank.warehouse},
		["actual_qty", "valuation_rate"],
		as_dict=True,
	)
	if not bin_data:
		return {"actual_qty": 0, "valuation_rate": 0}
	return {
		"actual_qty": bin_data.actual_qty or 0,
		"valuation_rate": bin_data.valuation_rate or 0,
	}
