# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Workshop Job Card is the shop-floor work order: complaint, diagnosis, work
done, labour hours, and spare parts consumed. On submit it:

  1. Optionally issues the listed parts from a Warehouse via a Stock Entry
     (Material Issue) — skipped gracefully if no warehouse is set or stock
     runs short.
  2. Auto-creates and submits a Truck Maintenance Log carrying the same
     parts/labour/other cost breakdown, so the job flows straight into the
     existing Truck Cost Analysis report and optional GL posting without any
     duplicate logic — the Job Card is the shop-floor detail, the
     Maintenance Log is the cost record other reports already read from.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import flt, today

from transport_logistics.transport_logistics.doctype.workshop.workshop import ACTIVE_JOB_STATUSES


class WorkshopJobCard(Document):
	def validate(self):
		compute_costs(self)
		validate_workshop_capacity(self)


def compute_costs(doc, method=None):
	parts_total = 0.0
	for row in doc.items:
		row.amount = flt(row.qty) * flt(row.rate)
		parts_total += row.amount
	doc.parts_cost = parts_total
	doc.labour_cost = flt(doc.labour_hours) * flt(doc.labour_rate)
	doc.total_cost = flt(doc.labour_cost) + flt(doc.parts_cost) + flt(doc.other_cost)


def validate_workshop_capacity(doc, method=None):
	"""A workshop with N bays can't have more than N jobs occupying it at
	once — mirrors the same real-world-capacity philosophy as Truck Trip's
	availability check. Only blocks the transition into an active status;
	editing a job that's already active, or closing one, is never blocked."""
	if not doc.workshop or doc.status not in ACTIVE_JOB_STATUSES:
		return

	if not doc.is_new():
		previous_status = frappe.db.get_value("Workshop Job Card", doc.name, "status")
		if previous_status in ACTIVE_JOB_STATUSES:
			return

	bay_count = frappe.db.get_value("Workshop", doc.workshop, "bay_count") or 0
	if not bay_count:
		return

	active_count = frappe.db.count(
		"Workshop Job Card",
		{
			"workshop": doc.workshop,
			"name": ["!=", doc.name or ""],
			"status": ["in", ACTIVE_JOB_STATUSES],
			"docstatus": ["!=", 2],
		},
	)
	if active_count >= bay_count:
		frappe.throw(
			f"Workshop {doc.workshop} only has {bay_count} bay(s) and already has "
			f"{active_count} job(s) in progress there. Complete or close an existing "
			"job before opening another one at this workshop."
		)


JOB_TYPE_TO_MAINTENANCE_TYPE = {
	"Scheduled Service": "Scheduled Service",
	"Repair": "Repair",
	"Breakdown": "Breakdown",
	"Inspection": "Inspection",
	"Accident Repair": "Repair",
}


def on_submit_actions(doc, method=None):
	issue_parts(doc)
	create_maintenance_log(doc)

	if not doc.date_closed:
		doc.db_set("date_closed", today(), update_modified=False)
	if doc.status not in ("Completed", "Cancelled"):
		doc.db_set("status", "Completed", update_modified=False)

	# The job is finished by definition of being submitted here, so make sure
	# the truck reads Active again rather than being left "Under Maintenance"
	# (which the underlying Maintenance Log's own submit hook may have just set
	# for Repair/Breakdown types).
	frappe.db.set_value("Truck", doc.truck, "status", "Active")


def issue_parts(doc):
	if not doc.warehouse or not doc.items:
		return

	stock_entry = frappe.new_doc("Stock Entry")
	stock_entry.stock_entry_type = "Material Issue"
	stock_entry.company = doc.company

	for row in doc.items:
		if not flt(row.qty):
			continue
		stock_entry.append(
			"items",
			{
				"item_code": row.item_code,
				"qty": row.qty,
				"s_warehouse": doc.warehouse,
				"basic_rate": row.rate,
			},
		)

	if not stock_entry.get("items"):
		return

	stock_entry.insert(ignore_permissions=True)
	try:
		stock_entry.submit()
	except Exception as e:
		frappe.msgprint(
			f"Parts cost was recorded on this Job Card, but the Stock Entry could "
			f"not be submitted automatically (often insufficient stock in "
			f"{doc.warehouse}): {e}. Please issue the stock manually if needed.",
			alert=True,
			indicator="orange",
		)
		return

	doc.db_set("stock_entry", stock_entry.name, update_modified=False)


def create_maintenance_log(doc):
	if doc.maintenance_log:
		return

	maintenance_type = JOB_TYPE_TO_MAINTENANCE_TYPE.get(doc.job_type, "Repair")

	log = frappe.new_doc("Truck Maintenance Log")
	log.truck = doc.truck
	log.company = doc.company
	log.maintenance_type = maintenance_type
	log.date = doc.date_closed or today()
	log.odometer_reading = doc.odometer_reading
	trailer_note = f" (Trailer: {doc.trailer})" if doc.trailer else ""
	log.description = f"[Workshop Job Card {doc.name}]{trailer_note} {doc.work_done or doc.complaint or ''}".strip()
	log.workshop = doc.workshop
	log.vendor = doc.workshop or "In-House Workshop"
	log.parts_cost = doc.parts_cost
	log.labour_cost = doc.labour_cost
	log.other_cost = doc.other_cost
	log.insert(ignore_permissions=True)
	log.submit()

	doc.db_set("maintenance_log", log.name, update_modified=False)


def on_cancel_actions(doc, method=None):
	if doc.maintenance_log and frappe.db.exists("Truck Maintenance Log", doc.maintenance_log):
		log = frappe.get_doc("Truck Maintenance Log", doc.maintenance_log)
		if log.docstatus == 1:
			log.cancel()

	if doc.stock_entry and frappe.db.exists("Stock Entry", doc.stock_entry):
		se = frappe.get_doc("Stock Entry", doc.stock_entry)
		if se.docstatus == 1:
			se.cancel()
