# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Authority to Load is the formal check-and-sign-off step before a truck can
be loaded for a trip: it verifies the truck is currently empty (not already
loaded on another trip), that its compliance documents (insurance,
license, inspection, COMESA/Yellow Card) aren't expired as of today, and
that the assigned driver's Driving License isn't expired either — then
blocks submission entirely if any check fails. A submitted Authority to
Load is required before its linked Truck Trip can move to "Ongoing" (see
truck_trip.py's validate_loading_authority).

A blank expiry date (on the Truck, or the driver's Employee record) is
treated as "not tracked, not a blocker" — consistent with how the
compliance-expiry scheduler in tasks.py already treats untracked dates —
so this doesn't punish fleets that haven't filled in every date field.
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
		driver_license_expiry = frappe.db.get_value(
			"Employee", doc.driver, "driving_license_expiry_date"
		)
		doc.driver_license_valid = _date_ok(
			driver_license_expiry, check_date, f"Driver ({doc.driver}) Driving License", failures
		)
	else:
		doc.driver_license_valid = 1  # nothing to check without a driver

	doc.all_checks_passed = 1 if (
		doc.truck_empty_ok and doc.insurance_valid and doc.license_valid
		and doc.inspection_valid and doc.comesa_valid and doc.driver_license_valid
	) else 0
	doc.failure_reason = "\n".join(failures) if failures else ""


def _date_ok(expiry_date, check_date, label, failures):
	if not expiry_date:
		return 1  # not tracked — not a blocker
	if getdate(expiry_date) < check_date:
		failures.append(f"{label} expired on {expiry_date}.")
		return 0
	return 1
