# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Trailer Utilization reconstructs coupled/decoupled intervals from Trailer
Coupling Log history and measures how many days of the selected period each
trailer actually spent coupled to a truck (i.e. in service) versus sitting
in the yard uncoupled.
"""

import frappe
from frappe import _
from frappe.utils import date_diff, getdate


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
		{"label": _("Trailer"), "fieldname": "trailer", "fieldtype": "Link", "options": "Trailer", "width": 110},
		{"label": _("Type"), "fieldname": "trailer_type", "fieldtype": "Data", "width": 100},
		{"label": _("Registration No"), "fieldname": "registration_number", "fieldtype": "Data", "width": 120},
		{"label": _("Total Days"), "fieldname": "total_days", "fieldtype": "Int", "width": 90},
		{"label": _("Coupled Days"), "fieldname": "coupled_days", "fieldtype": "Int", "width": 100},
		{"label": _("Uncoupled Days"), "fieldname": "uncoupled_days", "fieldtype": "Int", "width": 110},
		{"label": _("Utilization %"), "fieldname": "utilization_percent", "fieldtype": "Percent", "width": 110},
		{"label": _("Current Truck"), "fieldname": "current_truck", "fieldtype": "Link", "options": "Truck", "width": 110},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
	]


def get_data(filters):
	from_date = getdate(filters.get("from_date"))
	to_date = getdate(filters.get("to_date"))
	total_days = date_diff(to_date, from_date) + 1

	conditions = ""
	values = {}
	if filters.get("trailer"):
		conditions += " and name = %(trailer)s"
		values["trailer"] = filters.get("trailer")
	if filters.get("trailer_type"):
		conditions += " and trailer_type = %(trailer_type)s"
		values["trailer_type"] = filters.get("trailer_type")
	if filters.get("company"):
		conditions += " and company = %(company)s"
		values["company"] = filters.get("company")

	trailers = frappe.db.sql(
		f"""
		select name, trailer_type, registration_number, current_truck, status
		from `tabTrailer`
		where 1=1 {conditions}
		order by name
		""",
		values,
		as_dict=True,
	)

	rows = []
	for trailer in trailers:
		coupled_days = get_coupled_days(trailer.name, from_date, to_date)
		coupled_days = min(coupled_days, total_days)
		uncoupled_days = total_days - coupled_days
		utilization_percent = (coupled_days / total_days * 100) if total_days else 0

		rows.append({
			"trailer": trailer.name,
			"trailer_type": trailer.trailer_type,
			"registration_number": trailer.registration_number,
			"total_days": total_days,
			"coupled_days": coupled_days,
			"uncoupled_days": uncoupled_days,
			"utilization_percent": utilization_percent,
			"current_truck": trailer.current_truck,
			"status": trailer.status,
		})

	return rows


def get_coupled_days(trailer, from_date, to_date):
	"""Reconstructs Coupled -> Decoupled intervals in chronological order and
	sums the portion of each interval that overlaps the report's date window.
	An unmatched trailing 'Coupled' (still coupled today) extends to to_date."""
	logs = frappe.db.sql(
		"""
		select date, action from `tabTrailer Coupling Log`
		where trailer = %(trailer)s and docstatus = 1
		order by date asc, creation asc
		""",
		{"trailer": trailer},
		as_dict=True,
	)

	coupled_days = 0
	open_start = None

	for log in logs:
		log_date = getdate(log.date)
		if log.action == "Coupled" and open_start is None:
			open_start = log_date
		elif log.action == "Decoupled" and open_start is not None:
			coupled_days += _overlap_days(open_start, log_date, from_date, to_date)
			open_start = None

	if open_start is not None:
		coupled_days += _overlap_days(open_start, to_date, from_date, to_date)

	return coupled_days


def _overlap_days(interval_start, interval_end, window_start, window_end):
	start = max(interval_start, window_start)
	end = min(interval_end, window_end)
	return max(0, date_diff(end, start) + 1)


def get_chart(data):
	if not data:
		return None
	return {
		"data": {
			"labels": [row["trailer"] for row in data],
			"datasets": [
				{"name": "Utilization %", "values": [round(row["utilization_percent"], 1) for row in data]},
			],
		},
		"type": "bar",
		"colors": ["#8E44AD"],
	}
