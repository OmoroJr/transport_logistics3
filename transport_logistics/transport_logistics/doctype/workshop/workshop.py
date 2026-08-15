# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

# Single source of truth for "a Job Card is currently occupying a bay" —
# imported by workshop_job_card.py's capacity check so the two can never
# disagree about which statuses count as active.
ACTIVE_JOB_STATUSES = ("Open", "In Progress", "Awaiting Parts")


class Workshop(Document):
	def validate(self):
		if self.bay_count is not None and self.bay_count < 0:
			frappe.throw("Number of Bays cannot be negative")


@frappe.whitelist()
def get_bay_occupancy(workshop):
	"""Used by the form's dashboard indicator to show e.g. '2 / 3 bays in use'."""
	bay_count = frappe.db.get_value("Workshop", workshop, "bay_count") or 0
	active_jobs = frappe.db.count(
		"Workshop Job Card",
		{"workshop": workshop, "status": ["in", ACTIVE_JOB_STATUSES], "docstatus": ["!=", 2]},
	)
	return {"bay_count": bay_count, "active_jobs": active_jobs}
