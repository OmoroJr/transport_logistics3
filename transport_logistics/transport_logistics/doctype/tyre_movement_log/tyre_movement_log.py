# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class TyreMovementLog(Document):
	def validate(self):
		validate_movement(self)


def validate_movement(doc, method=None):
	if doc.movement_type in ("Fitted", "Rotated") and not (doc.truck and doc.position):
		frappe.throw("Truck and Position are mandatory for Fitted / Rotated movements")

	if doc.movement_type == "Fitted":
		existing = frappe.db.exists(
			"Tyre Movement Log",
			{
				"truck": doc.truck,
				"position": doc.position,
				"movement_type": "Fitted",
				"docstatus": 1,
				"name": ["!=", doc.name or ""],
			},
		)
		# only block if that position hasn't since been vacated
		if existing:
			last_on_position = frappe.db.sql(
				"""
				select movement_type from `tabTyre Movement Log`
				where truck=%s and position=%s and docstatus=1 and name != %s
				order by date desc, creation desc limit 1
				""",
				(doc.truck, doc.position, doc.name or ""),
			)
			if last_on_position and last_on_position[0][0] == "Fitted":
				frappe.throw(
					f"Position {doc.position} on Truck {doc.truck} already has a tyre fitted. "
					"Record a Removed movement first."
				)


def apply_movement(doc, method=None):
	tyre = frappe.get_doc("Tyre", doc.tyre)

	if doc.movement_type == "Fitted":
		tyre.status = "Fitted"
		tyre.current_truck = doc.truck
		tyre.current_position = doc.position
		tyre.fitted_at_odometer = doc.odometer_reading or 0

	elif doc.movement_type == "Removed":
		_accumulate_km(tyre, doc)
		tyre.status = "In Stock"
		tyre.current_truck = None
		tyre.current_position = None
		tyre.fitted_at_odometer = 0

	elif doc.movement_type == "Rotated":
		_accumulate_km(tyre, doc)
		tyre.current_position = doc.position
		tyre.fitted_at_odometer = doc.odometer_reading or 0

	elif doc.movement_type == "Retreaded":
		_accumulate_km(tyre, doc)
		tyre.status = "In Stock"
		tyre.current_truck = None
		tyre.current_position = None
		tyre.fitted_at_odometer = 0
		tyre.retread_count = (tyre.retread_count or 0) + 1

	elif doc.movement_type == "Scrapped":
		_accumulate_km(tyre, doc)
		tyre.status = "Scrapped"
		tyre.current_truck = None
		tyre.current_position = None

	tyre.save(ignore_permissions=True)


def reverse_movement(doc, method=None):
	# On cancellation, simply flag for manual review since re-deriving
	# state from movement history is safer than reversing deltas blindly.
	frappe.msgprint(
		f"Tyre Movement Log {doc.name} cancelled. Please verify Tyre {doc.tyre} "
		"current status/position manually.",
		alert=True,
	)


def _accumulate_km(tyre, doc):
	if doc.odometer_reading and tyre.fitted_at_odometer:
		km_run = doc.odometer_reading - tyre.fitted_at_odometer
		if km_run > 0:
			tyre.total_km_run = (tyre.total_km_run or 0) + km_run
