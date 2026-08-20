# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Per-driver utilization over a date range: how many trips they actually
drove, how much distance/revenue that represents, and what fraction of the
period they were actively out on a trip versus idle. "Active" is measured
by distinct trip dates with an Ongoing or Completed trip — Cancelled/Planned
trips don't count as utilization, since the driver wasn't actually out
driving on those.

Last Trip Date / Days Idle are computed across ALL of a driver's trips,
not just within the selected date range — so a driver who shows zero
activity in this period still shows how long they've actually been idle,
rather than that being indistinguishable from "just outside the filter".
"""

import frappe
from frappe import _
from frappe.utils import flt, cint, getdate, date_diff, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Link", "options": "Employee", "width": 100},
		{"label": _("Driver Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 150},
		{"label": _("Trips"), "fieldname": "trip_count", "fieldtype": "Int", "width": 70},
		{"label": _("Total Distance (Km)"), "fieldname": "total_distance_km", "fieldtype": "Float", "width": 130},
		{"label": _("Total Revenue"), "fieldname": "total_revenue", "fieldtype": "Currency", "width": 120},
		{"label": _("Active Days"), "fieldname": "active_days", "fieldtype": "Int", "width": 90},
		{"label": _("Period Days"), "fieldname": "period_days", "fieldtype": "Int", "width": 90},
		{"label": _("Utilization %"), "fieldname": "utilization_pct", "fieldtype": "Percent", "width": 100},
		{"label": _("Avg Km / Trip"), "fieldname": "avg_km_per_trip", "fieldtype": "Float", "width": 100},
		{"label": _("Avg Revenue / Trip"), "fieldname": "avg_revenue_per_trip", "fieldtype": "Currency", "width": 120},
		{"label": _("Last Trip Date"), "fieldname": "last_trip_date", "fieldtype": "Date", "width": 100},
		{"label": _("Days Idle"), "fieldname": "days_idle", "fieldtype": "Int", "width": 80},
	]


def get_data(filters):
	from_date = getdate(filters.get("from_date")) if filters.get("from_date") else getdate(today()).replace(day=1)
	to_date = getdate(filters.get("to_date")) if filters.get("to_date") else getdate(today())
	period_days = date_diff(to_date, from_date) + 1

	conditions = [
		"t.driver is not null",
		"t.trip_date between %(from_date)s and %(to_date)s",
		"t.status in ('Ongoing', 'Completed')",
	]
	values = {"from_date": from_date, "to_date": to_date}

	if filters.get("driver"):
		conditions.append("t.driver = %(driver)s")
		values["driver"] = filters.get("driver")
	if filters.get("company"):
		conditions.append("t.company = %(company)s")
		values["company"] = filters.get("company")

	where_clause = " and ".join(conditions)

	rows = frappe.db.sql(
		f"""
		select
			t.driver,
			e.employee_name,
			count(distinct t.name) as trip_count,
			coalesce(sum(t.distance_km), 0) as total_distance_km,
			coalesce(sum(t.revenue), 0) as total_revenue,
			count(distinct t.trip_date) as active_days
		from `tabTruck Trip` t
		left join `tabEmployee` e on e.name = t.driver
		where {where_clause}
		group by t.driver, e.employee_name
		order by trip_count desc
		""",
		values,
		as_dict=True,
	)

	today_date = getdate(today())
	data = []
	for r in rows:
		last_trip_date = frappe.db.get_value(
			"Truck Trip",
			{"driver": r.driver, "status": ["in", ["Ongoing", "Completed"]]},
			"trip_date",
			order_by="trip_date desc",
		)
		data.append({
			"driver": r.driver,
			"employee_name": r.employee_name,
			"trip_count": cint(r.trip_count),
			"total_distance_km": flt(r.total_distance_km),
			"total_revenue": flt(r.total_revenue),
			"active_days": cint(r.active_days),
			"period_days": period_days,
			"utilization_pct": (flt(r.active_days) / period_days * 100) if period_days else 0,
			"avg_km_per_trip": (flt(r.total_distance_km) / r.trip_count) if r.trip_count else 0,
			"avg_revenue_per_trip": (flt(r.total_revenue) / r.trip_count) if r.trip_count else 0,
			"last_trip_date": last_trip_date,
			"days_idle": date_diff(today_date, last_trip_date) if last_trip_date else None,
		})

	return data
