# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class TruckFuelLog(Document):
	def validate(self):
		validate_reason_for_fuelling(self)
		set_computed_fields(self)


def validate_reason_for_fuelling(doc):
	"""If fuelling is for a trip, the Authority to Load for that trip must be attached
	and must check out (right truck, right trip, submitted, all checks passed)."""
	if doc.reason_for_fuelling != "For Trip":
		return

	if not doc.truck_trip:
		frappe.throw("Truck Trip is required when Reason for Fuelling is 'For Trip'.")

	if not doc.authority_to_load:
		frappe.throw(
			"Please attach the Authority to Load for this trip. "
			"Fuelling for a trip is not allowed without an approved Authority to Load."
		)

	atl = frappe.db.get_value(
		"Authority to Load",
		doc.authority_to_load,
		["truck", "truck_trip", "docstatus", "all_checks_passed"],
		as_dict=True,
	)

	if not atl:
		frappe.throw(f"Authority to Load {doc.authority_to_load} not found.")

	if atl.truck != doc.truck:
		frappe.throw(
			f"Authority to Load {doc.authority_to_load} was issued for truck {atl.truck}, "
			f"not {doc.truck}."
		)

	if atl.truck_trip != doc.truck_trip:
		frappe.throw(
			f"Authority to Load {doc.authority_to_load} was issued for Truck Trip "
			f"{atl.truck_trip}, not {doc.truck_trip}."
		)

	if atl.docstatus != 1:
		frappe.throw(f"Authority to Load {doc.authority_to_load} must be submitted before it can be attached.")

	if not atl.all_checks_passed:
		frappe.throw(
			f"Authority to Load {doc.authority_to_load} did not pass all compliance checks "
			"and cannot be used to authorize fuelling for this trip."
		)


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


def notify_driver_fuel_confirmation(doc, method=None):
	"""Fires on_submit. Confirms to the driver what was fuelled, for their
	own record — most useful for 'For Trip' fuelling, but sent regardless
	of reason since any driver present at the pump likely wants the
	confirmation."""
	if not doc.driver:
		return

	settings = frappe.get_cached_doc("Transport Logistics Settings")
	if not (settings.enable_whatsapp and settings.whatsapp_notify_driver):
		return

	cell_number = frappe.db.get_value("Employee", doc.driver, "cell_number")
	if not cell_number:
		return

	from transport_logistics.transport_logistics.whatsapp import send_whatsapp_message

	message = (
		f"Fuel log {doc.name} confirmed — {doc.fuel_qty_litres} litres for Truck {doc.truck}"
		f"{' (' + doc.reason_for_fuelling + ')' if doc.reason_for_fuelling else ''}. "
		f"Total: {doc.total_amount}."
	)
	send_whatsapp_message(
		cell_number, message, reference_doctype="Truck Fuel Log", reference_name=doc.name, settings=settings
	)


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
