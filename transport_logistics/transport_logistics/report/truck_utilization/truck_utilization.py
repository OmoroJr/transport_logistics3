# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Truck Utilization measures, for each truck over a date range, how many days
it actually did something (a completed trip, or a gate-out for work) versus
sitting idle, and how many days were lost to declared maintenance downtime.

  Active Days      = distinct days with a Completed Truck Trip OR a
                      Departed Gate Pass in the period
  Downtime Days     = sum(downtime_hours) from Truck Maintenance Log in the
                      period, converted to days
  Idle Days         = Total Days - Active Days - Downtime Days (floored at 0)
  Utilization %     = Active Days / Total Days * 100

This is a simple, explainable definition deliberately chosen over a
precision time-in-motion metric, since Truck Trip currently records only a
trip date (not start/end times) — good enough to flag chronically idle
trucks without needing GPS/telematics data this app doesn't have.
"""

import frappe
from frappe import _
from frappe.utils import flt, date_diff, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw("Please set both From Date and To Date")

	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	return columns, data, None, chart


def get_columns():
	return [
		{"label": _("Truck"), "fieldname": "truck", "fieldtype": "Link", "options": "Truck", "width": 110},
		{"label": _("Registration No"), "fieldname": "registration_number", "fieldtype": "Data", "width": 120},
		{"label": _("Total Days"), "fieldname": "total_days", "fieldtype": "Int", "width": 90},
		{"label": _("Active Days"), "fieldname": "active_days", "fieldtype": "Int", "width": 100},
		{"label": _("Downtime Days"), "fieldname": "downtime_days", "fieldtype": "Float", "width": 110, "precision": 1},
		{"label": _("Idle Days"), "fieldname": "idle_days", "fieldtype": "Float", "width": 90, "precision": 1},
		{"label": _("Utilization %"), "fieldname": "utilization_percent", "fieldtype": "Percent", "width": 110},
		{"label": _("Distance Run (Km)"), "fieldname": "distance_km", "fieldtype": "Float", "width": 130},
		{"label": _("Avg Km / Active Day"), "fieldname": "avg_km_per_active_day", "fieldtype": "Float", "width": 140, "precision": 1},
		{"label": _("Current Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
	]


def get_data(filters):
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	total_days = date_diff(to_date, from_date) + 1

	conditions = ""
	values = {}
	if filters.get("truck"):
		conditions += " and name = %(truck)s"
		values["truck"] = filters.get("truck")
	if filters.get("company"):
		conditions += " and company = %(company)s"
		values["company"] = filters.get("company")

	trucks = frappe.db.sql(
		f"""
		select name, registration_number, status
		from `tabTruck`
		where 1=1 {conditions}
		order by name
		""",
		values,
		as_dict=True,
	)

	rows = []
	for truck in trucks:
		active_days = get_active_days(truck.name, from_date, to_date)
		downtime_hours = get_downtime_hours(truck.name, from_date, to_date)
		downtime_days = downtime_hours / 24
		idle_days = max(0, total_days - active_days - downtime_days)
		utilization_percent = (active_days / total_days * 100) if total_days else 0
		distance_km = get_trip_distance(truck.name, from_date, to_date)
		avg_km_per_active_day = (distance_km / active_days) if active_days else 0

		rows.append({
			"truck": truck.name,
			"registration_number": truck.registration_number,
			"total_days": total_days,
			"active_days": active_days,
			"downtime_days": downtime_days,
			"idle_days": idle_days,
			"utilization_percent": utilization_percent,
			"distance_km": distance_km,
			"avg_km_per_active_day": avg_km_per_active_day,
			"status": truck.status,
		})

	return rows


def get_active_days(truck, from_date, to_date):
	result = frappe.db.sql(
		"""
		select count(distinct d) from (
			select date(trip_date) as d
			from `tabTruck Trip`
			where truck = %(truck)s and status = 'Completed'
			and trip_date between %(from_date)s and %(to_date)s

			union

			select date(gate_in_time) as d
			from `tabGate Pass`
			where truck = %(truck)s and status = 'Departed' and pass_type = 'Vehicle'
			and date(gate_in_time) between %(from_date)s and %(to_date)s
		) days
		""",
		{"truck": truck, "from_date": from_date, "to_date": to_date},
	)
	return result[0][0] if result and result[0][0] else 0


def get_downtime_hours(truck, from_date, to_date):
	result = frappe.db.sql(
		"""
		select sum(downtime_hours)
		from `tabTruck Maintenance Log`
		where truck = %(truck)s and docstatus = 1
		and date between %(from_date)s and %(to_date)s
		""",
		{"truck": truck, "from_date": from_date, "to_date": to_date},
	)
	return flt(result[0][0]) if result and result[0][0] else 0


def get_trip_distance(truck, from_date, to_date):
	result = frappe.db.sql(
		"""
		select sum(distance_km)
		from `tabTruck Trip`
		where truck = %(truck)s and status = 'Completed'
		and trip_date between %(from_date)s and %(to_date)s
		""",
		{"truck": truck, "from_date": from_date, "to_date": to_date},
	)
	return flt(result[0][0]) if result and result[0][0] else 0


def get_chart(data):
	if not data:
		return None
	return {
		"data": {
			"labels": [row["truck"] for row in data],
			"datasets": [
				{"name": "Utilization %", "values": [flt(row["utilization_percent"], 1) for row in data]},
			],
		},
		"type": "bar",
		"colors": ["#27AE60"],
	}
