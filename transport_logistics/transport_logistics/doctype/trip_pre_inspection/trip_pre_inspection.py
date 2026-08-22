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

Every inspection is tied to a specific Truck Trip (the trip it's clearing
for departure) via the Truck Trip field — see validate_truck_trip() below.
On submit, a Fail also sends the truck to workshop automatically: a
Workshop Job Card (Job Type = Inspection) is opened for the faults found
and the Truck is flagged Under Maintenance — see send_truck_to_workshop().
"""

import frappe
from frappe.model.document import Document
from frappe.utils import today

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
		validate_truck_trip(self)


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


def validate_truck_trip(doc, method=None):
	"""Every inspection must be for a specific Truck Trip (reqd on the
	field itself), and that trip's truck must match the Truck selected
	here — otherwise this would be recording a safety check against the
	wrong vehicle."""
	if not doc.truck_trip:
		return

	trip_truck = frappe.db.get_value("Truck Trip", doc.truck_trip, "truck")
	if trip_truck is None:
		frappe.throw(f"Truck Trip {doc.truck_trip} not found.")
	if trip_truck != doc.truck:
		frappe.throw(
			f"Truck Trip {doc.truck_trip} is for truck {trip_truck}, which doesn't match "
			f"the Truck selected on this inspection ({doc.truck})."
		)


def _pick_workshop(company):
	"""Best-effort auto-assignment for a Job Card being created without a
	human choosing the Workshop: prefer an active Workshop (matching
	Company, if the truck has one) that still has a free bay, picking the
	one with the most free capacity so load spreads out rather than
	always landing on the first match. Falls back to Transport Logistics
	Settings > Default Workshop if no such Workshop is found, and leaves
	it blank (for manual triage) if neither is available."""
	from transport_logistics.transport_logistics.doctype.workshop.workshop import (
		ACTIVE_JOB_STATUSES,
	)

	filters = {"is_active": 1}
	if company:
		filters["company"] = company
	candidates = frappe.get_all(
		"Workshop", filters=filters, fields=["name", "bay_count"], order_by="name"
	)

	best_workshop, best_free = None, 0
	for w in candidates:
		if not w.bay_count:
			continue
		active_count = frappe.db.count(
			"Workshop Job Card",
			{"workshop": w.name, "status": ["in", ACTIVE_JOB_STATUSES], "docstatus": ["!=", 2]},
		)
		free = w.bay_count - active_count
		if free > best_free:
			best_workshop, best_free = w.name, free

	if best_workshop:
		return best_workshop

	settings = frappe.get_cached_doc("Transport Logistics Settings")
	return settings.default_workshop or None


def send_truck_to_workshop(doc, method=None):
	"""on_submit: a Fail means this truck cannot be trusted to depart, so
	it's sent to workshop automatically rather than relying on someone to
	notice and raise a Job Card by hand later. Opens a Workshop Job Card
	(Job Type = Inspection) pre-filled with the faults found, auto-assigns
	an available Workshop (see _pick_workshop()), and flags the Truck
	Under Maintenance — same status Highway Breakdown uses for a truck
	that isn't fit to be on the road. Idempotent: if this inspection is
	cancelled and re-submitted (amended), it won't create a second Job
	Card once one is already on file."""
	if doc.overall_status != "Fail" or doc.workshop_job_card:
		return

	if not doc.truck:
		frappe.throw(
			f"Trip Pre Inspection {doc.name} failed but has no Truck set — cannot open a "
			"Workshop Job Card without a Truck. Please set the Truck on this inspection and "
			"submit again."
		)

	failed_items = ", ".join(row.inspection_item for row in doc.items if row.status == "Not OK")
	remarks = ", ".join(
		f"{row.inspection_item}: {row.remarks}" for row in doc.items if row.status == "Not OK" and row.remarks
	)
	company = doc.company or frappe.db.get_value("Truck", doc.truck, "company")

	job_card = frappe.new_doc("Workshop Job Card")
	job_card.truck = doc.truck
	job_card.company = company
	job_card.workshop = _pick_workshop(company)
	job_card.job_type = "Inspection"
	job_card.status = "Open"
	job_card.date_opened = today()
	job_card.odometer_reading = doc.odometer_reading
	job_card.complaint = f"Failed pre-trip inspection ({doc.name}): {failed_items}."
	job_card.diagnosis = remarks
	job_card.trip_pre_inspection = doc.name
	job_card.insert(ignore_permissions=True)

	doc.db_set("workshop_job_card", job_card.name, update_modified=False)
	frappe.db.set_value("Truck", doc.truck, "status", "Under Maintenance")


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
