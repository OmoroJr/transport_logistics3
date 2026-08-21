# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Single consolidated view of the five actions that require System Manager
approval: Driver Change, Trailer Decoupling, Extra Fuel, Tyre Change, and
Spare Part Issuance. Each source doctype carries its own
manager_approval_status/approved_by/approved_on fields (see
manager_approval.py) — this report just unions them into one list so a
System Manager can see everything awaiting a decision (or already decided)
in one place, across all five doctypes and all trucks.
"""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Request Type"), "fieldname": "request_type", "fieldtype": "Data", "width": 140},
		{"label": _("Reference"), "fieldname": "reference_name", "fieldtype": "Dynamic Link", "options": "reference_doctype", "width": 140},
		{"label": _("Truck"), "fieldname": "truck", "fieldtype": "Link", "options": "Truck", "width": 110},
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 95},
		{"label": _("Details"), "fieldname": "details", "fieldtype": "Data", "width": 260},
		{"label": _("Requested By"), "fieldname": "requested_by", "fieldtype": "Data", "width": 150},
		{"label": _("Approval Status"), "fieldname": "status", "fieldtype": "Data", "width": 130},
		{"label": _("Approved/Rejected By"), "fieldname": "approved_by", "fieldtype": "Data", "width": 150},
		{"label": _("Approved/Rejected On"), "fieldname": "approved_on", "fieldtype": "Datetime", "width": 160},
	]


def get_data(filters):
	rows = []
	rows += get_driver_change_rows(filters)
	rows += get_trailer_decoupling_rows(filters)
	rows += get_extra_fuel_rows(filters)
	rows += get_tyre_change_rows(filters)
	rows += get_spare_part_rows(filters)

	if filters.get("request_type"):
		rows = [r for r in rows if r["request_type"] == filters.get("request_type")]
	if filters.get("status"):
		rows = [r for r in rows if r["status"] == filters.get("status")]

	rows.sort(key=lambda r: r.get("date") or "", reverse=True)
	return rows


def _base_conditions(filters, table, company_field="company", truck_field="truck", date_field="date"):
	conditions = " and manager_approval_status != 'Not Required'"
	values = {}
	if filters.get("company"):
		conditions += f" and {company_field} = %(company)s"
		values["company"] = filters.get("company")
	if filters.get("truck"):
		conditions += f" and {truck_field} = %(truck)s"
		values["truck"] = filters.get("truck")
	if filters.get("from_date"):
		conditions += f" and {date_field} >= %(from_date)s"
		values["from_date"] = filters.get("from_date")
	if filters.get("to_date"):
		conditions += f" and {date_field} <= %(to_date)s"
		values["to_date"] = filters.get("to_date")
	return conditions, values


def get_driver_change_rows(filters):
	conditions, values = _base_conditions(filters, "Truck Trip", date_field="trip_date")
	records = frappe.db.sql(
		f"""
		select name, truck, company, trip_date as date, driver, new_driver_requested,
		       driver_change_reason, owner, manager_approval_status, approved_by, approved_on
		from `tabTruck Trip`
		where new_driver_requested is not null and new_driver_requested != '' {conditions}
		""",
		values,
		as_dict=True,
	)
	rows = []
	for r in records:
		rows.append({
			"request_type": "Driver Change",
			"reference_doctype": "Truck Trip",
			"reference_name": r.name,
			"truck": r.truck,
			"date": r.date,
			"details": f"{r.driver or '—'} -> {r.new_driver_requested}"
			+ (f" ({r.driver_change_reason})" if r.driver_change_reason else ""),
			"requested_by": r.owner,
			"status": r.manager_approval_status,
			"approved_by": r.approved_by,
			"approved_on": r.approved_on,
		})
	return rows


def get_trailer_decoupling_rows(filters):
	conditions, values = _base_conditions(filters, "Trailer Coupling Log")
	records = frappe.db.sql(
		f"""
		select name, truck, trailer, date, owner, manager_approval_status, approved_by, approved_on
		from `tabTrailer Coupling Log`
		where action = 'Decoupled' {conditions}
		""",
		values,
		as_dict=True,
	)
	rows = []
	for r in records:
		rows.append({
			"request_type": "Trailer Decoupling",
			"reference_doctype": "Trailer Coupling Log",
			"reference_name": r.name,
			"truck": r.truck,
			"date": r.date,
			"details": f"Trailer {r.trailer} decoupled from {r.truck}",
			"requested_by": r.owner,
			"status": r.manager_approval_status,
			"approved_by": r.approved_by,
			"approved_on": r.approved_on,
		})
	return rows


def get_extra_fuel_rows(filters):
	conditions, values = _base_conditions(filters, "Truck Fuel Log")
	records = frappe.db.sql(
		f"""
		select name, truck, company, date, extra_fuel_litres, extra_fuel_reason,
		       owner, manager_approval_status, approved_by, approved_on
		from `tabTruck Fuel Log`
		where extra_fuel_litres > 0 {conditions}
		""",
		values,
		as_dict=True,
	)
	rows = []
	for r in records:
		rows.append({
			"request_type": "Extra Fuel",
			"reference_doctype": "Truck Fuel Log",
			"reference_name": r.name,
			"truck": r.truck,
			"date": r.date,
			"details": f"{flt(r.extra_fuel_litres, 1)} L over standard"
			+ (f" — {r.extra_fuel_reason}" if r.extra_fuel_reason else ""),
			"requested_by": r.owner,
			"status": r.manager_approval_status,
			"approved_by": r.approved_by,
			"approved_on": r.approved_on,
		})
	return rows


def get_tyre_change_rows(filters):
	conditions, values = _base_conditions(filters, "Tyre Movement Log")
	records = frappe.db.sql(
		f"""
		select name, truck, company, date, tyre, movement_type, position,
		       owner, manager_approval_status, approved_by, approved_on
		from `tabTyre Movement Log`
		where movement_type in ('Fitted', 'Removed') {conditions}
		""",
		values,
		as_dict=True,
	)
	rows = []
	for r in records:
		rows.append({
			"request_type": "Tyre Change",
			"reference_doctype": "Tyre Movement Log",
			"reference_name": r.name,
			"truck": r.truck,
			"date": r.date,
			"details": f"{r.movement_type} — Tyre {r.tyre} ({r.position or 'position n/a'})",
			"requested_by": r.owner,
			"status": r.manager_approval_status,
			"approved_by": r.approved_by,
			"approved_on": r.approved_on,
		})
	return rows


def get_spare_part_rows(filters):
	conditions, values = _base_conditions(filters, "Workshop Job Card", date_field="date_opened")
	records = frappe.db.sql(
		f"""
		select name, truck, company, date_opened as date, parts_cost,
		       owner, manager_approval_status, approved_by, approved_on
		from `tabWorkshop Job Card`
		where parts_cost > 0 {conditions}
		""",
		values,
		as_dict=True,
	)
	rows = []
	for r in records:
		rows.append({
			"request_type": "Spare Part Issuance",
			"reference_doctype": "Workshop Job Card",
			"reference_name": r.name,
			"truck": r.truck,
			"date": r.date,
			"details": f"Parts cost {flt(r.parts_cost, 2)}",
			"requested_by": r.owner,
			"status": r.manager_approval_status,
			"approved_by": r.approved_by,
			"approved_on": r.approved_on,
		})
	return rows
