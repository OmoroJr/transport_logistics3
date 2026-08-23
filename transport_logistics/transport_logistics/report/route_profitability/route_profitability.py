# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Per-route profitability over a date range: trips, distance, fuel cost,
driver cost, revenue, and the profit that leaves — plus profit per Km and
per trip, so routes can be compared on a level footing regardless of
length or trip volume.

Two costs are deliberately included, one deliberately isn't:
  - Fuel cost: summed from submitted Truck Fuel Logs where the fuelling
    was "For Trip" and that trip's route matches. Only trip-purpose fuel
    counts — a log for "Yard Top-up" or similar isn't this route's cost.
  - Driver cost: trips x Route.driver_rate (the same per-trip rate
    Driver Mileage Payment already uses), not the driver's full salary —
    consistent with how driver pay is modelled elsewhere in this app.
  - Toll, parking, fines, and other Truck Expense entries are NOT
    included: those are recorded against a Truck and a date, not against
    a specific trip or route, so there's no reliable way to attribute them
    to one route without guessing. Leaving them out is more honest than a
    fabricated allocation.

Because of that last point, "Total Cost" here is a partial cost (fuel +
driver), not the full landed cost of running the route — treat Profit
accordingly as "contribution after fuel and driver pay", not a complete P&L.
"""

import frappe
from frappe import _
from frappe.utils import flt, cint, getdate, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	summary = get_summary(data)
	return columns, data, None, chart, summary


def get_columns():
	return [
		{"label": _("Route"), "fieldname": "route", "fieldtype": "Link", "options": "Route", "width": 100},
		{"label": _("Route Name"), "fieldname": "route_name", "fieldtype": "Data", "width": 130},
		{"label": _("Origin"), "fieldname": "origin", "fieldtype": "Data", "width": 100},
		{"label": _("Destination"), "fieldname": "destination", "fieldtype": "Data", "width": 100},
		{"label": _("Trips"), "fieldname": "trip_count", "fieldtype": "Int", "width": 70},
		{"label": _("Total Distance (Km)"), "fieldname": "total_distance_km", "fieldtype": "Float", "width": 130},
		{"label": _("Fuel Cost"), "fieldname": "fuel_cost", "fieldtype": "Currency", "width": 110},
		{"label": _("Driver Cost"), "fieldname": "driver_cost", "fieldtype": "Currency", "width": 110},
		{"label": _("Total Cost (Fuel + Driver)"), "fieldname": "total_cost", "fieldtype": "Currency", "width": 150},
		{"label": _("Revenue"), "fieldname": "revenue", "fieldtype": "Currency", "width": 110},
		{"label": _("Profit"), "fieldname": "profit", "fieldtype": "Currency", "width": 110},
		{"label": _("Profit / Trip"), "fieldname": "profit_per_trip", "fieldtype": "Currency", "width": 100},
		{"label": _("Profit / Km"), "fieldname": "profit_per_km", "fieldtype": "Currency", "width": 100},
	]


def get_data(filters):
	from_date = getdate(filters.get("from_date")) if filters.get("from_date") else getdate(today()).replace(day=1)
	to_date = getdate(filters.get("to_date")) if filters.get("to_date") else getdate(today())

	conditions = [
		"t.route is not null",
		"t.trip_date between %(from_date)s and %(to_date)s",
		"t.status = 'Completed'",
	]
	values = {"from_date": from_date, "to_date": to_date}

	if filters.get("route"):
		conditions.append("t.route = %(route)s")
		values["route"] = filters.get("route")
	if filters.get("company"):
		conditions.append("t.company = %(company)s")
		values["company"] = filters.get("company")

	where_clause = " and ".join(conditions)

	trip_rows = frappe.db.sql(
		f"""
		select
			t.route,
			r.route_name, r.origin, r.destination, r.driver_rate,
			count(distinct t.name) as trip_count,
			coalesce(sum(t.distance_km), 0) as total_distance_km,
			coalesce(sum(t.revenue), 0) as revenue
		from `tabTruck Trip` t
		left join `tabRoute` r on r.name = t.route
		where {where_clause}
		group by t.route, r.route_name, r.origin, r.destination, r.driver_rate
		order by revenue desc
		""",
		values,
		as_dict=True,
	)

	data = []
	for r in trip_rows:
		fuel_cost = flt(frappe.db.sql(
			"""
			select coalesce(sum(tfl.total_amount), 0)
			from `tabTruck Fuel Log` tfl
			inner join `tabTruck Trip` tt on tt.name = tfl.truck_trip
			where tfl.docstatus = 1
			and tfl.reason_for_fuelling = 'For Trip'
			and tt.route = %s
			and tt.trip_date between %s and %s
			and tt.status = 'Completed'
			""",
			(r.route, values["from_date"], values["to_date"]),
		)[0][0])

		driver_cost = flt(r.driver_rate) * cint(r.trip_count)
		total_cost = fuel_cost + driver_cost
		profit = flt(r.revenue) - total_cost

		data.append({
			"route": r.route,
			"route_name": r.route_name,
			"origin": r.origin,
			"destination": r.destination,
			"trip_count": cint(r.trip_count),
			"total_distance_km": flt(r.total_distance_km),
			"fuel_cost": fuel_cost,
			"driver_cost": driver_cost,
			"total_cost": total_cost,
			"revenue": flt(r.revenue),
			"profit": profit,
			"profit_per_trip": (profit / r.trip_count) if r.trip_count else 0,
			"profit_per_km": (profit / r.total_distance_km) if r.total_distance_km else 0,
		})

	return data


def get_chart(data):
	if not data:
		return None

	top = sorted(data, key=lambda r: r["profit"], reverse=True)[:15]
	return {
		"data": {
			"labels": [r["route_name"] or r["route"] for r in top],
			"datasets": [{"name": _("Profit"), "values": [flt(r["profit"], 2) for r in top]}],
		},
		"type": "bar",
		"colors": ["#2E8B57"],
	}


def get_summary(data):
	if not data:
		return []

	total_trips = sum(r["trip_count"] for r in data)
	total_distance = sum(r["total_distance_km"] for r in data)
	total_revenue = sum(r["revenue"] for r in data)
	total_cost = sum(r["total_cost"] for r in data)
	total_profit = sum(r["profit"] for r in data)

	return [
		{"label": _("Routes"), "value": len(data), "datatype": "Int"},
		{"label": _("Total Trips"), "value": total_trips, "datatype": "Int"},
		{"label": _("Total Distance (Km)"), "value": flt(total_distance, 1), "datatype": "Float"},
		{"label": _("Total Revenue"), "value": flt(total_revenue, 2), "datatype": "Currency"},
		{"label": _("Total Cost (Fuel + Driver)"), "value": flt(total_cost, 2), "datatype": "Currency"},
		{"label": _("Total Profit"), "value": flt(total_profit, 2), "datatype": "Currency"},
		{
			"label": _("Overall Profit / Km"),
			"value": flt(total_profit / total_distance, 2) if total_distance else 0,
			"datatype": "Currency",
		},
	]
