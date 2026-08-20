# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Records a periodic tread-depth measurement for a Tyre, against a legal (or
internal-policy) minimum, and auto-computes Pass / Marginal / Fail. A Fail
flags the Tyre for replacement immediately (visible on the Tyre record
itself, not just buried in inspection history) and alerts whoever holds
the Notify Role, the same mechanism used for expiring compliance documents
and highway breakdowns elsewhere in this app.

Vehicle/position fields are fetched from the Tyre at creation time and are
NOT re-fetched afterward — they're a snapshot of where the tyre actually
was at the moment of inspection, since a tyre can be moved to a different
position (or removed entirely) after this record is created, and the
inspection should still reflect what was true when it happened.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class TyreDepthInspection(Document):
	def validate(self):
		set_minimum_if_unset(self)
		compute_status(self)


def set_minimum_if_unset(doc, method=None):
	if not doc.minimum_required_mm:
		settings = frappe.get_cached_doc("Transport Logistics Settings")
		doc.minimum_required_mm = flt(settings.minimum_tyre_tread_depth_mm) or 1.6


def compute_status(doc, method=None):
	if not doc.tread_depth_mm or not doc.minimum_required_mm:
		doc.status = ""
		return

	if doc.tread_depth_mm <= doc.minimum_required_mm:
		doc.status = "Fail"
	elif doc.tread_depth_mm <= doc.minimum_required_mm * 1.2:
		doc.status = "Marginal"
	else:
		doc.status = "Pass"


def flag_tyre_on_fail(doc, method=None):
	"""on_submit: a Fail flags the Tyre immediately and alerts the fleet
	office — a bald tyre is a genuine road-safety and legal-compliance
	issue, not something that should wait to be noticed on the next
	scheduled inspection."""
	if doc.status != "Fail":
		return

	frappe.db.set_value("Tyre", doc.tyre, "flagged_for_replacement", 1)

	from transport_logistics.transport_logistics.tasks import notify_users

	vehicle = doc.current_truck or doc.current_trailer or "an unfitted tyre"
	subject = f"Tyre {doc.tyre} FAILED depth inspection ({doc.tread_depth_mm}mm)"
	message = (
		f"Tyre {doc.tyre} measured {doc.tread_depth_mm}mm on "
		f"{doc.inspection_date} — at or below the minimum of "
		f"{doc.minimum_required_mm}mm. Currently on {vehicle}"
		f"{f', position {doc.current_position}' if doc.current_position else ''}. "
		"This tyre is flagged for replacement — please arrange it before further use."
	)
	notify_users(subject, message, "Tyre Depth Inspection", doc.name, priority="High")
