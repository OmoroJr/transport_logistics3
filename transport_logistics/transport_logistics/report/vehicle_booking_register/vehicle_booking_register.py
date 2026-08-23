# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
One row per Truck Trip, consolidating what a paper/spreadsheet "Vehicle
Booking Register" usually tracks across trip, fuel, and driver-allowance
data — joining Truck Trip with its "For Trip" Truck Fuel Log(s) and its
Route's per-trip driver rate.

Built against an uploaded reference spreadsheet with this exact name. That
sheet tracked several things this app does not currently capture at all:
Turnboy (loading assistant), Loader Team, fuel-tank carryover between
trips (B/f Fuel, Fuel Adjustment, Fuel Diff C/F), and a fuel gauge/dipstick
reading distinct from litres purchased. Rather than silently drop those
columns or invent placeholder data, they're omitted here and named
explicitly below — if any of them matter going forward, they'd need new
fields on Truck Trip / Truck Fuel Log, not just a new report.

"Driver Allowance" uses Route.driver_rate (the same per-trip rate Trip
Profitability and Route Profitability already use) rather than trying to
back-compute a per-trip figure out of Driver Mileage Payment, since that
doctype pays out per PERIOD per ROUTE (via its Driver Mileage Payment
Route child table), not per individual trip — there is no reliable way to
split a period total back down to one trip's share.
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
		{"label": _("Trip"), "fieldname": "name", "fieldtype": "Link", "options": "Truck Trip", "width": 110},
		{"label": _("Date"), "fieldname": "trip_date", "fieldtype": "Date", "width": 95},
		{"label": _("Vehicle"), "fieldname": "truck", "fieldtype": "Link", "options": "Truck", "width": 100},
		{"label": _("Driver"), "fieldname": "driver_name", "fieldtype": "Data", "width": 140},
		{"label": _("Route"), "fieldname": "route", "fieldtype": "Link", "options": "Route", "width": 100},
		{"label": _("Route Km (Ref)"), "fieldname": "route_distance_km", "fieldtype": "Float", "width": 110},
		{"label": _("Origin"), "fieldname": "origin", "fieldtype": "Data", "width": 100},
		{"label": _("Destination"), "fieldname": "destination", "fieldtype": "Data", "width": 100},
		{"label": _("Start Odometer"), "fieldname": "start_odometer", "fieldtype": "Float", "width": 110},
		{"label": _("End Odometer"), "fieldname": "end_odometer", "fieldtype": "Float", "width": 110},
		{"label": _("Trip Km Travelled"), "fieldname": "distance_km", "fieldtype": "Float", "width": 120},
		{"label": _("Standard Fuel (L)"), "fieldname": "standard_fuel_litres", "fieldtype": "Float", "width": 110},
		{"label": _("Fuel Purchased (L)"), "fieldname": "fuel_qty_litres", "fieldtype": "Float", "width": 110},
		{"label": _("Extra Fuel (L)"), "fieldname": "extra_fuel_litres", "fieldtype": "Float", "width": 100},
		{"label": _("Extra Fuel Reason"), "fieldname": "extra_fuel_reason", "fieldtype": "Data", "width": 160},
		{"label": _("Fuel Level Before (L)"), "fieldname": "fuel_level_before_refuel", "fieldtype": "Float", "width": 110},
		{"label": _("Actual Km/L"), "fieldname": "actual_km_per_litre", "fieldtype": "Float", "width": 90},
		{"label": _("Driver Allowance (Rate)"), "fieldname": "driver_allowance_rate", "fieldtype": "Currency", "width": 140},
		{"label": _("Entry By"), "fieldname": "owner", "fieldtype": "Data", "width": 120},
		{"label": _("Authorized By"), "fieldname": "authorized_by", "fieldtype": "Data", "width": 120},
		{"label": _("End Trip Date"), "fieldname": "offload_datetime", "fieldtype": "Datetime", "width": 140},
		{"label": _("Delivery Number"), "fieldname": "delivery_number", "fieldtype": "Data", "width": 120},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
	]


def get_data(filters):
	conditions = ["1=1"]
	values = {}

	if filters.get("from_date"):
		conditions.append("t.trip_date >= %(from_date)s")
		values["from_date"] = filters.get("from_date")
	if filters.get("to_date"):
		conditions.append("t.trip_date <= %(to_date)s")
		values["to_date"] = filters.get("to_date")
	if filters.get("truck"):
		conditions.append("t.truck = %(truck)s")
		values["truck"] = filters.get("truck")
	if filters.get("driver"):
		conditions.append("t.driver = %(driver)s")
		values["driver"] = filters.get("driver")
	if filters.get("route"):
		conditions.append("t.route = %(route)s")
		values["route"] = filters.get("route")
	if filters.get("company"):
		conditions.append("t.company = %(company)s")
		values["company"] = filters.get("company")

	where_clause = " and ".join(conditions)

	trips = frappe.db.sql(
		f"""
		select
			t.name, t.trip_date, t.truck, t.driver, t.route, t.origin, t.destination,
			t.start_odometer, t.end_odometer, t.distance_km, t.owner, t.status,
			t.offload_datetime, t.delivery_number,
			e.employee_name as driver_name,
			r.distance_km as route_distance_km, r.driver_rate as driver_allowance_rate
		from `tabTruck Trip` t
		left join `tabEmployee` e on e.name = t.driver
		left join `tabRoute` r on r.name = t.route
		where {where_clause}
		order by t.trip_date desc, t.name desc
		""",
		values,
		as_dict=True,
	)

	data = []
	for t in trips:
		fuel = frappe.db.sql(
			"""
			select
				coalesce(sum(fuel_qty_litres), 0) as fuel_qty_litres,
				coalesce(sum(standard_fuel_litres), 0) as standard_fuel_litres,
				coalesce(sum(extra_fuel_litres), 0) as extra_fuel_litres,
				group_concat(distinct extra_fuel_reason separator '; ') as extra_fuel_reason,
				max(fuel_level_before_refuel) as fuel_level_before_refuel
			from `tabTruck Fuel Log`
			where docstatus = 1 and reason_for_fuelling = 'For Trip' and truck_trip = %s
			""",
			(t.name,),
			as_dict=True,
		)[0]

		authorized_by = frappe.db.get_value(
			"Authority to Load", {"truck_trip": t.name, "docstatus": 1}, "issued_by"
		)

		row = dict(t)
		row["fuel_qty_litres"] = flt(fuel.fuel_qty_litres)
		row["standard_fuel_litres"] = flt(fuel.standard_fuel_litres)
		row["extra_fuel_litres"] = flt(fuel.extra_fuel_litres)
		row["extra_fuel_reason"] = fuel.extra_fuel_reason
		row["fuel_level_before_refuel"] = flt(fuel.fuel_level_before_refuel)
		row["actual_km_per_litre"] = (
			flt(t.distance_km) / fuel.fuel_qty_litres if fuel.fuel_qty_litres else 0
		)
		row["authorized_by"] = authorized_by

		data.append(row)

	return data
