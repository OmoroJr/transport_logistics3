# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Consolidated historical log of every Gate Pass (Vehicle and Pedestrian),
for a selected date range. This is the audit trail security/reception
would hand over for a gate register review -- who/what came in, when,
why, and when it left. For who is on site right now, see the
"Visitors On Site" report instead.
"""

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	return columns, data, None, chart


def get_columns():
	return [
		{"label": _("Gate Pass"), "fieldname": "name", "fieldtype": "Link", "options": "Gate Pass", "width": 150},
		{"label": _("Pass Type"), "fieldname": "pass_type", "fieldtype": "Data", "width": 90},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
		{"label": _("Purpose"), "fieldname": "purpose", "fieldtype": "Data", "width": 110},
		{"label": _("Truck"), "fieldname": "truck", "fieldtype": "Link", "options": "Truck", "width": 110},
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Link", "options": "Employee", "width": 130},
		{"label": _("Visitor Name"), "fieldname": "visitor_name", "fieldtype": "Data", "width": 140},
		{"label": _("Visitor Card No."), "fieldname": "visitor_card_number", "fieldtype": "Data", "width": 110},
		{"label": _("ID / Passport No."), "fieldname": "id_number", "fieldtype": "Data", "width": 120},
		{"label": _("Host / Dept."), "fieldname": "host_employee", "fieldtype": "Link", "options": "Employee", "width": 130},
		{"label": _("Gate In"), "fieldname": "gate_in_time", "fieldtype": "Datetime", "width": 150},
		{"label": _("Gate Out"), "fieldname": "gate_out_time", "fieldtype": "Datetime", "width": 150},
		{"label": _("Duration (Hrs)"), "fieldname": "duration_hours", "fieldtype": "Float", "width": 100},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 120},
		{"label": _("Security Officer"), "fieldname": "security_officer", "fieldtype": "Data", "width": 130},
	]


def get_data(filters):
	conditions, values = _build_conditions(filters)

	return frappe.db.sql(
		f"""
		select
			name, pass_type, status, purpose, truck, driver, visitor_name,
			visitor_card_number, id_number, host_employee, gate_in_time,
			gate_out_time, duration_hours, company, security_officer
		from `tabGate Pass`
		where {conditions}
		order by gate_in_time desc
		""",
		values,
		as_dict=True,
	)


def _build_conditions(filters):
	conditions = ["1=1"]
	values = {}

	if filters.get("company"):
		conditions.append("company = %(company)s")
		values["company"] = filters.company
	if filters.get("pass_type"):
		conditions.append("pass_type = %(pass_type)s")
		values["pass_type"] = filters.pass_type
	if filters.get("status"):
		conditions.append("status = %(status)s")
		values["status"] = filters.status
	if filters.get("truck"):
		conditions.append("truck = %(truck)s")
		values["truck"] = filters.truck
	if filters.get("visitor_card_number"):
		conditions.append("visitor_card_number = %(visitor_card_number)s")
		values["visitor_card_number"] = filters.visitor_card_number
	if filters.get("from_date"):
		conditions.append("date(gate_in_time) >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("date(gate_in_time) <= %(to_date)s")
		values["to_date"] = filters.to_date

	return " and ".join(conditions), values


def get_chart(data):
	if not data:
		return None

	counts = {}
	for row in data:
		key = row.get("purpose") or _("Unspecified")
		counts[key] = counts.get(key, 0) + 1

	return {
		"data": {
			"labels": list(counts.keys()),
			"datasets": [{"name": _("Gate Passes"), "values": list(counts.values())}],
		},
		"type": "bar",
		"colors": ["#2E86C1"],
	}
