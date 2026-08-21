# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Truck Cost Analysis (see that report) gives one summarized row per truck.
This report is the drill-down: one row per individual transaction across
every cost-bearing doctype — General Expenses, Fuel, Tyres, Maintenance
(including spare parts issued via Workshop Job Card, which flows into Truck
Maintenance Log on submit), and Accidents — so a manager can see exactly
which transactions make up a truck's costs, not just the totals.
"""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	return columns, data, None, chart


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 95},
		{"label": _("Truck"), "fieldname": "truck", "fieldtype": "Link", "options": "Truck", "width": 110},
		{"label": _("Category"), "fieldname": "category", "fieldtype": "Data", "width": 110},
		{"label": _("Reference"), "fieldname": "reference_name", "fieldtype": "Dynamic Link", "options": "reference_doctype", "width": 140},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 300},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 120},
	]


def get_data(filters):
	rows = []
	rows += get_general_expense_rows(filters)
	rows += get_fuel_rows(filters)
	rows += get_tyre_rows(filters)
	rows += get_maintenance_rows(filters)
	rows += get_accident_rows(filters)

	if filters.get("expense_category"):
		rows = [r for r in rows if r["category"] == filters.get("expense_category")]

	rows.sort(key=lambda r: r.get("date") or "", reverse=True)
	return rows


def _conditions(filters, date_field="date", truck_field="truck", company_field="company"):
	conditions = " and docstatus = 1"
	values = {}
	if filters.get("truck"):
		conditions += f" and {truck_field} = %(truck)s"
		values["truck"] = filters.get("truck")
	if filters.get("company"):
		conditions += f" and {company_field} = %(company)s"
		values["company"] = filters.get("company")
	if filters.get("from_date"):
		conditions += f" and {date_field} >= %(from_date)s"
		values["from_date"] = filters.get("from_date")
	if filters.get("to_date"):
		conditions += f" and {date_field} <= %(to_date)s"
		values["to_date"] = filters.get("to_date")
	return conditions, values


def get_general_expense_rows(filters):
	conditions, values = _conditions(filters)
	records = frappe.db.sql(
		f"""
		select name, truck, date, expense_type, amount, reference_no, remarks, company
		from `tabTruck Expense`
		where 1=1 {conditions}
		""",
		values,
		as_dict=True,
	)
	rows = []
	for r in records:
		desc = r.expense_type
		if r.reference_no:
			desc += f" — Ref: {r.reference_no}"
		if r.remarks:
			desc += f" — {r.remarks}"
		rows.append({
			"date": r.date, "truck": r.truck, "category": "General Expense",
			"reference_doctype": "Truck Expense", "reference_name": r.name,
			"description": desc, "amount": flt(r.amount), "company": r.company,
		})
	return rows


def get_fuel_rows(filters):
	conditions, values = _conditions(filters)
	records = frappe.db.sql(
		f"""
		select name, truck, date, fuel_qty_litres, total_amount, reason_for_fuelling,
		       extra_fuel_litres, fuel_station, company
		from `tabTruck Fuel Log`
		where 1=1 {conditions}
		""",
		values,
		as_dict=True,
	)
	rows = []
	for r in records:
		desc = f"{flt(r.fuel_qty_litres, 1)} L ({r.reason_for_fuelling})"
		if r.fuel_station:
			desc += f" at {r.fuel_station}"
		if flt(r.extra_fuel_litres) > 0:
			desc += f" — incl. {flt(r.extra_fuel_litres, 1)} L extra"
		rows.append({
			"date": r.date, "truck": r.truck, "category": "Fuel",
			"reference_doctype": "Truck Fuel Log", "reference_name": r.name,
			"description": desc, "amount": flt(r.total_amount), "company": r.company,
		})
	return rows


def get_tyre_rows(filters):
	conditions, values = _conditions(filters)
	records = frappe.db.sql(
		f"""
		select name, truck, date, tyre, movement_type, position, cost, vendor, company
		from `tabTyre Movement Log`
		where cost > 0 {conditions}
		""",
		values,
		as_dict=True,
	)
	rows = []
	for r in records:
		desc = f"Tyre {r.tyre} — {r.movement_type}"
		if r.position:
			desc += f" ({r.position})"
		if r.vendor:
			desc += f" — {r.vendor}"
		rows.append({
			"date": r.date, "truck": r.truck, "category": "Tyre",
			"reference_doctype": "Tyre Movement Log", "reference_name": r.name,
			"description": desc, "amount": flt(r.cost), "company": r.company,
		})
	return rows


def get_maintenance_rows(filters):
	"""Truck Maintenance Log covers both manually logged maintenance and
	Workshop Job Cards (which auto-create one on submit), so spare part
	issuance costs show up here without double-counting the Job Card too."""
	conditions, values = _conditions(filters)
	records = frappe.db.sql(
		f"""
		select name, truck, date, maintenance_type, description, workshop,
		       parts_cost, labour_cost, other_cost, total_cost, company
		from `tabTruck Maintenance Log`
		where 1=1 {conditions}
		""",
		values,
		as_dict=True,
	)
	rows = []
	for r in records:
		desc = r.maintenance_type
		if r.workshop:
			desc += f" at {r.workshop}"
		if flt(r.parts_cost) > 0:
			desc += f" — Parts {flt(r.parts_cost, 2)}"
		if r.description:
			desc += f" — {r.description}"
		rows.append({
			"date": r.date, "truck": r.truck, "category": "Maintenance",
			"reference_doctype": "Truck Maintenance Log", "reference_name": r.name,
			"description": desc, "amount": flt(r.total_cost), "company": r.company,
		})
	return rows


def get_accident_rows(filters):
	conditions, values = _conditions(filters, date_field="date(date_of_accident)")
	records = frappe.db.sql(
		f"""
		select name, truck, date_of_accident, severity, accident_type,
		       total_cost, claim_amount_recovered, net_cost, company
		from `tabAccident Report`
		where 1=1 {conditions}
		""",
		values,
		as_dict=True,
	)
	rows = []
	for r in records:
		desc = f"{r.accident_type} ({r.severity})"
		if flt(r.claim_amount_recovered) > 0:
			desc += f" — {flt(r.claim_amount_recovered, 2)} recovered from insurance"
		rows.append({
			"date": r.date_of_accident.date() if hasattr(r.date_of_accident, "date") else r.date_of_accident,
			"truck": r.truck, "category": "Accident",
			"reference_doctype": "Accident Report", "reference_name": r.name,
			"description": desc, "amount": flt(r.net_cost), "company": r.company,
		})
	return rows


def get_chart(data):
	if not data:
		return None
	totals = {}
	for row in data:
		totals[row["category"]] = totals.get(row["category"], 0) + flt(row["amount"])
	return {
		"data": {
			"labels": list(totals.keys()),
			"datasets": [{"name": "Amount", "values": [flt(v, 2) for v in totals.values()]}],
		},
		"type": "pie",
	}
