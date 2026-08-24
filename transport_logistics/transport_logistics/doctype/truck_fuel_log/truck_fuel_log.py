# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from transport_logistics.transport_logistics.manager_approval import (
	block_submit_if_not_approved,
	flag_pending_approval,
)


class TruckFuelLog(Document):
	def validate(self):
		validate_source_requires_dispensing(self)
		validate_reason_for_fuelling(self)
		set_computed_fields(self)
		set_extra_fuel_fields(self)
		validate_extra_fuel_reason(self)
		enforce_extra_fuel_approval(self)
		validate_fuel_level(self)


def _extra_fuel_requires_approval(doc):
	return flt(doc.extra_fuel_litres) > 0


def enforce_extra_fuel_approval(doc, method=None):
	"""Fuel logged beyond the route's standard allowance must be signed off
	by a System Manager before the log can be submitted, on top of the
	driver/clerk's own written reason captured above."""
	flag_pending_approval(doc, _extra_fuel_requires_approval)
	block_submit_if_not_approved(doc, "extra fuel over the route standard")


def validate_source_requires_dispensing(doc):
	"""Internal Bulk Dispensing is only allowed to reach Truck Fuel Log via the
	Fuel Dispensing doctype (Fuel Dispensing.check_stock_and_issue creates this
	log automatically after it has already deducted the litres from the tank's
	warehouse with a Stock Entry). A log can't otherwise say which tank the
	fuel came from, so without this guard someone could log an 'Internal Bulk
	Dispensing' fill-up by hand and no fuel stock would ever be depleted for
	it — this makes that impossible."""
	if doc.source != "Internal Bulk Dispensing":
		return

	if not doc.fuel_dispensing:
		frappe.throw(
			"Truck Fuel Log with Source 'Internal Bulk Dispensing' cannot be created "
			"directly — it must come from a Fuel Dispensing record, which deducts the "
			"litres from the fuel tank's stock. Please create a Fuel Dispensing entry "
			"instead."
		)

	linked_truck = frappe.db.get_value("Fuel Dispensing", doc.fuel_dispensing, "truck")
	if linked_truck and linked_truck != doc.truck:
		frappe.throw(
			f"Fuel Dispensing {doc.fuel_dispensing} is for truck {linked_truck}, not {doc.truck}."
		)


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


def validate_fuel_level(doc, method=None):
	"""Optional dipstick/known-capacity check — only runs if the driver/clerk
	actually recorded a pre-refuel level for this fill-up. Cross-checked
	against the truck's known tank capacity where available: a computed
	post-refuel level above capacity (beyond a small measurement-tolerance
	buffer) is a physical impossibility, so it's flagged as a likely data
	entry error rather than silently accepted."""
	if not doc.fuel_level_before_refuel:
		doc.fuel_level_after_refuel = 0
		return

	if doc.fuel_level_before_refuel < 0:
		frappe.throw("Fuel Level Before Refuelling cannot be negative.")

	doc.fuel_level_after_refuel = flt(doc.fuel_level_before_refuel) + flt(doc.fuel_qty_litres)

	tank_capacity = frappe.db.get_value("Truck", doc.truck, "tank_capacity_litres")
	if not tank_capacity:
		return  # nothing to cross-check against

	if doc.fuel_level_before_refuel > tank_capacity:
		frappe.throw(
			f"Fuel Level Before Refuelling ({doc.fuel_level_before_refuel}L) is more than this "
			f"truck's tank capacity ({tank_capacity}L). Check the reading, or update the "
			f"truck's Tank Capacity if it's wrong."
		)

	tolerance = tank_capacity * 1.05  # allow ~5% for dipstick/measurement imprecision
	if doc.fuel_level_after_refuel > tolerance:
		frappe.throw(
			f"Fuel Level Before ({doc.fuel_level_before_refuel}L) + Fuel Quantity "
			f"({doc.fuel_qty_litres}L) = {doc.fuel_level_after_refuel}L, which exceeds this "
			f"truck's tank capacity ({tank_capacity}L) by more than a reasonable margin. "
			"One of these figures is likely off — check the pre-refuel reading, the litres "
			"purchased, or the truck's configured Tank Capacity."
		)


def set_extra_fuel_fields(doc):
	"""Pull the Standard Fuel (Litres) set on the trip's Route (if any) and work
	out how much, if anything, this fill-up goes over that standard by."""
	standard = 0
	if doc.reason_for_fuelling == "For Trip" and doc.truck_trip:
		route = frappe.db.get_value("Truck Trip", doc.truck_trip, "route")
		if route:
			standard = frappe.db.get_value("Route", route, "standard_fuel_litres") or 0

	doc.standard_fuel_litres = standard
	doc.extra_fuel_litres = max(0, (doc.fuel_qty_litres or 0) - standard) if standard else 0


def validate_extra_fuel_reason(doc):
	"""Fuel is capped at the route's standard by default, but a driver/clerk can
	go over it as long as they record why \u2014 this is the leeway, not a hard block."""
	if doc.extra_fuel_litres and doc.extra_fuel_litres > 0 and not doc.extra_fuel_reason:
		frappe.throw(
			f"This fill-up is {flt(doc.extra_fuel_litres, 1)} L over the "
			f"{flt(doc.standard_fuel_litres, 1)} L standard for this route. "
			"Please give a reason for the extra fuel."
		)


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


def notify_driver_fuel_confirmation_email(doc, method=None):
	"""Email companion to notify_driver_fuel_confirmation() above, using the
	driver's Employee Company Email (falling back to Personal Email)."""
	if not doc.driver:
		return

	settings = frappe.get_cached_doc("Transport Logistics Settings")
	if not (settings.enable_email_alerts and settings.email_notify_driver):
		return

	email = frappe.db.get_value("Employee", doc.driver, "company_email") or frappe.db.get_value(
		"Employee", doc.driver, "personal_email"
	)
	if not email:
		return

	from transport_logistics.transport_logistics.email_alerts import send_email_alert

	message = (
		f"Fuel log {doc.name} confirmed — {doc.fuel_qty_litres} litres for Truck {doc.truck}"
		f"{' (' + doc.reason_for_fuelling + ')' if doc.reason_for_fuelling else ''}. "
		f"Total: {doc.total_amount}."
	)
	send_email_alert(
		email,
		f"Fuel Log {doc.name} confirmed",
		message,
		reference_doctype="Truck Fuel Log",
		reference_name=doc.name,
		settings=settings,
	)


def notify_driver_fuel_confirmation_sms(doc, method=None):
	"""SMS companion to notify_driver_fuel_confirmation() above."""
	if not doc.driver:
		return

	settings = frappe.get_cached_doc("Transport Logistics Settings")
	if not (settings.enable_sms and settings.sms_notify_driver):
		return

	cell_number = frappe.db.get_value("Employee", doc.driver, "cell_number")
	if not cell_number:
		return

	from transport_logistics.transport_logistics.sms import send_sms

	message = (
		f"Fuel log {doc.name} confirmed — {doc.fuel_qty_litres} litres for Truck {doc.truck}"
		f"{' (' + doc.reason_for_fuelling + ')' if doc.reason_for_fuelling else ''}. "
		f"Total: {doc.total_amount}."
	)
	send_sms(
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
