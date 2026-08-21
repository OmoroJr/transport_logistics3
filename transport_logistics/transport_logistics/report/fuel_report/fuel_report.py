# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	summary = get_summary(data)
	return columns, data, None, chart, summary


def get_columns():
	return [
		{"label": _("Fuel Log"), "fieldname": "name", "fieldtype": "Link", "options": "Truck Fuel Log", "width": 130},
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 95},
		{"label": _("Truck"), "fieldname": "truck", "fieldtype": "Link", "options": "Truck", "width": 100},
		{"label": _("Registration No"), "fieldname": "registration_number", "fieldtype": "Data", "width": 110},
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Link", "options": "Employee", "width": 100},
		{"label": _("Driver Name"), "fieldname": "driver_name", "fieldtype": "Data", "width": 120},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 120},
		{"label": _("Reason"), "fieldname": "reason_for_fuelling", "fieldtype": "Data", "width": 100},
		{"label": _("Source"), "fieldname": "source", "fieldtype": "Data", "width": 130},
		{"label": _("Truck Trip"), "fieldname": "truck_trip", "fieldtype": "Link", "options": "Truck Trip", "width": 110},
		{"label": _("Route"), "fieldname": "route", "fieldtype": "Link", "options": "Route", "width": 100},
		{"label": _("Route Name"), "fieldname": "route_name", "fieldtype": "Data", "width": 120},
		{"label": _("Origin"), "fieldname": "origin", "fieldtype": "Data", "width": 100},
		{"label": _("Destination"), "fieldname": "destination", "fieldtype": "Data", "width": 100},
		{"label": _("Fuel Station"), "fieldname": "fuel_station", "fieldtype": "Data", "width": 110},
		{"label": _("Full Tank"), "fieldname": "full_tank", "fieldtype": "Check", "width": 80},
		{"label": _("Odometer (Km)"), "fieldname": "odometer_reading", "fieldtype": "Float", "width": 100},
		{"label": _("Distance Covered (Km)"), "fieldname": "distance_covered", "fieldtype": "Float", "width": 130},
		{"label": _("Fuel Qty (L)"), "fieldname": "fuel_qty_litres", "fieldtype": "Float", "width": 100},
		{"label": _("Rate/Litre"), "fieldname": "rate_per_litre", "fieldtype": "Currency", "width": 100},
		{"label": _("Total Amount"), "fieldname": "total_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Efficiency (Km/L)"), "fieldname": "fuel_efficiency_km_per_litre", "fieldtype": "Float", "width": 120, "precision": 2},
		{"label": _("Route Standard (L)"), "fieldname": "standard_fuel_litres", "fieldtype": "Float", "width": 120},
		{"label": _("Extra Fuel (L)"), "fieldname": "extra_fuel_litres", "fieldtype": "Float", "width": 100},
		{"label": _("Extra Fuel %"), "fieldname": "extra_fuel_percent", "fieldtype": "Percent", "width": 100},
		{"label": _("Reason for Extra Fuel"), "fieldname": "extra_fuel_reason", "fieldtype": "Data", "width": 200},
		{"label": _("Status"), "fieldname": "docstatus_label", "fieldtype": "Data", "width": 90},
	]


def get_data(filters):
	conditions, values = get_conditions(filters)

	rows = frappe.db.sql(
		f"""
		select
			tfl.name, tfl.date, tfl.truck, t.registration_number,
			tfl.driver, emp.employee_name as driver_name,
			tfl.company, tfl.reason_for_fuelling, tfl.source,
			tfl.truck_trip, tt.route, r.route_name, r.origin, r.destination,
			tfl.fuel_station, tfl.full_tank,
			tfl.odometer_reading, tfl.distance_covered,
			tfl.fuel_qty_litres, tfl.rate_per_litre, tfl.total_amount,
			tfl.fuel_efficiency_km_per_litre,
			tfl.standard_fuel_litres, tfl.extra_fuel_litres, tfl.extra_fuel_reason,
			tfl.docstatus
		from `tabTruck Fuel Log` tfl
		left join `tabTruck` t on t.name = tfl.truck
		left join `tabEmployee` emp on emp.name = tfl.driver
		left join `tabTruck Trip` tt on tt.name = tfl.truck_trip
		left join `tabRoute` r on r.name = tt.route
		where 1=1 {conditions}
		order by tfl.date desc, tfl.name desc
		""",
		values,
		as_dict=True,
	)

	docstatus_label = {0: _("Draft"), 1: _("Submitted"), 2: _("Cancelled")}
	for row in rows:
		row["extra_fuel_percent"] = (
			(flt(row.extra_fuel_litres) / flt(row.standard_fuel_litres) * 100)
			if row.standard_fuel_litres else 0
		)
		row["docstatus_label"] = docstatus_label.get(row.docstatus)

	return rows


def get_conditions(filters):
	conditions = ""
	values = {}

	if not filters.get("include_unsubmitted"):
		conditions += " and tfl.docstatus = 1"

	if filters.get("from_date"):
		conditions += " and tfl.date >= %(from_date)s"
		values["from_date"] = filters.get("from_date")
	if filters.get("to_date"):
		conditions += " and tfl.date <= %(to_date)s"
		values["to_date"] = filters.get("to_date")
	if filters.get("company"):
		conditions += " and tfl.company = %(company)s"
		values["company"] = filters.get("company")
	if filters.get("truck"):
		conditions += " and tfl.truck = %(truck)s"
		values["truck"] = filters.get("truck")
	if filters.get("driver"):
		conditions += " and tfl.driver = %(driver)s"
		values["driver"] = filters.get("driver")
	if filters.get("reason_for_fuelling"):
		conditions += " and tfl.reason_for_fuelling = %(reason_for_fuelling)s"
		values["reason_for_fuelling"] = filters.get("reason_for_fuelling")
	if filters.get("source"):
		conditions += " and tfl.source = %(source)s"
		values["source"] = filters.get("source")
	if filters.get("route"):
		conditions += " and tt.route = %(route)s"
		values["route"] = filters.get("route")
	if filters.get("only_extra_fuel"):
		conditions += " and tfl.extra_fuel_litres > 0"

	return conditions, values


def get_chart(data):
	if not data:
		return None

	truck_totals = {}
	for row in data:
		truck_totals[row.truck] = truck_totals.get(row.truck, 0) + flt(row.fuel_qty_litres)

	# Keep the chart readable — top 15 trucks by fuel consumed.
	top_trucks = sorted(truck_totals.items(), key=lambda x: x[1], reverse=True)[:15]

	return {
		"data": {
			"labels": [t[0] for t in top_trucks],
			"datasets": [
				{"name": "Fuel Qty (L)", "values": [flt(t[1], 1) for t in top_trucks]},
			],
		},
		"type": "bar",
		"colors": ["#2E86C1"],
	}


def get_summary(data):
	if not data:
		return []

	total_qty = sum(flt(r.fuel_qty_litres) for r in data)
	total_amount = sum(flt(r.total_amount) for r in data)
	total_distance = sum(flt(r.distance_covered) for r in data)
	extra_rows = [r for r in data if flt(r.extra_fuel_litres) > 0]
	total_extra_litres = sum(flt(r.extra_fuel_litres) for r in extra_rows)
	unexplained = [r for r in extra_rows if not r.extra_fuel_reason]
	avg_efficiency = (total_distance / total_qty) if total_qty else 0

	return [
		{"label": _("Total Fuel Logs"), "value": len(data), "datatype": "Int"},
		{"label": _("Total Fuel (L)"), "value": flt(total_qty, 1), "datatype": "Float"},
		{"label": _("Total Fuel Cost"), "value": flt(total_amount, 2), "datatype": "Currency"},
		{"label": _("Avg Efficiency (Km/L)"), "value": flt(avg_efficiency, 2), "datatype": "Float"},
		{"label": _("Logs Over Route Standard"), "value": len(extra_rows), "datatype": "Int"},
		{"label": _("Total Extra Fuel (L)"), "value": flt(total_extra_litres, 1), "datatype": "Float"},
		{
			"label": _("Extra Fuel Logs Missing a Reason"),
			"value": len(unexplained),
			"datatype": "Int",
			"indicator": "Red" if unexplained else "Green",
		},
	]
