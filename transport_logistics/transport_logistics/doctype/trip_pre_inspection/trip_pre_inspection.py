# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Pre-departure vehicle safety checklist for a Truck. A submitted Trip Pre
Inspection with Overall Status = Pass, dated on or before departure, is
required before a Truck Trip can move to Ongoing — see
validate_pretrip_inspection()/validate_pretrip_inspection_locked() in
truck_trip.py, the same gating pattern already used for the Pre-Trip Fuel
Log and Authority to Load.

Overall Status is computed automatically: any checklist row marked "Not OK"
fails the whole inspection. A Fail does NOT block saving/submitting this
document itself (the inspector still needs to be able to record and submit
a failed inspection) — it's the Truck Trip side that refuses to depart on
it.

Tyre Pressure Check is a separate, entirely optional section: it never
affects Overall Status and is never required to submit. It exists for
record-keeping and to feed the Pre Trip Inspection Report — see
../../report/pre_trip_inspection_report/.
"""

import frappe
from frappe.model.document import Document

DEFAULT_CHECKLIST_ITEMS = [
	"Tyres & Wheel Nuts",
	"Brakes",
	"Lights & Indicators",
	"Mirrors",
	"Windscreen & Wipers",
	"Horn",
	"Seatbelts",
	"Fuel Level",
	"Engine Oil Level",
	"Coolant Level",
	"Fire Extinguisher",
	"First Aid Kit",
	"Warning Triangle",
	"Spare Wheel & Jack",
	"Load Secured / Ties",
	"Vehicle Documents in Cab",
]


class TripPreInspection(Document):
	def validate(self):
		populate_default_items(self)
		validate_items(self)
		compute_overall_status(self)
		compute_tyre_pressure_status(self)


def populate_default_items(doc, method=None):
	"""Only ever fills a genuinely empty checklist (e.g. a record created
	via the API without items) — never touches it once at least one row
	exists, so an inspector's edits (added/removed/reordered rows) are
	always left alone."""
	if doc.items:
		return
	for item in DEFAULT_CHECKLIST_ITEMS:
		doc.append("items", {"inspection_item": item})


def validate_items(doc, method=None):
	for row in doc.items:
		if row.status == "Not OK" and not row.remarks:
			frappe.throw(
				f"Row {row.idx} ({row.inspection_item}): Remarks are required when Status is "
				"Not OK — describe the fault found."
			)


def compute_overall_status(doc, method=None):
	if not doc.items:
		doc.overall_status = ""
		return
	doc.overall_status = "Fail" if any(row.status == "Not OK" for row in doc.items) else "Pass"


def compute_tyre_pressure_status(doc, method=None):
	"""Entirely optional and informational — a tyre pressure reading never
	affects Overall Status or blocks anything downstream. Only fills in
	Status when the inspector left it blank and gave a Standard (PSI) to
	compare against; a Status the inspector set by hand is always left
	alone. Tolerance is a simple flat +/-10% band, since this is a quick
	pre-trip check, not a calibrated measurement."""
	for row in doc.tyre_pressures:
		if row.status or not row.standard_psi or not row.pressure_psi:
			continue
		lower = row.standard_psi * 0.9
		upper = row.standard_psi * 1.1
		if row.pressure_psi < lower:
			row.status = "Low"
		elif row.pressure_psi > upper:
			row.status = "High"
		else:
			row.status = "OK"


def notify_on_fail(doc, method=None):
	"""on_submit: a Fail is a real road-safety issue — alert the fleet
	office immediately rather than waiting for it to be noticed when the
	Truck Trip is blocked from departing."""
	if doc.overall_status != "Fail":
		return

	from transport_logistics.transport_logistics.tasks import notify_users

	failed_items = ", ".join(row.inspection_item for row in doc.items if row.status == "Not OK")
	subject = f"Truck {doc.truck} FAILED pre-trip inspection ({doc.name})"
	message = (
		f"Trip Pre Inspection {doc.name} for Truck {doc.truck} on {doc.inspection_date} "
		f"failed the following item(s): {failed_items}. This truck cannot depart on a new "
		"trip until a passing inspection is on file."
	)
	notify_users(subject, message, "Trip Pre Inspection", doc.name, priority="High")
