# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
A Truck is only "available" for a new trip once its current trip has been
offloaded at the client's premises — this models the real-world constraint
that a truck physically can't start a new haulage while it's still loaded
and en route to (or waiting at) a customer. Offloading is the discrete event
that both completes the trip and frees the truck up again.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, flt, getdate


class TruckTrip(Document):
	def validate(self):
		compute_distance(self)
		enforce_driver_change_approval(self)
		validate_truck_availability(self)
		validate_loading_authority(self)
		auto_create_delivery_note(self)
		validate_delivery_note_locked(self)
		auto_create_driver_mileage_payment(self)
		validate_driver_mileage_payment_locked(self)
		validate_pretrip_fuel_log_locked(self)
		validate_pretrip_fuel(self)
		validate_pretrip_inspection_locked(self)
		validate_pretrip_inspection(self)
		set_planned_depot(self)
		validate_planned_depot_locked(self)
		flag_depot_change(self)
		validate_offload_data(self)
		set_revenue_from_sales_order(self)
		notify_driver_trip_started(self)
		notify_driver_trip_started_email(self)
		notify_driver_trip_started_sms(self)


def compute_distance(doc, method=None):
	if doc.start_odometer and doc.end_odometer:
		if doc.end_odometer < doc.start_odometer:
			frappe.throw("End Odometer cannot be less than Start Odometer")
		doc.distance_km = doc.end_odometer - doc.start_odometer
	else:
		doc.distance_km = 0


def enforce_driver_change_approval(doc, method=None):
	"""Once a trip already has a Driver assigned, swapping to a different
	Driver is a sensitive change (pay, notifications, and accountability
	all follow the Driver field) and cannot be made by directly editing the
	field. It must go through request_driver_change() below, which requires
	System Manager approval via manager_approval.approve_request() before
	the Driver field is actually updated."""
	if doc.is_new():
		return

	previous_driver = frappe.db.get_value("Truck Trip", doc.name, "driver")
	if not previous_driver or doc.driver == previous_driver:
		return

	if doc.manager_approval_status == "Approved" and doc.new_driver_requested == doc.driver:
		# This is manager_approval.approve_request() applying an already-approved
		# change (it sets manager_approval_status to Approved and saves; the
		# Driver field itself was changed here, in this same save, to match
		# new_driver_requested). Allow it through, then clear the request.
		doc.new_driver_requested = None
		doc.driver_change_reason = None
		return

	frappe.throw(
		f"Driver cannot be changed directly on an existing trip (was {previous_driver}, "
		f"tried to set {doc.driver}). Use the 'Request Driver Change' action instead — it "
		"requires System Manager approval before the Driver field is updated."
	)


@frappe.whitelist()
def request_driver_change(trip_name, new_driver, reason=None):
	"""Raises a Driver Change request for System Manager approval. Does NOT
	change the Driver field itself — that only happens once
	manager_approval.approve_request() approves this request, which then
	re-saves the trip with Driver set to New Driver Requested."""
	doc = frappe.get_doc("Truck Trip", trip_name)

	if not doc.driver:
		frappe.throw("This trip has no Driver assigned yet — set the Driver field directly instead.")
	if new_driver == doc.driver:
		frappe.throw("New Driver is the same as the current Driver.")

	doc.new_driver_requested = new_driver
	doc.driver_change_reason = reason
	doc.manager_approval_status = "Pending Approval"
	doc.approved_by = None
	doc.approved_on = None
	doc.save()

	return doc.name


def validate_truck_availability(doc, method=None):
	if doc.status not in ("Planned", "Ongoing"):
		return

	existing = frappe.db.get_value(
		"Truck Trip",
		{
			"truck": doc.truck,
			"name": ["!=", doc.name or ""],
			"status": "Ongoing",
			"offload_status": "Not Offloaded",
		},
		"name",
	)
	if existing:
		frappe.throw(
			f"Truck {doc.truck} is still on trip {existing} (loaded, not yet offloaded "
			"at the client's premises). Offload that trip before starting a new one."
		)


def validate_loading_authority(doc, method=None):
	"""A trip can't move to Ongoing (i.e. the truck gets loaded) without a
	submitted Authority to Load on file for it — that document is what
	actually verifies the truck is empty and its compliance documents are
	current. Only skipped if this trip was already Ongoing before this save
	(a subsequent edit, not the transition itself) — a brand new Truck Trip
	saved directly as Ongoing is NOT exempt, since no Authority to Load can
	possibly reference a trip that didn't exist yet when it was issued.

	Not applicable to Empty Return to Depot trips: there's no cargo being
	loaded on this leg, so there's nothing for an Authority to Load to
	authorize."""
	if doc.trip_type == "Empty Return to Depot":
		return

	if doc.status != "Ongoing":
		return

	if not doc.is_new():
		previous_status = frappe.db.get_value("Truck Trip", doc.name, "status")
		if previous_status == "Ongoing":
			return

	has_authority = frappe.db.exists(
		"Authority to Load", {"truck_trip": doc.name, "docstatus": 1}
	)
	if not has_authority:
		frappe.throw(
			f"Truck Trip {doc.name or '(new)'} cannot start (status Ongoing) without a "
			"submitted Authority to Load on file. Save this trip as Planned first, then "
			"create and submit an Authority to Load against it — it verifies the truck "
			"is empty and its compliance documents are valid."
		)


def set_revenue_from_sales_order(doc, method=None):
	"""Revenue Earned always mirrors the linked Sales Order's Grand Total —
	enforced server-side (not just via the client-side fetch_from on the
	field) so it stays correct however the trip was saved: from the desk
	form, the API, a data import, or if the Sales Order is linked after
	Revenue was already typed in. With no Sales Order linked, Revenue is
	left exactly as entered."""
	if not doc.sales_order:
		return

	grand_total = frappe.db.get_value("Sales Order", doc.sales_order, "grand_total")
	if grand_total is not None:
		doc.revenue = flt(grand_total)


def auto_create_delivery_note(doc, method=None):
	"""When a trip moves to Ongoing (the truck is loaded and departs) and is
	linked to a Sales Order but has no Delivery Note yet, generate and
	submit one automatically from that Sales Order — the normal ERPNext
	Sales flow (Sales Order -> Delivery Note), just triggered by the trip
	departing instead of requiring someone to create it by hand first.

	If a Delivery Note is already linked (created manually, or reused from
	an earlier partial shipment), this is skipped entirely — auto-creation
	only fills a gap, never overrides a deliberate choice. Likewise skipped
	if there's no Sales Order to generate from, or if the trip was already
	Ongoing before this save (so re-editing an in-progress trip doesn't
	spawn a second Delivery Note).

	If Delivery Note creation/submission fails — e.g. insufficient stock,
	or the Sales Order is already fully delivered — that failure correctly
	blocks the trip from starting, since the truck can't credibly depart
	with goods that were never actually issued against real stock.

	Not applicable to Empty Return to Depot trips (no Sales Order flow on
	this leg — the sales_order guard below would already skip it, but this
	makes the exclusion explicit)."""
	if doc.trip_type == "Empty Return to Depot":
		return
	if doc.status != "Ongoing" or doc.delivery_note or not doc.sales_order:
		return

	if not doc.is_new():
		previous_status = frappe.db.get_value("Truck Trip", doc.name, "status")
		if previous_status == "Ongoing":
			return

	from erpnext.stock.doctype.delivery_note.delivery_note import make_delivery_note

	try:
		dn = make_delivery_note(doc.sales_order)
		dn.set_posting_time = 1
		dn.posting_date = frappe.utils.nowdate()
		dn.posting_time = frappe.utils.nowtime()
		dn.insert(ignore_permissions=True)
		dn.submit()
	except Exception as e:
		frappe.throw(
			f"Could not automatically generate a Delivery Note from Sales Order "
			f"{doc.sales_order} while starting this trip: {e}"
		)

	doc.delivery_note = dn.name


def auto_create_driver_mileage_payment(doc, method=None):
	"""When a trip moves to Ongoing (the truck is loaded/dispatched and
	departs) fires and there's no Driver Mileage Payment linked yet, create
	one automatically for this single trip: driver, truck, and a one-row
	Routes table (this trip's Route, 1 trip, at the Route's Driver Rate) —
	the same per-destination rate get_route_trip_counts() uses when someone
	fetches trips manually for a period. From Date / To Date are both set
	to the trip date, since this payment covers exactly one trip.

	Left as a Draft (not submitted) so Transport Manager can review, add
	Other Allowance / Bonus, and choose Payment Method / initiate payment —
	auto-creation only removes the data-entry step, not the review step.

	Requires both a Driver and a Route: with no Route there's no
	per-destination rate to compute, and the Routes child table is
	mandatory on Driver Mileage Payment, so there'd be nothing valid to
	save. In that case no payment is auto-created — link one manually if
	the driver is still owed something for this trip.

	Fires only on the Planned -> Ongoing transition (same trigger point
	auto_create_delivery_note() uses above), so re-editing an in-progress
	trip doesn't spawn a second payment; validate_driver_mileage_payment_locked()
	below then freezes the link so it can't be swapped out afterward."""
	if doc.status != "Ongoing" or doc.driver_mileage_payment:
		return
	if not doc.driver or not doc.route:
		return

	if not doc.is_new():
		previous_status = frappe.db.get_value("Truck Trip", doc.name, "status")
		if previous_status == "Ongoing":
			return

	rate = frappe.db.get_value("Route", doc.route, "driver_rate") or 0

	try:
		dmp = frappe.new_doc("Driver Mileage Payment")
		dmp.driver = doc.driver
		dmp.truck = doc.truck
		dmp.company = doc.company
		dmp.from_date = doc.trip_date
		dmp.to_date = doc.trip_date
		dmp.append(
			"routes",
			{
				"route": doc.route,
				"number_of_trips": 1,
				"rate": rate,
				"amount": flt(rate),
			},
		)
		dmp.remarks = f"Auto-created for Truck Trip {doc.name}"
		dmp.insert(ignore_permissions=True)
	except Exception as e:
		frappe.throw(
			f"Could not automatically create a Driver Mileage Payment for this trip: {e}"
		)

	doc.driver_mileage_payment = dmp.name


def validate_driver_mileage_payment_locked(doc, method=None):
	if doc.is_new():
		return

	previous = frappe.db.get_value("Truck Trip", doc.name, "driver_mileage_payment")
	if previous and doc.driver_mileage_payment != previous:
		frappe.throw(
			f"Driver Mileage Payment cannot be changed once set (was {previous}). It represents "
			"the allowance auto-created for this specific trip when it started."
		)


def validate_pretrip_fuel(doc, method=None):
	"""A truck can't start a trip (status Ongoing) without proof it was
	fueled up first — a submitted Full Tank Truck Fuel Log, dated on or
	before departure. This is a real operational safeguard: a truck that
	leaves the yard on a low tank is exactly the kind of thing that turns
	into a Highway Breakdown a few hundred Km down the road.

	Locked once set — same reasoning as validate_delivery_note_locked()
	above: if it could be swapped after the fact, someone could retroactively
	satisfy this check with an unrelated fuel log instead of what actually
	happened before departure."""
	if doc.status != "Ongoing":
		return

	if not doc.is_new():
		previous_status = frappe.db.get_value("Truck Trip", doc.name, "status")
		if previous_status == "Ongoing":
			return

	if not doc.pre_trip_fuel_log:
		frappe.throw(
			"Truck Trip cannot start (status Ongoing) without a Pre-Trip Fuel Log — "
			"link a Full Tank Truck Fuel Log for this truck, dated on or before "
			"departure, confirming it was fueled up before leaving."
		)


def validate_pretrip_fuel_log_locked(doc, method=None):
	if doc.is_new():
		return

	previous = frappe.db.get_value("Truck Trip", doc.name, "pre_trip_fuel_log")
	if previous and doc.pre_trip_fuel_log != previous:
		frappe.throw(
			f"Pre-Trip Fuel Log cannot be changed once set (was {previous}). It represents "
			"proof the truck was actually fueled before this specific trip departed."
		)

	if not doc.pre_trip_fuel_log:
		return

	log = frappe.db.get_value(
		"Truck Fuel Log",
		doc.pre_trip_fuel_log,
		["docstatus", "truck", "full_tank", "date"],
		as_dict=True,
	)
	if not log:
		frappe.throw(f"Truck Fuel Log {doc.pre_trip_fuel_log} not found.")
	if log.docstatus != 1:
		frappe.throw(
			f"Truck Fuel Log {doc.pre_trip_fuel_log} must be submitted before it can be "
			"linked as this trip's Pre-Trip Fuel Log."
		)
	if log.truck != doc.truck:
		frappe.throw(
			f"Truck Fuel Log {doc.pre_trip_fuel_log} is for truck {log.truck}, which doesn't "
			f"match this trip's truck ({doc.truck})."
		)
	if not log.full_tank:
		frappe.throw(
			f"Truck Fuel Log {doc.pre_trip_fuel_log} is not marked Full Tank. The Pre-Trip "
			"Fuel Log must be a full fill-up, not a partial top-up."
		)
	if doc.trip_date and log.date and getdate(log.date) > getdate(doc.trip_date):
		frappe.throw(
			f"Truck Fuel Log {doc.pre_trip_fuel_log} is dated {log.date}, which is after this "
			f"trip's date ({doc.trip_date}). The Pre-Trip Fuel Log must be dated on or before "
			"departure — it can't happen after the trip has already started."
		)


def validate_pretrip_inspection(doc, method=None):
	"""A truck can't start a trip (status Ongoing) without a Pass'd Trip Pre
	Inspection on file — the pre-departure vehicle safety checklist (tyres,
	brakes, lights, fluids, safety equipment, load securing, etc; see
	trip_pre_inspection.py). Same gating pattern as validate_pretrip_fuel()
	above, and for the same reason: a truck sent out without this check is
	exactly the kind of thing that turns into a Highway Breakdown or an
	Accident Report later.

	Off by default (Transport Logistics Settings > Require Pre-Trip
	Inspection Before Departure) — Trip Pre Inspection can still be created
	and used either way; this only controls whether it's enforced as a hard
	gate before a trip can depart."""
	settings = frappe.get_cached_doc("Transport Logistics Settings")
	if not settings.require_pretrip_inspection:
		return

	if doc.status != "Ongoing":
		return

	if not doc.is_new():
		previous_status = frappe.db.get_value("Truck Trip", doc.name, "status")
		if previous_status == "Ongoing":
			return

	if not doc.pre_trip_inspection:
		frappe.throw(
			"Truck Trip cannot start (status Ongoing) without a Pre-Trip Inspection — "
			"link a Trip Pre Inspection for this truck, dated on or before departure, "
			"with Overall Status Pass."
		)


def validate_pretrip_inspection_locked(doc, method=None):
	if doc.is_new():
		return

	previous = frappe.db.get_value("Truck Trip", doc.name, "pre_trip_inspection")
	if previous and doc.pre_trip_inspection != previous:
		frappe.throw(
			f"Pre-Trip Inspection cannot be changed once set (was {previous}). It represents "
			"proof the vehicle safety checklist was actually completed before this specific "
			"trip departed."
		)

	if not doc.pre_trip_inspection:
		return

	inspection = frappe.db.get_value(
		"Trip Pre Inspection",
		doc.pre_trip_inspection,
		["docstatus", "truck", "truck_trip", "overall_status", "inspection_date"],
		as_dict=True,
	)
	if not inspection:
		frappe.throw(f"Trip Pre Inspection {doc.pre_trip_inspection} not found.")
	if inspection.docstatus != 1:
		frappe.throw(
			f"Trip Pre Inspection {doc.pre_trip_inspection} must be submitted before it can be "
			"linked as this trip's Pre-Trip Inspection."
		)
	if inspection.truck != doc.truck:
		frappe.throw(
			f"Trip Pre Inspection {doc.pre_trip_inspection} is for truck {inspection.truck}, "
			f"which doesn't match this trip's truck ({doc.truck})."
		)
	if inspection.truck_trip and inspection.truck_trip != doc.name:
		frappe.throw(
			f"Trip Pre Inspection {doc.pre_trip_inspection} was made for a different trip "
			f"({inspection.truck_trip}), not this one. Link the Trip Pre Inspection that was "
			"created for this specific trip."
		)
	if inspection.overall_status != "Pass":
		frappe.throw(
			f"Trip Pre Inspection {doc.pre_trip_inspection} has Overall Status "
			f"{inspection.overall_status or 'not set'}, not Pass. This truck cannot depart "
			"until a passing inspection is on file."
		)
	if doc.trip_date and inspection.inspection_date and getdate(inspection.inspection_date) > getdate(
		doc.trip_date
	):
		frappe.throw(
			f"Trip Pre Inspection {doc.pre_trip_inspection} is dated {inspection.inspection_date}, "
			f"which is after this trip's date ({doc.trip_date}). The Pre-Trip Inspection must be "
			"dated on or before departure — it can't happen after the trip has already started."
		)


def validate_delivery_note_locked(doc, method=None):
	"""The Delivery Note is generated (as in a normal Sales flow) at the
	moment the truck is loaded and the driver departs — it's the physical
	document the driver carries. Once a trip has moved past Planned, that
	document can no longer be swapped out from under the trip; doing so
	would let someone attach a different delivery's paperwork after the
	fact, which is exactly what the offload-time match check below exists
	to prevent."""
	if doc.is_new():
		return

	previous_delivery_note = frappe.db.get_value("Truck Trip", doc.name, "delivery_note")
	if previous_delivery_note and doc.delivery_note != previous_delivery_note:
		frappe.throw(
			f"Delivery Note cannot be changed once set (was {previous_delivery_note}). "
			"It represents the document issued to the driver at departure and must stay "
			"fixed for the life of the trip."
		)

	if not doc.delivery_note:
		return

	dn = frappe.db.get_value(
		"Delivery Note", doc.delivery_note, ["docstatus", "customer"], as_dict=True
	)
	if not dn:
		frappe.throw(f"Delivery Note {doc.delivery_note} not found.")
	if dn.docstatus != 1:
		frappe.throw(
			f"Delivery Note {doc.delivery_note} must be submitted before it can be linked "
			"to this trip — it isn't a real issued document until then."
		)
	if doc.customer and dn.customer and dn.customer != doc.customer:
		frappe.throw(
			f"Delivery Note {doc.delivery_note} is for customer {dn.customer}, which doesn't "
			f"match this trip's customer ({doc.customer})."
		)

	existing = frappe.db.get_value(
		"Truck Trip",
		{"delivery_note": doc.delivery_note, "name": ["!=", doc.name or ""]},
		"name",
	)
	if existing:
		frappe.throw(
			f"Delivery Note {doc.delivery_note} is already linked to Truck Trip {existing}. "
			"Each Delivery Note represents one consignment leaving with one trip."
		)


def set_planned_depot(doc, method=None):
	"""Planned Depot / Yard is the baseline an Empty Return to Depot trip was
	dispatched against — it mirrors Destination at the point this trip first
	becomes an Empty Return to Depot trip. Only filled in if still blank;
	validate_planned_depot_locked() below then freezes it, so later edits to
	Destination (or a redirect at return time via Actual Depot / Yard) don't
	silently move the baseline out from under the comparison in
	flag_depot_change()."""
	if doc.trip_type != "Empty Return to Depot":
		return
	if not doc.planned_depot:
		doc.planned_depot = doc.destination


def validate_planned_depot_locked(doc, method=None):
	if doc.is_new():
		return

	previous = frappe.db.get_value("Truck Trip", doc.name, "planned_depot")
	if previous and doc.planned_depot != previous:
		frappe.throw(
			f"Planned Depot / Yard cannot be changed once set (was {previous}). It represents "
			"where this container was originally routed to, and is what Actual Depot / Yard is "
			"compared against to detect a depot change."
		)


def flag_depot_change(doc, method=None):
	"""Detects whether the empty container was actually returned to a
	different depot/CFS than the one it was planned for (Planned Depot /
	Yard). This is a normal occurrence — the original depot can be full,
	closed, or the shipping line/CFS can redirect it — but it needs to be
	visible and explained (see depot_change_reason), not just silently
	recorded in a free-text Depot field."""
	if doc.trip_type != "Empty Return to Depot":
		doc.depot_changed = 0
		return

	if not doc.planned_depot or not doc.depot:
		doc.depot_changed = 0
		return

	doc.depot_changed = 1 if doc.depot.strip().lower() != doc.planned_depot.strip().lower() else 0
	if not doc.depot_changed:
		doc.depot_change_reason = None


def validate_offload_data(doc, method=None):
	"""A trip can't be marked Offloaded unless every piece of proof-of-
	delivery data is actually captured — this is the field-level backstop
	behind the offload_truck() flow below, so the requirement holds even if
	a Truck Trip is offloaded via the API or a data import rather than the
	'Offload at Client' dialog.

	Empty Return to Depot trips have no customer delivery on this leg, so
	they're checked against the Interchange Number / Depot instead of
	Delivery Note / Delivery Number / Proof of Delivery — see
	return_empty_container() below, the equivalent flow for this trip type."""
	if doc.offload_status != "Offloaded":
		return

	missing = []
	if not doc.offload_datetime:
		missing.append("Offloaded At")
	if not doc.offload_odometer:
		missing.append("Odometer At Offload")
	if not doc.offloaded_by:
		missing.append("Offload Confirmed By")

	if doc.trip_type == "Empty Return to Depot":
		if not doc.depot:
			missing.append("Actual Depot / Yard")
		if not doc.interchange_no:
			missing.append("Interchange Number")
		if doc.depot_changed and not doc.depot_change_reason:
			missing.append("Reason for Depot Change")
	else:
		if not doc.delivery_note:
			missing.append("Delivery Note")
		if not doc.delivery_number:
			missing.append("Delivery Number")
		if not doc.proof_of_delivery:
			missing.append("Proof of Delivery (attached file)")

	if missing:
		frappe.throw(
			"Cannot mark this trip as Offloaded — the following are required: "
			+ ", ".join(missing)
			+ (
				". An Empty Return to Depot trip can only be confirmed returned once the "
				"Depot / Yard and Interchange Number are captured."
				if doc.trip_type == "Empty Return to Depot"
				else ". A truck can only be confirmed offloaded at the client's premises once "
				"the Delivery Number and signed Proof of Delivery are captured."
			)
		)

	if doc.trip_type != "Empty Return to Depot":
		validate_delivery_number_matches_delivery_note(doc)


def validate_delivery_number_matches_delivery_note(doc, method=None):
	"""The Delivery Number transcribed at offload must be the SAME delivery
	that was issued to the driver at departure — i.e. it must match the
	linked Delivery Note. This is the actual "reference point" check: it
	catches a driver returning proof against the wrong (or a substitute)
	delivery, rather than just recording whatever number is typed in."""
	if not doc.delivery_note or not doc.delivery_number:
		return

	if doc.delivery_number.strip() != doc.delivery_note.strip():
		frappe.throw(
			f"Delivery Number '{doc.delivery_number}' does not match the Delivery Note issued "
			f"to the driver at departure ({doc.delivery_note}). The proof of delivery must be "
			"for the same delivery that left with this trip — verify the physical document "
			"and correct the entry, or investigate if it genuinely doesn't match."
		)


def notify_driver_trip_started(doc, method=None):
	"""Fires only on the Planned -> Ongoing transition (same trigger point
	validate_loading_authority uses above), i.e. once a submitted Authority
	to Load already exists for this trip — so the driver is only paged once
	the truck is actually cleared to depart, not on every edit of a Planned
	trip."""
	if doc.status != "Ongoing" or not doc.driver:
		return

	if not doc.is_new():
		previous_status = frappe.db.get_value("Truck Trip", doc.name, "status")
		if previous_status == "Ongoing":
			return

	settings = frappe.get_cached_doc("Transport Logistics Settings")
	if not (settings.enable_whatsapp and settings.whatsapp_notify_driver):
		return

	cell_number = frappe.db.get_value("Employee", doc.driver, "cell_number")
	if not cell_number:
		return

	from transport_logistics.transport_logistics.whatsapp import send_whatsapp_message

	message = (
		f"Trip {doc.name} dispatched — Truck {doc.truck}, "
		f"{doc.origin or 'origin not set'} to {doc.destination or 'destination not set'}."
		+ (f" Delivery Note: {doc.delivery_note}." if doc.delivery_note else "")
	)
	send_whatsapp_message(
		cell_number, message, reference_doctype="Truck Trip", reference_name=doc.name, settings=settings
	)


def notify_driver_trip_started_email(doc, method=None):
	"""Email companion to notify_driver_trip_started() above, using the
	driver's Employee Company Email (falling back to Personal Email)."""
	if doc.status != "Ongoing" or not doc.driver:
		return

	if not doc.is_new():
		previous_status = frappe.db.get_value("Truck Trip", doc.name, "status")
		if previous_status == "Ongoing":
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
		f"Trip {doc.name} dispatched — Truck {doc.truck}, "
		f"{doc.origin or 'origin not set'} to {doc.destination or 'destination not set'}."
		+ (f" Delivery Note: {doc.delivery_note}." if doc.delivery_note else "")
	)
	send_email_alert(
		email,
		f"Trip {doc.name} dispatched",
		message,
		reference_doctype="Truck Trip",
		reference_name=doc.name,
		settings=settings,
	)


def notify_driver_trip_started_sms(doc, method=None):
	"""SMS companion to notify_driver_trip_started() above."""
	if doc.status != "Ongoing" or not doc.driver:
		return

	if not doc.is_new():
		previous_status = frappe.db.get_value("Truck Trip", doc.name, "status")
		if previous_status == "Ongoing":
			return

	settings = frappe.get_cached_doc("Transport Logistics Settings")
	if not (settings.enable_sms and settings.sms_notify_driver):
		return

	cell_number = frappe.db.get_value("Employee", doc.driver, "cell_number")
	if not cell_number:
		return

	from transport_logistics.transport_logistics.sms import send_sms

	message = (
		f"Trip {doc.name} dispatched — Truck {doc.truck}, "
		f"{doc.origin or 'origin not set'} to {doc.destination or 'destination not set'}."
		+ (f" Delivery Note: {doc.delivery_note}." if doc.delivery_note else "")
	)
	send_sms(
		cell_number, message, reference_doctype="Truck Trip", reference_name=doc.name, settings=settings
	)


@frappe.whitelist()
def offload_truck(
	trip_name,
	offload_odometer=None,
	offloaded_by=None,
	delivery_number=None,
	proof_of_delivery=None,
):
	"""Records that the truck has offloaded at the client's premises: marks
	the trip Completed and the truck available again. This is the mechanism
	that distinguishes a truck currently 'loaded, en route to a client' from
	one that is 'empty and available' — see the Truck Fleet Status report.

	Odometer, Confirmed By, Delivery Number, and Proof of Delivery are all
	required, and Delivery Number must match this trip's Delivery Note
	(the document issued to the driver at departure) — validate_offload_data()
	and validate_delivery_number_matches_delivery_note() above enforce this
	again at save time regardless of how this method is called. This only
	captures the POD; it does NOT authenticate it — see authenticate_pod()
	below, which is a deliberately separate, restricted action.

	Loaded Haul trips only — see return_empty_container() below for the
	Empty Return to Depot equivalent."""
	if not offload_odometer:
		frappe.throw("Odometer Reading at Offload is required.")
	if not offloaded_by:
		frappe.throw("Confirmed By (the person who witnessed/confirmed the offload) is required.")
	if not delivery_number:
		frappe.throw(
			"Delivery Number is required — transcribe it from the physical Delivery Note the "
			"driver is returning with."
		)
	if not proof_of_delivery:
		frappe.throw(
			"Proof of Delivery must be attached before this trip can be marked Offloaded."
		)

	doc = frappe.get_doc("Truck Trip", trip_name)

	if doc.trip_type == "Empty Return to Depot":
		frappe.throw(
			"This trip is Trip Type 'Empty Return to Depot' — use 'Return Empty Container to "
			"Depot' instead of 'Offload at Client'."
		)

	if doc.offload_status == "Offloaded":
		frappe.throw("This trip has already been offloaded.")

	if not doc.delivery_note:
		frappe.throw(
			"This trip has no Delivery Note on file. It should have been generated "
			"automatically when the trip started — if it's missing, the Sales Order link "
			"may be missing too, or auto-generation may have failed silently. Check the "
			"Error Log, or link a Delivery Note manually."
		)

	doc.offload_status = "Offloaded"
	doc.offload_datetime = now_datetime()
	doc.offload_odometer = flt(offload_odometer)
	if not doc.end_odometer:
		doc.end_odometer = flt(offload_odometer)
	doc.offloaded_by = offloaded_by
	doc.delivery_number = delivery_number.strip()
	doc.proof_of_delivery = proof_of_delivery
	doc.status = "Completed"

	doc.save(ignore_permissions=True)

	_link_attachment(doc, proof_of_delivery, "proof_of_delivery")

	return doc.name


@frappe.whitelist()
def return_empty_container(
	trip_name,
	offload_odometer=None,
	offloaded_by=None,
	depot=None,
	depot_change_reason=None,
	interchange_no=None,
	interchange_date=None,
	interchange_receipt=None,
):
	"""Companion to offload_truck() above, for an 'Empty Return to Depot'
	leg: marks the trip Completed once the empty container has physically
	been handed back at the depot/CFS. There's no customer delivery on
	this leg, so it's evidenced by an Actual Depot / Yard and Interchange
	Number (the receipt the depot/CFS issues confirming the container was
	accepted back in good condition) rather than a Delivery Note + POD.

	'depot' here is where the container was ACTUALLY returned — it can
	differ from Planned Depot / Yard (set automatically from Destination
	when the trip was created; see set_planned_depot()) if the driver was
	redirected. When it does differ, depot_change_reason is required —
	flag_depot_change() and validate_offload_data() above enforce this
	again at save time regardless of how this method is called.

	interchange_receipt is an optional scanned/photographed copy of the
	interchange receipt, attached the same way Proof of Delivery is on
	offload_truck() below."""
	if not offload_odometer:
		frappe.throw("Odometer Reading at Return is required.")
	if not offloaded_by:
		frappe.throw("Confirmed By (the person who witnessed/confirmed the return) is required.")
	if not depot:
		frappe.throw("Actual Depot / Yard is required.")
	if not interchange_no:
		frappe.throw(
			"Interchange Number is required — transcribe it from the interchange receipt "
			"issued at the depot/CFS confirming the empty container was accepted back."
		)

	doc = frappe.get_doc("Truck Trip", trip_name)

	if doc.trip_type != "Empty Return to Depot":
		frappe.throw(
			"This action is only for trips of Trip Type 'Empty Return to Depot' — use "
			"'Offload at Client' instead."
		)
	if doc.offload_status == "Offloaded":
		frappe.throw("This trip has already been marked as returned.")

	if not doc.planned_depot:
		doc.planned_depot = doc.destination

	depot = depot.strip()
	depot_changed = bool(doc.planned_depot) and depot.lower() != doc.planned_depot.strip().lower()
	if depot_changed and not depot_change_reason:
		frappe.throw(
			f"Actual Depot / Yard ({depot}) is different from the Planned Depot / Yard "
			f"({doc.planned_depot}) — a Reason for Depot Change is required."
		)

	doc.offload_status = "Offloaded"
	doc.offload_datetime = now_datetime()
	doc.offload_odometer = flt(offload_odometer)
	if not doc.end_odometer:
		doc.end_odometer = flt(offload_odometer)
	doc.offloaded_by = offloaded_by
	doc.depot = depot
	doc.depot_changed = 1 if depot_changed else 0
	doc.depot_change_reason = depot_change_reason if depot_changed else None
	doc.interchange_no = interchange_no.strip()
	if interchange_date:
		doc.interchange_date = getdate(interchange_date)
	doc.interchange_receipt = interchange_receipt
	doc.status = "Completed"

	doc.save(ignore_permissions=True)

	if interchange_receipt:
		_link_attachment(doc, interchange_receipt, "interchange_receipt")

	return doc.name


def _link_attachment(doc, file_url, fieldname):
	"""Files uploaded from a stand-alone Dialog (before the Truck Trip
	document context is available to the uploader — e.g. Proof of Delivery
	on offload_truck(), Interchange Receipt on return_empty_container())
	aren't automatically linked to this Truck Trip the way an in-form
	Attach upload would be. Link explicitly so they show up correctly in
	the document's Attachments list rather than sitting orphaned."""
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if file_name:
		frappe.db.set_value(
			"File",
			file_name,
			{
				"attached_to_doctype": "Truck Trip",
				"attached_to_name": doc.name,
				"attached_to_field": fieldname,
			},
		)


AUTHENTICATING_ROLES = ("Transport Manager", "System Manager")


@frappe.whitelist()
def authenticate_pod(trip_name):
	"""Deliberately separate from offload_truck(): capturing the scanned
	POD (any driver/loading clerk can do that at the point of offload) is
	not the same thing as authenticating it (an independent check, by
	someone with authority, that the scanned document and Delivery Number
	genuinely match a real delivery). Restricted to Transport Manager /
	System Manager so the person who captured the POD can't also be the one
	who authenticates it."""
	user_roles = frappe.get_roles(frappe.session.user)
	if not any(role in user_roles for role in AUTHENTICATING_ROLES):
		frappe.throw(
			"You don't have permission to authenticate a Proof of Delivery. This action is "
			"restricted to Transport Manager, to keep the person capturing the POD separate "
			"from the person verifying it.",
			frappe.PermissionError,
		)

	doc = frappe.get_doc("Truck Trip", trip_name)

	if doc.offload_status != "Offloaded":
		frappe.throw("This trip has not been offloaded yet — nothing to authenticate.")
	if not doc.proof_of_delivery:
		frappe.throw("No Proof of Delivery is attached to this trip.")
	if doc.pod_authenticated:
		frappe.throw("This Proof of Delivery has already been authenticated.")

	doc.pod_authenticated = 1
	doc.pod_authenticated_by = frappe.session.user
	doc.pod_authenticated_on = now_datetime()
	doc.save(ignore_permissions=True)

	return doc.name
