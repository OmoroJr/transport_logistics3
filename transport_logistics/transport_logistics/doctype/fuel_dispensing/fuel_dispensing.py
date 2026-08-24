# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class FuelDispensing(Document):
	def validate(self):
		check_tank_stock(self)


def check_tank_stock(doc):
	tank = frappe.get_doc("Fuel Tank", doc.tank)
	available = frappe.db.get_value(
		"Bin", {"item_code": tank.fuel_item, "warehouse": tank.warehouse}, "actual_qty"
	) or 0
	if flt(doc.qty_litres) > flt(available):
		frappe.throw(
			f"Not enough fuel in tank {doc.tank}: {flt(available, 1)} L available, "
			f"{flt(doc.qty_litres, 1)} L requested. Record a Bulk Fuel Purchase first."
		)


def check_stock_and_issue(doc, method=None):
	tank = frappe.get_doc("Fuel Tank", doc.tank)

	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Issue"
	se.company = doc.company
	se.posting_date = doc.date
	se.append("items", {
		"item_code": tank.fuel_item,
		"qty": doc.qty_litres,
		"s_warehouse": tank.warehouse,
	})
	se.insert(ignore_permissions=True)
	se.submit()

	se.reload()
	valuation_rate = flt(se.items[0].basic_rate) if se.items else 0

	doc.db_set("stock_entry", se.name, update_modified=False)
	doc.db_set("valuation_rate", valuation_rate, update_modified=False)
	doc.db_set("total_amount", valuation_rate * flt(doc.qty_litres), update_modified=False)

	log = frappe.new_doc("Truck Fuel Log")
	log.truck = doc.truck
	log.company = doc.company
	log.date = doc.date
	log.odometer_reading = doc.odometer_reading
	log.fuel_qty_litres = doc.qty_litres
	log.rate_per_litre = valuation_rate
	log.full_tank = doc.full_tank
	log.fuel_station = f"Internal Bulk Tank: {tank.tank_name}"
	log.source = "Internal Bulk Dispensing"
	log.fuel_dispensing = doc.name
	log.reason_for_fuelling = doc.get("reason_for_fuelling") or "Yard / Standby"
	log.truck_trip = doc.get("truck_trip")
	log.authority_to_load = doc.get("authority_to_load")
	log.insert(ignore_permissions=True)
	log.submit()

	doc.db_set("truck_fuel_log", log.name, update_modified=False)


def on_cancel_actions(doc, method=None):
	if doc.truck_fuel_log and frappe.db.exists("Truck Fuel Log", doc.truck_fuel_log):
		log = frappe.get_doc("Truck Fuel Log", doc.truck_fuel_log)
		if log.docstatus == 1:
			log.cancel()

	if doc.stock_entry and frappe.db.exists("Stock Entry", doc.stock_entry):
		se = frappe.get_doc("Stock Entry", doc.stock_entry)
		if se.docstatus == 1:
			se.cancel()
