# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Live view of every Gate Pass still marked "In Yard" -- i.e. everyone and
every vehicle that has checked in but not yet checked out. This is the
roll-call / emergency-evacuation list, and the quickest way to look up
who a physical visitor card (see Gate Pass -> Visitor Card Number) is
currently checked out to. For historical records, see the
"Gate Pass Register" report instead.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime, time_diff_in_hours


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Gate Pass"), "fieldname": "name", "fieldtype": "Link", "options": "Gate Pass", "width": 150},
		{"label": _("Pass Type"), "fieldname": "pass_type", "fieldtype": "Data", "width": 90},
		{"label": _("Who / What"), "fieldname": "who", "fieldtype": "Data", "width": 180},
		{"label": _("Visitor Card No."), "fieldname": "visitor_card_number", "fieldtype": "Data", "width": 110},
		{"label": _("Purpose"), "fieldname": "purpose", "fieldtype": "Data", "width": 110},
		{"label": _("Host / Dept."), "fieldname": "host_employee", "fieldtype": "Link", "options": "Employee", "width": 130},
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Link", "options": "Employee", "width": 130},
		{"label": _("Gate In"), "fieldname": "gate_in_time", "fieldtype": "Datetime", "width": 150},
		{"label": _("Hours On Site"), "fieldname": "hours_on_site", "fieldtype": "Float", "width": 100},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 120},
		{"label": _("Security Officer"), "fieldname": "security_officer", "fieldtype": "Data", "width": 130},
	]


def get_data(filters):
	conditions, values = _build_conditions(filters)

	rows = frappe.db.sql(
		f"""
		select
			name, pass_type, purpose, truck, driver, visitor_name,
			visitor_card_number, host_employee, gate_in_time, company,
			security_officer
		from `tabGate Pass`
		where status = 'In Yard' and {conditions}
		order by gate_in_time asc
		""",
		values,
		as_dict=True,
	)

	now = now_datetime()
	data = []
	for row in rows:
		row["who"] = row.truck if row.pass_type == "Vehicle" else row.visitor_name
		row["hours_on_site"] = (
			round(time_diff_in_hours(now, row.gate_in_time), 2) if row.gate_in_time else 0
		)
		data.append(row)
	return data


def _build_conditions(filters):
	conditions = ["1=1"]
	values = {}

	if filters.get("company"):
		conditions.append("company = %(company)s")
		values["company"] = filters.company
	if filters.get("pass_type"):
		conditions.append("pass_type = %(pass_type)s")
		values["pass_type"] = filters.pass_type

	return " and ".join(conditions), values
