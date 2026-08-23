# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Consolidated fleet-wide Profit & Loss for a date range:

    Revenue
  - Fuel
  - Driver Costs
  - Maintenance
  - Tyres
  - Tolls
  - Insurance
  - Depreciation
  - Administration        (not tracked in this system — see note below)
  - Outsourced Transport  (not tracked in this system — see note below)
  = Net Transport Profit

Every other line pulls from real, submitted records already in this app.
Administration overhead and Outsourced Transport costs have no home in
this data model at all (no cost-center allocation, no subcontractor
doctype) — rather than omit them and leave the statement looking
incomplete, or silently fabricate a number, they're shown explicitly as
0 with a note, so it's clear they're a structural gap, not an oversight
or a rounding artifact.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, today, date_diff

from transport_logistics.transport_logistics.report.truck_cost_analysis.truck_cost_analysis import (
	get_depreciation,
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Line Item"), "fieldname": "line_item", "fieldtype": "Data", "width": 260},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 150},
		{"label": _("Note"), "fieldname": "note", "fieldtype": "Data", "width": 300},
	]


def get_data(filters):
	from_date = getdate(filters.get("from_date")) if filters.get("from_date") else getdate(today()).replace(day=1)
	to_date = getdate(filters.get("to_date")) if filters.get("to_date") else getdate(today())
	company = filters.get("company")

	company_clause = "and company = %(company)s" if company else ""
	values = {"from_date": from_date, "to_date": to_date}
	if company:
		values["company"] = company

	revenue = flt(frappe.db.sql(
		f"""
		select coalesce(sum(revenue), 0) from `tabTruck Trip`
		where status = 'Completed' and trip_date between %(from_date)s and %(to_date)s {company_clause}
		""",
		values,
	)[0][0])

	fuel = flt(frappe.db.sql(
		f"""
		select coalesce(sum(total_amount), 0) from `tabTruck Fuel Log`
		where docstatus = 1 and date between %(from_date)s and %(to_date)s {company_clause}
		""",
		values,
	)[0][0])

	driver_costs = flt(frappe.db.sql(
		f"""
		select coalesce(sum(total_amount), 0) from `tabDriver Mileage Payment`
		where docstatus = 1 and payment_date between %(from_date)s and %(to_date)s {company_clause}
		""",
		values,
	)[0][0])

	maintenance = flt(frappe.db.sql(
		f"""
		select coalesce(sum(total_cost), 0) from `tabTruck Maintenance Log`
		where docstatus = 1 and date between %(from_date)s and %(to_date)s {company_clause}
		""",
		values,
	)[0][0])

	tyres = flt(frappe.db.sql(
		f"""
		select coalesce(sum(cost), 0) from `tabTyre Movement Log`
		where docstatus = 1 and date between %(from_date)s and %(to_date)s {company_clause}
		""",
		values,
	)[0][0])

	tolls = flt(frappe.db.sql(
		f"""
		select coalesce(sum(amount), 0) from `tabTruck Expense`
		where docstatus = 1 and expense_type = 'Toll'
		and date between %(from_date)s and %(to_date)s {company_clause}
		""",
		values,
	)[0][0])

	insurance = flt(frappe.db.sql(
		f"""
		select coalesce(sum(amount), 0) from `tabTruck Expense`
		where docstatus = 1 and expense_type = 'Insurance'
		and date between %(from_date)s and %(to_date)s {company_clause}
		""",
		values,
	)[0][0])

	depreciation = get_fleet_depreciation(from_date, to_date, company)

	costs = fuel + driver_costs + maintenance + tyres + tolls + insurance + depreciation
	net_profit = revenue - costs

	rows = [
		{"line_item": _("Revenue"), "amount": revenue, "note": ""},
		{"line_item": _("− Fuel"), "amount": -fuel, "note": ""},
		{"line_item": _("− Driver Costs"), "amount": -driver_costs, "note": _("Driver Mileage Payments only")},
		{"line_item": _("− Maintenance"), "amount": -maintenance, "note": _("Includes spare parts issued via Workshop Job Card")},
		{"line_item": _("− Tyres"), "amount": -tyres, "note": ""},
		{"line_item": _("− Tolls"), "amount": -tolls, "note": ""},
		{"line_item": _("− Insurance"), "amount": -insurance, "note": ""},
		{"line_item": _("− Depreciation"), "amount": -depreciation, "note": _("Straight-line, prorated for the period")},
		{"line_item": _("− Administration"), "amount": 0, "note": _("Not tracked in this system")},
		{"line_item": _("− Outsourced Transport"), "amount": 0, "note": _("Not tracked in this system")},
		{"line_item": _("= Net Transport Profit"), "amount": net_profit, "note": ""},
	]

	return rows


def get_fleet_depreciation(from_date, to_date, company=None):
	period_days = date_diff(to_date, from_date) + 1

	filters = {}
	if company:
		filters["company"] = company

	trucks = frappe.get_all(
		"Truck",
		filters=filters,
		fields=["name", "purchase_cost", "purchase_date", "depreciation_rate_percent", "salvage_value", "company"],
	)

	total = 0
	for t in trucks:
		total += get_depreciation(frappe._dict(t), period_days)
	return flt(total)
