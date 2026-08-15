# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Workshop Utilization shows, per Workshop: how many bays are occupied right
now versus its bay capacity, plus job throughput (opened/completed, average
turnaround in days, and total cost) for the selected date range. "Active
jobs now" and the active-status list are the same definition Workshop Job
Card's own bay-capacity validation uses, so this report can never disagree
with what actually blocks a new job from being opened.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate

from transport_logistics.transport_logistics.doctype.workshop.workshop import ACTIVE_JOB_STATUSES


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
		{"label": _("Workshop"), "fieldname": "workshop", "fieldtype": "Link", "options": "Workshop", "width": 150},
		{"label": _("Type"), "fieldname": "workshop_type", "fieldtype": "Data", "width": 130},
		{"label": _("Bays"), "fieldname": "bay_count", "fieldtype": "Int", "width": 70},
		{"label": _("Active Jobs Now"), "fieldname": "active_jobs", "fieldtype": "Int", "width": 110},
		{"label": _("Bay Utilization %"), "fieldname": "bay_utilization_percent", "fieldtype": "Percent", "width": 130},
		{"label": _("Jobs Opened"), "fieldname": "jobs_opened", "fieldtype": "Int", "width": 100},
		{"label": _("Jobs Completed"), "fieldname": "jobs_completed", "fieldtype": "Int", "width": 110},
		{"label": _("Avg Turnaround (Days)"), "fieldname": "avg_turnaround_days", "fieldtype": "Float", "width": 150},
		{"label": _("Total Cost (Completed)"), "fieldname": "total_cost", "fieldtype": "Currency", "width": 140},
	]


def get_data(filters):
	conditions = ""
	values = {}
	if filters.get("workshop"):
		conditions += " and name = %(workshop)s"
		values["workshop"] = filters.get("workshop")
	if filters.get("company"):
		conditions += " and company = %(company)s"
		values["company"] = filters.get("company")

	workshops = frappe.db.sql(
		f"""
		select name, workshop_type, bay_count
		from `tabWorkshop`
		where 1=1 {conditions}
		order by name
		""",
		values,
		as_dict=True,
	)

	from_date = getdate(filters.get("from_date"))
	to_date = getdate(filters.get("to_date"))

	rows = []
	for ws in workshops:
		active_jobs = frappe.db.count(
			"Workshop Job Card",
			{"workshop": ws.name, "status": ["in", ACTIVE_JOB_STATUSES], "docstatus": ["!=", 2]},
		)
		bay_utilization_percent = (active_jobs / ws.bay_count * 100) if ws.bay_count else 0

		jobs_opened = frappe.db.count(
			"Workshop Job Card",
			{"workshop": ws.name, "date_opened": ["between", [from_date, to_date]], "docstatus": ["!=", 2]},
		)

		completed = frappe.db.sql(
			"""
			select date_opened, date_closed, total_cost
			from `tabWorkshop Job Card`
			where workshop = %(workshop)s
			  and status = 'Completed'
			  and date_closed between %(from_date)s and %(to_date)s
			  and docstatus != 2
			""",
			{"workshop": ws.name, "from_date": from_date, "to_date": to_date},
			as_dict=True,
		)

		turnarounds = [
			(getdate(c.date_closed) - getdate(c.date_opened)).days
			for c in completed
			if c.date_opened and c.date_closed
		]
		avg_turnaround_days = (sum(turnarounds) / len(turnarounds)) if turnarounds else 0

		rows.append({
			"workshop": ws.name,
			"workshop_type": ws.workshop_type,
			"bay_count": ws.bay_count,
			"active_jobs": active_jobs,
			"bay_utilization_percent": bay_utilization_percent,
			"jobs_opened": jobs_opened,
			"jobs_completed": len(completed),
			"avg_turnaround_days": round(avg_turnaround_days, 1),
			"total_cost": sum(flt(c.total_cost) for c in completed),
		})

	return rows


def get_chart(data):
	if not data:
		return None
	return {
		"data": {
			"labels": [row["workshop"] for row in data],
			"datasets": [
				{"name": "Bay Utilization %", "values": [round(row["bay_utilization_percent"], 1) for row in data]},
			],
		},
		"type": "bar",
		"colors": ["#D35400"],
	}
