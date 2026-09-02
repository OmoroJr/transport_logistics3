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
		{"label": _("Accident Report"), "fieldname": "name", "fieldtype": "Link", "options": "Accident Report", "width": 130},
		{"label": _("Date"), "fieldname": "date_of_accident", "fieldtype": "Datetime", "width": 140},
		{"label": _("Truck"), "fieldname": "truck", "fieldtype": "Link", "options": "Truck", "width": 100},
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Link", "options": "Employee", "width": 110},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 120},
		{"label": _("Severity"), "fieldname": "severity", "fieldtype": "Data", "width": 85},
		{"label": _("Type"), "fieldname": "accident_type", "fieldtype": "Data", "width": 120},
		{"label": _("At Fault"), "fieldname": "at_fault", "fieldtype": "Data", "width": 90},
		{"label": _("Location"), "fieldname": "location", "fieldtype": "Data", "width": 120},
		{"label": _("Injuries"), "fieldname": "injuries", "fieldtype": "Check", "width": 70},
		{"label": _("Fatalities"), "fieldname": "fatalities", "fieldtype": "Check", "width": 75},
		{"label": _("3rd Party Involved"), "fieldname": "third_party_involved", "fieldtype": "Check", "width": 100},
		{"label": _("Police Report"), "fieldname": "police_report_filed", "fieldtype": "Check", "width": 90},
		{"label": _("Insurance Claim"), "fieldname": "insurance_claim_filed", "fieldtype": "Check", "width": 95},
		{"label": _("Repair Cost"), "fieldname": "repair_cost", "fieldtype": "Currency", "width": 100},
		{"label": _("Other Cost"), "fieldname": "other_cost", "fieldtype": "Currency", "width": 95},
		{"label": _("Total Cost"), "fieldname": "total_cost", "fieldtype": "Currency", "width": 100},
		{"label": _("Claim Recovered"), "fieldname": "claim_amount_recovered", "fieldtype": "Currency", "width": 110},
		{"label": _("Net Cost"), "fieldname": "net_cost", "fieldtype": "Currency", "width": 95},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
	]


def get_data(filters):
	conditions, values = get_conditions(filters)

	rows = frappe.db.sql(
		f"""
		select
			ar.name, ar.date_of_accident, ar.truck, ar.driver, ar.company,
			ar.severity, ar.accident_type, ar.at_fault, ar.location,
			ar.injuries, ar.fatalities, ar.third_party_involved,
			ar.police_report_filed, ar.insurance_claim_filed,
			ar.repair_cost, ar.other_cost, ar.total_cost,
			ar.claim_amount_recovered, ar.net_cost, ar.status
		from `tabAccident Report` ar
		where 1=1 {conditions}
		order by ar.date_of_accident desc
		""",
		values,
		as_dict=True,
	)

	return rows


def get_conditions(filters):
	conditions = ""
	values = {}

	if not filters.get("include_unsubmitted"):
		conditions += " and ar.docstatus = 1"

	if filters.get("company"):
		conditions += " and ar.company = %(company)s"
		values["company"] = filters.get("company")
	if filters.get("truck"):
		conditions += " and ar.truck = %(truck)s"
		values["truck"] = filters.get("truck")
	if filters.get("driver"):
		conditions += " and ar.driver = %(driver)s"
		values["driver"] = filters.get("driver")
	if filters.get("severity"):
		conditions += " and ar.severity = %(severity)s"
		values["severity"] = filters.get("severity")
	if filters.get("accident_type"):
		conditions += " and ar.accident_type = %(accident_type)s"
		values["accident_type"] = filters.get("accident_type")
	if filters.get("at_fault"):
		conditions += " and ar.at_fault = %(at_fault)s"
		values["at_fault"] = filters.get("at_fault")
	if filters.get("status"):
		conditions += " and ar.status = %(status)s"
		values["status"] = filters.get("status")
	if filters.get("from_date"):
		conditions += " and date(ar.date_of_accident) >= %(from_date)s"
		values["from_date"] = filters.get("from_date")
	if filters.get("to_date"):
		conditions += " and date(ar.date_of_accident) <= %(to_date)s"
		values["to_date"] = filters.get("to_date")
	if filters.get("only_with_injuries"):
		conditions += " and (ar.injuries = 1 or ar.fatalities = 1)"

	return conditions, values


def get_chart(data):
	if not data:
		return None

	type_costs = {}
	for row in data:
		key = row.accident_type or _("Unspecified")
		type_costs[key] = type_costs.get(key, 0) + flt(row.total_cost)

	return {
		"data": {
			"labels": list(type_costs.keys()),
			"datasets": [
				{"name": "Total Cost", "values": [flt(v, 2) for v in type_costs.values()]},
			],
		},
		"type": "bar",
		"colors": ["#C0392B"],
	}


def get_summary(data):
	if not data:
		return []

	total_cost = sum(flt(r.total_cost) for r in data)
	net_cost = sum(flt(r.net_cost) for r in data)
	injury_rows = [r for r in data if r.injuries]
	fatality_rows = [r for r in data if r.fatalities]
	at_fault_rows = [r for r in data if r.at_fault == "Driver"]

	return [
		{"label": _("Total Accidents"), "value": len(data), "datatype": "Int"},
		{"label": _("Total Cost"), "value": flt(total_cost, 2), "datatype": "Currency"},
		{"label": _("Net Cost (After Recovery)"), "value": flt(net_cost, 2), "datatype": "Currency"},
		{
			"label": _("Accidents With Injuries"),
			"value": len(injury_rows),
			"datatype": "Int",
			"indicator": "Red" if injury_rows else "Green",
		},
		{
			"label": _("Fatalities"),
			"value": len(fatality_rows),
			"datatype": "Int",
			"indicator": "Red" if fatality_rows else "Green",
		},
		{"label": _("Driver At Fault"), "value": len(at_fault_rows), "datatype": "Int"},
	]
