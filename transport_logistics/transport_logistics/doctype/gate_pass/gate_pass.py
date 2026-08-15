# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import time_diff_in_hours


class GatePass(Document):
	def validate(self):
		validate_pass_type(self)
		compute_status_and_duration(self)


def validate_pass_type(doc, method=None):
	if doc.pass_type == "Vehicle" and not doc.truck:
		frappe.throw("Truck is required for a Vehicle pass")
	if doc.pass_type == "Pedestrian" and not doc.visitor_name:
		frappe.throw("Visitor Name is required for a Pedestrian pass")


def compute_status_and_duration(doc, method=None):
	if doc.gate_out_time:
		if doc.gate_in_time and doc.gate_out_time < doc.gate_in_time:
			frappe.throw("Gate Out Time cannot be before Gate In Time")
		doc.status = "Departed"
		if doc.gate_in_time:
			doc.duration_hours = time_diff_in_hours(doc.gate_out_time, doc.gate_in_time)
	else:
		doc.status = "In Yard"
		doc.duration_hours = 0
