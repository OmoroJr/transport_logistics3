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
from frappe.utils import now_datetime, flt


class TruckTrip(Document):
	def validate(self):
		compute_distance(self)
		validate_truck_availability(self)
		validate_loading_authority(self)
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


@frappe.whitelist()
def offload_truck(trip_name, offload_odometer=None, offloaded_by=None):
	"""Records that the truck has offloaded at the client's premises: marks
	the trip Completed and the truck available again. This is the mechanism
	that distinguishes a truck currently 'loaded, en route to a client' from
	one that is 'empty and available' — see the Truck Fleet Status report."""
	doc = frappe.get_doc("Truck Trip", trip_name)

	if doc.offload_status == "Offloaded":
		frappe.throw("This trip has already been offloaded.")

	doc.offload_status = "Offloaded"
	doc.offload_datetime = now_datetime()
	if offload_odometer:
		doc.offload_odometer = flt(offload_odometer)
		if not doc.end_odometer:
			doc.end_odometer = flt(offload_odometer)
	if offloaded_by:
		doc.offloaded_by = offloaded_by
	doc.status = "Completed"

	doc.save(ignore_permissions=True)
	return doc.name
