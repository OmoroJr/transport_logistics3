# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Shows, for every truck, whether it's currently Loaded (en route to or
waiting at a client, on an Ongoing Truck Trip that hasn't been offloaded
yet) or Empty (available for a new trip) — deliberately derived live from
Truck Trip rather than a stored field on Truck, so it can never drift out
of sync with the actual trip data driving truck_trip.py's own availability
validation.
"""

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Truck"), "fieldname": "truck", "fieldtype": "Link", "options": "Truck", "width": 110},
		{"label": _("Registration No"), "fieldname": "registration_number", "fieldtype": "Data", "width": 120},
		{"label": _("Fleet Status"), "fieldname": "fleet_status", "fieldtype": "Data", "width": 110},
		{"label": _("Load Status"), "fieldname": "load_status", "fieldtype": "Data", "width": 140},
		{"label": _("Current Trip"), "fieldname": "current_trip", "fieldtype": "Link", "options": "Truck Trip", "width": 110},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 120},
		{"label": _("Destination"), "fieldname": "destination", "fieldtype": "Data", "width": 130},
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Link", "options": "Employee", "width": 110},
		{"label": _("Trailer"), "fieldname": "trailer", "fieldtype": "Link", "options": "Trailer", "width": 100},
	]


def get_data(filters):
	conditions = ""
	values = {}
	if filters.get("truck"):
		conditions += " and t.name = %(truck)s"
		values["truck"] = filters.get("truck")
	if filters.get("company"):
		conditions += " and t.company = %(company)s"
		values["company"] = filters.get("company")

	trucks = frappe.db.sql(
		f"""
		select t.name, t.registration_number, t.status, t.assigned_driver, t.current_trailer
		from `tabTruck` t
		where 1=1 {conditions}
		order by t.name
		""",
		values,
		as_dict=True,
	)

	load_filter = filters.get("load_status")

	rows = []
	for truck in trucks:
		active_trip = frappe.db.get_value(
			"Truck Trip",
			{"truck": truck.name, "status": "Ongoing", "offload_status": "Not Offloaded"},
			["name", "customer", "destination"],
			as_dict=True,
		)

		if active_trip:
			load_status = "Loaded — En Route to Client"
			current_trip = active_trip.name
			customer = active_trip.customer
			destination = active_trip.destination
		else:
			load_status = "Empty — Available"
			current_trip = None
			customer = None
			destination = None

		if load_filter == "Loaded" and not active_trip:
			continue
		if load_filter == "Empty" and active_trip:
			continue

		rows.append({
			"truck": truck.name,
			"registration_number": truck.registration_number,
			"fleet_status": truck.status,
			"load_status": load_status,
			"current_trip": current_trip,
			"customer": customer,
			"destination": destination,
			"driver": truck.assigned_driver,
			"trailer": truck.current_trailer,
		})

	return rows
