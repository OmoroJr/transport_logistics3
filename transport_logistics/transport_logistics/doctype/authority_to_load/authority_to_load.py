# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Authority to Load is the formal check-and-sign-off step before a truck can
be loaded for a trip: it verifies the truck is currently empty (not already
loaded on another trip), that its compliance documents (insurance,
license, inspection, COMESA/Yellow Card) aren't expired as of today, and
that the assigned driver's Driving License — and Port Pass, if they have
one on file — aren't expired either — then blocks submission entirely if
any check fails. A submitted Authority to Load is required before its
linked Truck Trip can move to "Ongoing" (see truck_trip.py's
validate_loading_authority).

A blank expiry date (on the Truck, or the driver's Employee record) is
treated as "not tracked, not a blocker" — consistent with how the
compliance-expiry scheduler in tasks.py already treats untracked dates —
so this doesn't punish fleets that haven't filled in every date field. The
Port Pass check specifically only activates for drivers who actually have
a Port Pass Number on file; drivers who never need port access are
unaffected either way.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, nowdate


class AuthoritytoLoad(Document):
	def validate(self):
		run_compliance_checks(self)

	def before_submit(self):
		if not self.all_checks_passed:
			frappe.throw(
				f"Cannot issue Authority to Load — compliance checks failed:\n{self.failure_reason}"
			)


def run_compliance_checks(doc, method=None):
	truck = frappe.get_doc("Truck", doc.truck)
	check_date = getdate(doc.date) if doc.date else getdate(nowdate())

	failures = []

	# Truck must not currently be loaded on another Ongoing, un-offloaded trip.
	other_active_trip = frappe.db.get_value(
		"Truck Trip",
		{
			"truck": doc.truck,
			"name": ["!=", doc.truck_trip or ""],
			"status": "Ongoing",
			"offload_status": "Not Offloaded",
		},
		"name",
	)
	doc.truck_empty_ok = 0 if other_active_trip else 1
	if other_active_trip:
		failures.append(f"Truck is still loaded on trip {other_active_trip} (not yet offloaded).")

	doc.insurance_valid = _date_ok(truck.insurance_expiry_date, check_date, "Insurance", failures)
	doc.license_valid = _date_ok(truck.license_expiry_date, check_date, "License", failures)
	doc.inspection_valid = _date_ok(truck.inspection_expiry_date, check_date, "Inspection", failures)
	doc.comesa_valid = _date_ok(truck.comesa_expiry_date, check_date, "COMESA/Yellow Card", failures)

	if doc.driver:
		driver_license_expiry = _get_employee_field(doc.driver, "driving_license_expiry_date")
		doc.driver_license_valid = _date_ok(
			driver_license_expiry, check_date, f"Driver ({doc.driver}) Driving License", failures
		)

		port_pass_expiry = _get_employee_field(doc.driver, "port_pass_expiry_date")
		port_pass_number = _get_employee_field(doc.driver, "port_pass_number")
		if port_pass_number:
			# Only enforced if the driver actually has a Port Pass on file —
			# drivers who don't need port access are unaffected.
			doc.port_pass_valid = _date_ok(
				port_pass_expiry, check_date, f"Driver ({doc.driver}) Port Pass", failures
			)
		else:
			doc.port_pass_valid = 1
	else:
		doc.driver_license_valid = 1  # nothing to check without a driver
		doc.port_pass_valid = 1

	doc.all_checks_passed = 1 if (
		doc.truck_empty_ok and doc.insurance_valid and doc.license_valid
		and doc.inspection_valid and doc.comesa_valid and doc.driver_license_valid
		and doc.port_pass_valid
	) else 0
	doc.failure_reason = "\n".join(failures) if failures else ""


def _get_employee_field(employee, fieldname):
	"""driving_license_expiry_date / port_pass_number / port_pass_expiry_date
	are Custom Fields (see fixtures/custom_field.json), not core Employee
	columns. If a fixture hasn't been migrated onto this site yet, the
	column won't exist in the database — treat that as "not tracked" (same
	as blank) rather than letting a raw SQL error block every Authority to
	Load save."""
	if fieldname not in frappe.db.get_table_columns("Employee"):
		return None
	return frappe.db.get_value("Employee", employee, fieldname)


def _date_ok(expiry_date, check_date, label, failures):
	if not expiry_date:
		return 1  # not tracked — not a blocker
	if getdate(expiry_date) < check_date:
		failures.append(f"{label} expired on {expiry_date}.")
		return 0
	return 1


def notify_driver(doc, method=None):
	"""Fires on_submit. before_submit already enforced all_checks_passed, so
	by the time this runs it's always a pass — this simply tells the driver
	they're cleared to load, without them needing to check the desk."""
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
		f"Authority to Load {doc.name} approved for Truck {doc.truck}"
		f"{' — Trip ' + doc.truck_trip if doc.truck_trip else ''}. "
		f"{'Destination: ' + doc.destination + '. ' if doc.destination else ''}"
		"You are cleared to load."
	)
	send_whatsapp_message(
		cell_number, message, reference_doctype="Authority to Load", reference_name=doc.name, settings=settings
	)
