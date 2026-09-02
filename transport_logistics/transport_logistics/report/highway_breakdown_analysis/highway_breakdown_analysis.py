# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	summary = get_summary(data)
	return columns, data, None, chart, summary


def get_columns():
	return [
		{"label": _("Breakdown"), "fieldname": "name", "fieldtype": "Link", "options": "Highway Breakdown", "width": 130},
		{"label": _("Date/Time"), "fieldname": "date_time_of_breakdown", "fieldtype": "Datetime", "width": 140},
		{"label": _("Truck"), "fieldname": "truck", "fieldtype": "Link", "options": "Truck", "width": 100},
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Link", "options": "Employee", "width": 110},
		{"label": _("Truck Trip"), "fieldname": "truck_trip", "fieldtype": "Link", "options": "Truck Trip", "width": 110},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 120},
		{"label": _("Type"), "fieldname": "breakdown_type", "fieldtype": "Data", "width": 100},
		{"label": _("Location"), "fieldname": "location", "fieldtype": "Data", "width": 120},
		{"label": _("Recovery Required"), "fieldname": "recovery_required", "fieldtype": "Check", "width": 100},
		{"label": _("Towed"), "fieldname": "towed", "fieldtype": "Check", "width": 70},
		{"label": _("Downtime (Hrs)"), "fieldname": "downtime_hours", "fieldtype": "Float", "width": 100},
		{"label": _("Repair Cost"), "fieldname": "repair_cost", "fieldtype": "Currency", "width": 95},
		{"label": _("Towing Cost"), "fieldname": "towing_cost", "fieldtype": "Currency", "width": 95},
		{"label": _("Other Cost"), "fieldname": "other_cost", "fieldtype": "Currency", "width": 90},
		{"label": _("Total Cost"), "fieldname": "total_cost", "fieldtype": "Currency", "width": 100},
		{"label": _("Preventable"), "fieldname": "preventable", "fieldtype": "Check", "width": 85},
		{"label": _("Root Cause"), "fieldname": "root_cause", "fieldtype": "Data", "width": 160},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 130},
	]


def get_data(filters):
	conditions, values = get_conditions(filters)

	rows = frappe.db.sql(
		f"""
		select
			hb.name, hb.date_time_of_breakdown, hb.truck, hb.driver, hb.truck_trip,
			hb.company, hb.breakdown_type, hb.location,
			hb.recovery_required, hb.towed, hb.downtime_hours,
			hb.repair_cost, hb.towing_cost, hb.other_cost, hb.total_cost,
			hb.preventable, hb.root_cause, hb.status
		from `tabHighway Breakdown` hb
		where 1=1 {conditions}
		order by hb.date_time_of_breakdown desc
		""",
		values,
		as_dict=True,
	)

	return rows


def get_conditions(filters):
	conditions = ""
	values = {}

	if not filters.get("include_unsubmitted"):
		conditions += " and hb.docstatus = 1"

	if filters.get("company"):
		conditions += " and hb.company = %(company)s"
		values["company"] = filters.get("company")
	if filters.get("truck"):
		conditions += " and hb.truck = %(truck)s"
		values["truck"] = filters.get("truck")
	if filters.get("breakdown_type"):
		conditions += " and hb.breakdown_type = %(breakdown_type)s"
		values["breakdown_type"] = filters.get("breakdown_type")
	if filters.get("status"):
		conditions += " and hb.status = %(status)s"
		values["status"] = filters.get("status")
	if filters.get("preventable"):
		conditions += " and hb.preventable = 1"
	if filters.get("towed"):
		conditions += " and hb.towed = 1"
	if filters.get("from_date"):
		conditions += " and date(hb.date_time_of_breakdown) >= %(from_date)s"
		values["from_date"] = filters.get("from_date")
	if filters.get("to_date"):
		conditions += " and date(hb.date_time_of_breakdown) <= %(to_date)s"
		values["to_date"] = filters.get("to_date")

	return conditions, values


def get_chart(data):
	if not data:
		return None

	type_downtime = {}
	for row in data:
		key = row.breakdown_type or _("Unspecified")
		type_downtime[key] = type_downtime.get(key, 0) + flt(row.downtime_hours)

	return {
		"data": {
			"labels": list(type_downtime.keys()),
			"datasets": [
				{"name": "Downtime (Hrs)", "values": [flt(v, 1) for v in type_downtime.values()]},
			],
		},
		"type": "bar",
		"colors": ["#E67E22"],
	}


def get_summary(data):
	if not data:
		return []

	total_downtime = sum(flt(r.downtime_hours) for r in data)
	total_cost = sum(flt(r.total_cost) for r in data)
	preventable_rows = [r for r in data if r.preventable]
	towed_rows = [r for r in data if r.towed]

	return [
		{"label": _("Total Breakdowns"), "value": len(data), "datatype": "Int"},
		{"label": _("Total Downtime (Hrs)"), "value": flt(total_downtime, 1), "datatype": "Float"},
		{"label": _("Total Cost"), "value": flt(total_cost, 2), "datatype": "Currency"},
		{
			"label": _("Preventable Breakdowns"),
			"value": len(preventable_rows),
			"datatype": "Int",
			"indicator": "Red" if preventable_rows else "Green",
		},
		{"label": _("Towed to Workshop"), "value": len(towed_rows), "datatype": "Int"},
	]
