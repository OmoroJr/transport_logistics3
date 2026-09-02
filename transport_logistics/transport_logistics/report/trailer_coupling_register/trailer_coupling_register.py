# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Event-level register of every Trailer Coupling Log entry (each Coupled /
Decoupled action, with odometer and manager-approval detail). Complements
Trailer Utilization, which reconstructs these same logs into aggregated
coupled/uncoupled day counts — this report is the raw transaction list.
"""

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	summary = get_summary(data)
	return columns, data, None, chart, summary


def get_columns():
	return [
		{"label": _("Log"), "fieldname": "name", "fieldtype": "Link", "options": "Trailer Coupling Log", "width": 130},
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 95},
		{"label": _("Trailer"), "fieldname": "trailer", "fieldtype": "Link", "options": "Trailer", "width": 100},
		{"label": _("Trailer Reg No"), "fieldname": "trailer_registration_number", "fieldtype": "Data", "width": 120},
		{"label": _("Action"), "fieldname": "action", "fieldtype": "Data", "width": 90},
		{"label": _("Truck"), "fieldname": "truck", "fieldtype": "Link", "options": "Truck", "width": 100},
		{"label": _("Truck Reg No"), "fieldname": "truck_registration_number", "fieldtype": "Data", "width": 120},
		{"label": _("Odometer (Km)"), "fieldname": "odometer_reading", "fieldtype": "Float", "width": 100},
		{"label": _("Approval Status"), "fieldname": "manager_approval_status", "fieldtype": "Data", "width": 120},
		{"label": _("Approved By"), "fieldname": "approved_by", "fieldtype": "Link", "options": "User", "width": 110},
		{"label": _("Approved On"), "fieldname": "approved_on", "fieldtype": "Datetime", "width": 140},
		{"label": _("Approval Remarks"), "fieldname": "approval_remarks", "fieldtype": "Data", "width": 180},
		{"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 180},
		{"label": _("Status"), "fieldname": "docstatus_label", "fieldtype": "Data", "width": 90},
	]


def get_data(filters):
	conditions, values = get_conditions(filters)

	rows = frappe.db.sql(
		f"""
		select
			tcl.name, tcl.date, tcl.trailer, tr.registration_number as trailer_registration_number,
			tcl.action, tcl.truck, tk.registration_number as truck_registration_number,
			tcl.odometer_reading, tcl.manager_approval_status, tcl.approved_by,
			tcl.approved_on, tcl.approval_remarks, tcl.remarks, tcl.docstatus
		from `tabTrailer Coupling Log` tcl
		left join `tabTrailer` tr on tr.name = tcl.trailer
		left join `tabTruck` tk on tk.name = tcl.truck
		where 1=1 {conditions}
		order by tcl.date desc, tcl.name desc
		""",
		values,
		as_dict=True,
	)

	docstatus_label = {0: _("Draft"), 1: _("Submitted"), 2: _("Cancelled")}
	for row in rows:
		row["docstatus_label"] = docstatus_label.get(row.docstatus)

	return rows


def get_conditions(filters):
	conditions = ""
	values = {}

	if not filters.get("include_unsubmitted"):
		conditions += " and tcl.docstatus = 1"

	if filters.get("from_date"):
		conditions += " and tcl.date >= %(from_date)s"
		values["from_date"] = filters.get("from_date")
	if filters.get("to_date"):
		conditions += " and tcl.date <= %(to_date)s"
		values["to_date"] = filters.get("to_date")
	if filters.get("trailer"):
		conditions += " and tcl.trailer = %(trailer)s"
		values["trailer"] = filters.get("trailer")
	if filters.get("truck"):
		conditions += " and tcl.truck = %(truck)s"
		values["truck"] = filters.get("truck")
	if filters.get("action"):
		conditions += " and tcl.action = %(action)s"
		values["action"] = filters.get("action")
	if filters.get("manager_approval_status"):
		conditions += " and tcl.manager_approval_status = %(manager_approval_status)s"
		values["manager_approval_status"] = filters.get("manager_approval_status")

	return conditions, values


def get_chart(data):
	if not data:
		return None

	action_counts = {}
	for row in data:
		key = row.action or _("Unknown")
		action_counts[key] = action_counts.get(key, 0) + 1

	return {
		"data": {
			"labels": list(action_counts.keys()),
			"datasets": [
				{"name": "Event Count", "values": list(action_counts.values())},
			],
		},
		"type": "bar",
		"colors": ["#8E44AD"],
	}


def get_summary(data):
	if not data:
		return []

	coupled = [r for r in data if r.action == "Coupled"]
	decoupled = [r for r in data if r.action == "Decoupled"]
	pending = [r for r in data if r.manager_approval_status == "Pending Approval"]

	return [
		{"label": _("Total Events"), "value": len(data), "datatype": "Int"},
		{"label": _("Coupled Events"), "value": len(coupled), "datatype": "Int"},
		{"label": _("Decoupled Events"), "value": len(decoupled), "datatype": "Int"},
		{
			"label": _("Pending Approval"),
			"value": len(pending),
			"datatype": "Int",
			"indicator": "Red" if pending else "Green",
		},
	]
