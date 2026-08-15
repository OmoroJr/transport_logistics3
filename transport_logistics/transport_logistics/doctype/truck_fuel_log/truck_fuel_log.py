# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class TruckFuelLog(Document):
	def validate(self):
		set_computed_fields(self)


def set_computed_fields(doc, method=None):
	"""Compute previous odometer, distance covered, amount and efficiency."""
	previous = frappe.db.sql(
		"""
		select odometer_reading
		from `tabTruck Fuel Log`
		where truck = %s and docstatus = 1 and name != %s
		and (date < %s or (date = %s and creation < %s))
		order by date desc, creation desc
		limit 1
		""",
		(doc.truck, doc.name or "", doc.date, doc.date, doc.creation or frappe.utils.now()),
	)
	doc.previous_odometer = previous[0][0] if previous else 0

	if doc.odometer_reading and doc.previous_odometer:
		if doc.odometer_reading < doc.previous_odometer:
			frappe.throw(
				f"Odometer Reading ({doc.odometer_reading}) cannot be less than "
				f"the previous recorded reading ({doc.previous_odometer}) for this truck."
			)
		doc.distance_covered = doc.odometer_reading - doc.previous_odometer
	else:
		doc.distance_covered = 0

	doc.total_amount = (doc.fuel_qty_litres or 0) * (doc.rate_per_litre or 0)

	if doc.full_tank and doc.distance_covered and doc.fuel_qty_litres:
		doc.fuel_efficiency_km_per_litre = doc.distance_covered / doc.fuel_qty_litres
	else:
		doc.fuel_efficiency_km_per_litre = 0


def update_truck_odometer(doc, method=None):
	"""Keep Truck.current_odometer in sync with the latest submitted fuel log."""
	truck = frappe.get_doc("Truck", doc.truck)
	latest = frappe.db.sql(
		"""
		select max(odometer_reading) from `tabTruck Fuel Log`
		where truck = %s and docstatus = 1
		""",
		(doc.truck,),
	)[0][0]
	truck.db_set("current_odometer", latest or 0, update_modified=False)
