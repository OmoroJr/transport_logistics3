# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

# Points deducted from a starting score of 100 for each accident, by severity.
ACCIDENT_PENALTY = {"Minor": 5, "Moderate": 15, "Major": 30, "Fatal": 50}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	return columns, data, None, chart


def get_columns():
	return [
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Link", "options": "Employee", "width": 100},
		{"label": _("Driver Name"), "fieldname": "driver_name", "fieldtype": "Data", "width": 140},
		{"label": _("Accidents"), "fieldname": "accident_count", "fieldtype": "Int", "width": 90},
		{"label": _("At-Fault Accidents"), "fieldname": "at_fault_count", "fieldtype": "Int", "width": 120},
		{"label": _("Safety Incidents"), "fieldname": "incident_count", "fieldtype": "Int", "width": 110},
		{"label": _("Points Deducted"), "fieldname": "points_deducted", "fieldtype": "Int", "width": 110},
		{"label": _("Accident Cost"), "fieldname": "accident_cost", "fieldtype": "Currency", "width": 110},
		{"label": _("Fines (Logged)"), "fieldname": "fine_total", "fieldtype": "Currency", "width": 110},
		{"label": _("Safety Score"), "fieldname": "safety_score", "fieldtype": "Int", "width": 100},
		{"label": _("Rating"), "fieldname": "rating", "fieldtype": "Data", "width": 90},
	]


def get_data(filters):
	incident_cond, incident_values = _date_conditions("date", filters)
	accident_cond, accident_values = _date_conditions("date(date_of_accident)", filters)

	driver_filter_incident = ""
	driver_filter_accident = ""
	if filters.get("driver"):
		driver_filter_incident = " and driver = %(driver)s"
		driver_filter_accident = " and driver = %(driver)s"
		incident_values["driver"] = filters.get("driver")
		accident_values["driver"] = filters.get("driver")

	incident_drivers = frappe.db.sql(
		f"""
		select distinct driver from `tabDriver Safety Incident`
		where docstatus = 1 {incident_cond} {driver_filter_incident}
		""",
		incident_values,
		as_dict=True,
	)
	accident_drivers = frappe.db.sql(
		f"""
		select distinct driver from `tabAccident Report`
		where docstatus = 1 {accident_cond} {driver_filter_accident}
		""",
		accident_values,
		as_dict=True,
	)

	driver_names = {d.driver for d in incident_drivers if d.driver} | {
		d.driver for d in accident_drivers if d.driver
	}

	rows = []
	for driver in sorted(driver_names):
		driver_name = frappe.db.get_value("Employee", driver, "employee_name") or driver

		incident_cond2, incident_values2 = _date_conditions("date", filters)
		incident_values2["driver"] = driver
		incidents = frappe.db.sql(
			f"""
			select count(*), sum(points_deducted), sum(fine_amount)
			from `tabDriver Safety Incident`
			where docstatus = 1 and driver = %(driver)s {incident_cond2}
			""",
			incident_values2,
		)[0]
		incident_count = incidents[0] or 0
		incident_points = flt(incidents[1])
		fine_total = flt(incidents[2])

		acc_cond2, acc_values2 = _date_conditions("date(date_of_accident)", filters)
		acc_values2["driver"] = driver
		accidents = frappe.db.sql(
			f"""
			select severity, total_cost, at_fault
			from `tabAccident Report`
			where docstatus = 1 and driver = %(driver)s {acc_cond2}
			""",
			acc_values2,
			as_dict=True,
		)

		accident_count = len(accidents)
		at_fault_count = len([a for a in accidents if a.at_fault == "Driver"])
		accident_cost = sum(flt(a.total_cost) for a in accidents)
		accident_points = sum(ACCIDENT_PENALTY.get(a.severity, 0) for a in accidents)

		points_deducted = incident_points + accident_points
		safety_score = max(0, 100 - points_deducted)

		if safety_score >= 85:
			rating = "Good"
		elif safety_score >= 60:
			rating = "Watch"
		else:
			rating = "Poor"

		rows.append({
			"driver": driver,
			"driver_name": driver_name,
			"accident_count": accident_count,
			"at_fault_count": at_fault_count,
			"incident_count": incident_count,
			"points_deducted": points_deducted,
			"accident_cost": accident_cost,
			"fine_total": fine_total,
			"safety_score": safety_score,
			"rating": rating,
		})

	rows.sort(key=lambda r: r["safety_score"])
	return rows


def _date_conditions(field, filters):
	conditions = ""
	values = {}
	if filters.get("from_date"):
		conditions += f" and {field} >= %(from_date)s"
		values["from_date"] = filters.get("from_date")
	if filters.get("to_date"):
		conditions += f" and {field} <= %(to_date)s"
		values["to_date"] = filters.get("to_date")
	return conditions, values


def get_chart(data):
	if not data:
		return None
	return {
		"data": {
			"labels": [row["driver_name"] for row in data],
			"datasets": [
				{"name": "Safety Score", "values": [row["safety_score"] for row in data]},
			],
		},
		"type": "bar",
		"colors": ["#C0392B"],
	}
