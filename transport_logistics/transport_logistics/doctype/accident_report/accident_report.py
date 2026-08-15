# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class AccidentReport(Document):
	def validate(self):
		set_cost_fields(self)


def set_cost_fields(doc, method=None):
	doc.total_cost = flt(doc.repair_cost) + flt(doc.other_cost)
	doc.net_cost = doc.total_cost - flt(doc.claim_amount_recovered)


def update_truck_status(doc, method=None):
	"""Major/Fatal accidents automatically flag the truck as Under Maintenance
	until it's inspected and cleared back to Active by the fleet office."""
	if doc.severity in ("Major", "Fatal"):
		frappe.db.set_value("Truck", doc.truck, "status", "Under Maintenance")


def notify_high_severity(doc, method=None):
	"""Immediately alerts the notify role (Transport Logistics Settings)
	for Major/Fatal accidents, rather than waiting for any scheduled job."""
	if doc.severity not in ("Major", "Fatal"):
		return

	from transport_logistics.transport_logistics.tasks import notify_users

	subject = f"{doc.severity} accident reported: Truck {doc.truck} ({doc.name})"
	message = (
		f"A {doc.severity} accident was reported for Truck {doc.truck} on "
		f"{frappe.utils.format_datetime(doc.date_of_accident)}. "
		f"Location: {doc.location or 'not specified'}. "
		f"{'Injuries reported. ' if doc.injuries else ''}"
		f"{'Fatalities reported. ' if doc.fatalities else ''}"
		f"Please review Accident Report {doc.name} immediately."
	)
	notify_users(subject, message, "Accident Report", doc.name, priority="High")
