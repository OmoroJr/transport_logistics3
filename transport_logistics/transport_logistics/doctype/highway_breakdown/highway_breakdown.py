# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Highway Breakdown records a mechanical/roadside failure that strands a
truck en route — distinct from Accident Report (collisions, theft, fire,
injury) and from Truck Maintenance Log (planned/workshop-scheduled work).

Unlike Accident Report, which only alerts immediately for Major/Fatal
severity, EVERY Highway Breakdown is treated as operationally urgent: the
truck is flagged Under Maintenance and the fleet office is notified the
moment the record is created — not deferred until submission. Submission
is reserved for finalizing the record once the truck is actually back in
service (Status = Resolved), at which point costs post to the GL and the
truck reverts to Active.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import flt, time_diff_in_hours


class HighwayBreakdown(Document):
	def validate(self):
		set_computed_fields(self)

	def before_submit(self):
		if self.status != "Resolved":
			frappe.throw(
				"Highway Breakdown can only be submitted once Status is 'Resolved' — "
				"submitting finalizes the record for the audit trail and posts costs "
				"to the General Ledger. Update Status as the situation progresses, "
				"and submit only once the truck is back in service."
			)
		if not self.resolved_datetime:
			frappe.throw("Resolved At is required before this can be submitted as Resolved.")


def set_computed_fields(doc, method=None):
	doc.total_cost = flt(doc.repair_cost) + flt(doc.towing_cost) + flt(doc.other_cost)
	if doc.resolved_datetime and doc.date_time_of_breakdown:
		hours = time_diff_in_hours(doc.resolved_datetime, doc.date_time_of_breakdown)
		doc.downtime_hours = round(hours, 1) if hours > 0 else 0


def flag_truck_under_maintenance(doc, method=None):
	"""Fires on after_insert — immediately, not on submit — because a
	stranded truck needs to be flagged unavailable the moment it's
	reported, not once the whole incident is finalized and submitted."""
	frappe.db.set_value("Truck", doc.truck, "status", "Under Maintenance")


def notify_breakdown(doc, method=None):
	"""Also fires on after_insert. Every Highway Breakdown gets an
	immediate alert (unlike Accident Report, which reserves immediate
	alerts for Major/Fatal severity) — a truck stuck on the highway is
	always time-sensitive."""
	from transport_logistics.transport_logistics.tasks import notify_users

	subject = f"Highway breakdown reported: Truck {doc.truck} ({doc.name})"
	message = (
		f"Truck {doc.truck} broke down on "
		f"{frappe.utils.format_datetime(doc.date_time_of_breakdown)} at "
		f"{doc.location or 'an unspecified location'}. Type: {doc.breakdown_type}. "
		f"{'Recovery/towing required. ' if (doc.recovery_required or doc.towed) else ''}"
		f"Please review Highway Breakdown {doc.name}."
	)
	notify_users(subject, message, "Highway Breakdown", doc.name, priority="High")


def restore_truck_status(doc, method=None):
	"""Fires on_submit — by this point before_submit has already enforced
	Status == 'Resolved', so it's safe to bring the truck back to Active.
	Best-effort: doesn't check whether the truck has some unrelated reason
	to still be down (e.g. a separate open Workshop Job Card)."""
	frappe.db.set_value("Truck", doc.truck, "status", "Active")
