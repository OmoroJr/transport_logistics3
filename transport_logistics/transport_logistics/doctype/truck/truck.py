# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, nowdate


class Truck(Document):
	def validate(self):
		self.validate_dates()
		self.validate_single_truck_per_driver()

	def validate_dates(self):
		if self.purchase_date and getdate(self.purchase_date) > getdate(nowdate()):
			frappe.throw("Purchase Date cannot be in the future")

	def validate_single_truck_per_driver(self):
		if not self.assigned_driver:
			return
		existing = frappe.db.get_value(
			"Truck",
			{
				"assigned_driver": self.assigned_driver,
				"name": ["!=", self.name or ""],
				"status": ["!=", "Disposed"],
			},
			"name",
		)
		if existing:
			frappe.throw(
				f"Driver {self.assigned_driver} is already assigned to Truck {existing}. "
				"A driver can only be assigned to one truck at a time — unassign them from "
				"that truck first."
			)

	def on_trash(self):
		linked_doctypes = [
			"Truck Fuel Log",
			"Truck Maintenance Log",
			"Truck Expense",
			"Truck Trip",
			"Tyre Movement Log",
		]
		for dt in linked_doctypes:
			if frappe.db.exists(dt, {"truck": self.name}):
				frappe.throw(
					f"Cannot delete Truck {self.name}: it has linked {dt} records. "
					"Set status to Disposed instead."
				)


def get_loaded_truck_names():
	"""Trucks currently on an Ongoing, not-yet-offloaded trip — i.e. loaded
	and en route to (or waiting at) a client. This is the exact same
	definition the Truck Fleet Status report uses, so these dashboard
	Number Cards can never disagree with that report."""
	return frappe.db.get_all(
		"Truck Trip",
		filters={"status": "Ongoing", "offload_status": "Not Offloaded"},
		pluck="truck",
		distinct=True,
	)


@frappe.whitelist()
def get_loaded_truck_count():
	"""Number Card (Custom) backend: trucks loaded, en route to a client."""
	return {"value": len(get_loaded_truck_names()), "fieldtype": "Int"}


@frappe.whitelist()
def get_empty_truck_count():
	"""Number Card (Custom) backend: trucks empty and available — every
	truck that isn't currently in get_loaded_truck_names()."""
	total_trucks = frappe.db.count("Truck")
	loaded = len(get_loaded_truck_names())
	return {"value": max(total_trucks - loaded, 0), "fieldtype": "Int"}
