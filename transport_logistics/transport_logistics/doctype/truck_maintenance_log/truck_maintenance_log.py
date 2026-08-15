# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class TruckMaintenanceLog(Document):
	def validate(self):
		set_total_cost(self)


def set_total_cost(doc, method=None):
	doc.total_cost = (doc.parts_cost or 0) + (doc.labour_cost or 0) + (doc.other_cost or 0)


def update_truck_status(doc, method=None):
	"""If a breakdown/repair is logged, flag the truck as Under Maintenance."""
	if doc.maintenance_type in ("Repair", "Breakdown"):
		frappe.db.set_value("Truck", doc.truck, "status", "Under Maintenance")
