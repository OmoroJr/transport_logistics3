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
		validate_truck_availability(self)
		validate_loading_authority(self)
		auto_create_delivery_note(self)
		validate_delivery_note_locked(self)
		validate_pretrip_fuel_log_locked(self)
		validate_pretrip_fuel(self)
		validate_offload_data(self)
		set_revenue_from_sales_order(self)


def compute_distance(doc, method=None):
	if doc.start_odometer and doc.end_odometer:
		if doc.end_odometer < doc.start_odometer:
			frappe.throw("End Odometer cannot be less than Start Odometer")
		doc.distance_km = doc.end_odometer - doc.start_odometer
	else:
		doc.distance_km = 0


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
	possibly reference a trip that didn't exist yet when it was issued."""
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
	with goods that were never actually issued against real stock."""
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


def validate_offload_data(doc, method=None):
	"""A trip can't be marked Offloaded unless every piece of proof-of-
	delivery data is actually captured — this is the field-level backstop
	behind the offload_truck() flow below, so the requirement holds even if
	a Truck Trip is offloaded via the API or a data import rather than the
	'Offload at Client' dialog."""
	if doc.offload_status != "Offloaded":
		return

	missing = []
	if not doc.offload_datetime:
		missing.append("Offloaded At")
	if not doc.offload_odometer:
		missing.append("Odometer At Offload")
	if not doc.offloaded_by:
		missing.append("Offload Confirmed By")
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
			+ ". A truck can only be confirmed offloaded at the client's premises once "
			"the Delivery Number and signed Proof of Delivery are captured."
		)

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
	below, which is a deliberately separate, restricted action."""
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

	_link_proof_of_delivery_attachment(doc, proof_of_delivery)

	return doc.name


def _link_proof_of_delivery_attachment(doc, file_url):
	"""The Proof of Delivery file is uploaded from a stand-alone Dialog
	(before the Truck Trip document context is available to the uploader),
	so the resulting File record isn't automatically linked to this Truck
	Trip the way an in-form Attach upload would be. Link it explicitly so
	it shows up correctly in the document's Attachments list rather than
	sitting orphaned."""
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if file_name:
		frappe.db.set_value(
			"File",
			file_name,
			{
				"attached_to_doctype": "Truck Trip",
				"attached_to_name": doc.name,
				"attached_to_field": "proof_of_delivery",
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
