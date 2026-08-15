# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DriverSafetyIncident(Document):
	def validate(self):
		default_points_if_unset(self)


def default_points_if_unset(doc, method=None):
	if doc.points_deducted:
		return
	defaults = {"Low": 2, "Medium": 5, "High": 10}
	doc.points_deducted = defaults.get(doc.severity, 2)


def notify_high_severity(doc, method=None):
	"""Immediately alerts the notify role for High-severity safety incidents."""
	if doc.severity != "High":
		return

	from transport_logistics.transport_logistics.tasks import notify_users

	subject = f"High severity safety incident: Driver {doc.driver} ({doc.name})"
	message = (
		f"A High severity {doc.incident_type} was logged for Driver {doc.driver}"
		f"{' on Truck ' + doc.truck if doc.truck else ''} on {doc.date}. "
		f"Action taken so far: {doc.action_taken or 'none recorded'}. "
		f"Please review Driver Safety Incident {doc.name}."
	)
	notify_users(subject, message, "Driver Safety Incident", doc.name, priority="High")
