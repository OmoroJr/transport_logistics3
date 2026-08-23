# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
For each truck, looks at its MOST RECENT submitted Truck Maintenance Log
and checks whether that service's own next_service_due_km / next_service_due_date
has been reached — by the truck's current odometer and today's date
respectively. Either threshold being crossed marks the truck Due/Overdue;
a truck with no maintenance history at all, or whose last service didn't
set either due field, shows as "Not Scheduled" rather than being silently
omitted, since an untracked truck is exactly the kind of gap this report
exists to surface.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, today, date_diff


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Truck"), "fieldname": "truck", "fieldtype": "Link", "options": "Truck", "width": 100},
		{"label": _("Registration No"), "fieldname": "registration_number", "fieldtype": "Data", "width": 110},
		{"label": _("Current Odometer (Km)"), "fieldname": "current_odometer", "fieldtype": "Float", "width": 130},
		{"label": _("Last Service Date"), "fieldname": "last_service_date", "fieldtype": "Date", "width": 110},
		{"label": _("Last Service Type"), "fieldname": "last_maintenance_type", "fieldtype": "Data", "width": 120},
		{"label": _("Next Service Due (Km)"), "fieldname": "next_service_due_km", "fieldtype": "Float", "width": 130},
		{"label": _("Km Over/Under Due"), "fieldname": "km_over_due", "fieldtype": "Float", "width": 120},
		{"label": _("Next Service Due (Date)"), "fieldname": "next_service_due_date", "fieldtype": "Date", "width": 130},
		{"label": _("Days Over/Under Due"), "fieldname": "days_over_due", "fieldtype": "Int", "width": 120},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
	]


def get_data(filters):
	conditions = ["t.status != 'Disposed'"]
	values = {}
	if filters.get("truck"):
		conditions.append("t.name = %(truck)s")
		values["truck"] = filters.get("truck")
	if filters.get("company"):
		conditions.append("t.company = %(company)s")
		values["company"] = filters.get("company")

	where_clause = " and ".join(conditions)

	trucks = frappe.db.sql(
		f"""
		select t.name as truck, t.registration_number, t.current_odometer
		from `tabTruck` t
		where {where_clause}
		""",
		values,
		as_dict=True,
	)

	today_date = getdate(today())
	rows = []

	for t in trucks:
		last = frappe.db.get_value(
			"Truck Maintenance Log",
			{"truck": t.truck, "docstatus": 1},
			["date", "maintenance_type", "next_service_due_km", "next_service_due_date"],
			as_dict=True,
			order_by="date desc, creation desc",
		)

		if not last:
			status = "Not Scheduled"
		else:
			overdue_by_km = bool(last.next_service_due_km and flt(t.current_odometer) >= flt(last.next_service_due_km))
			overdue_by_date = bool(last.next_service_due_date and today_date >= getdate(last.next_service_due_date))
			due_soon_km = bool(
				last.next_service_due_km
				and not overdue_by_km
				and flt(last.next_service_due_km) - flt(t.current_odometer) <= 1000
			)
			due_soon_date = bool(
				last.next_service_due_date
				and not overdue_by_date
				and date_diff(last.next_service_due_date, today_date) <= 14
			)

			if not last.next_service_due_km and not last.next_service_due_date:
				status = "Not Scheduled"
			elif overdue_by_km or overdue_by_date:
				status = "Overdue"
			elif due_soon_km or due_soon_date:
				status = "Due Soon"
			else:
				status = "OK"

		if filters.get("status") and status != filters.get("status"):
			continue

		rows.append({
			"truck": t.truck,
			"registration_number": t.registration_number,
			"current_odometer": flt(t.current_odometer),
			"last_service_date": last.date if last else None,
			"last_maintenance_type": last.maintenance_type if last else None,
			"next_service_due_km": last.next_service_due_km if last else None,
			"km_over_due": (
				flt(t.current_odometer) - flt(last.next_service_due_km)
				if last and last.next_service_due_km else None
			),
			"next_service_due_date": last.next_service_due_date if last else None,
			"days_over_due": (
				date_diff(today_date, last.next_service_due_date)
				if last and last.next_service_due_date else None
			),
			"status": status,
		})

	# Surface the most urgent trucks first.
	status_order = {"Overdue": 0, "Due Soon": 1, "OK": 2, "Not Scheduled": 3}
	rows.sort(key=lambda r: status_order.get(r["status"], 9))

	return rows
