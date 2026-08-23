# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Route Profitability (see that report) aggregates by route. This is the
same underlying calculation at the finer grain of one row per individual
Completed Truck Trip — Trip Revenue − Fuel − Driver Cost = Trip Profit.

Same honesty caveat as Route Profitability: Toll, parking, fines, and
other Truck Expense entries are recorded against a truck and a date, not
a specific trip, so they're NOT included here. "Total Cost" is fuel +
driver pay only — treat Profit as a contribution margin, not a full P&L
per trip.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	summary = get_summary(data)
	return columns, data, None, None, summary


def get_columns():
	return [
		{"label": _("Trip"), "fieldname": "name", "fieldtype": "Link", "options": "Truck Trip", "width": 110},
		{"label": _("Date"), "fieldname": "trip_date", "fieldtype": "Date", "width": 95},
		{"label": _("Truck"), "fieldname": "truck", "fieldtype": "Link", "options": "Truck", "width": 100},
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Link", "options": "Employee", "width": 100},
		{"label": _("Driver Name"), "fieldname": "driver_name", "fieldtype": "Data", "width": 120},
		{"label": _("Route"), "fieldname": "route", "fieldtype": "Link", "options": "Route", "width": 100},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 110},
		{"label": _("Origin"), "fieldname": "origin", "fieldtype": "Data", "width": 100},
		{"label": _("Destination"), "fieldname": "destination", "fieldtype": "Data", "width": 100},
		{"label": _("Distance (Km)"), "fieldname": "distance_km", "fieldtype": "Float", "width": 100},
		{"label": _("Revenue"), "fieldname": "revenue", "fieldtype": "Currency", "width": 100},
		{"label": _("Fuel Cost"), "fieldname": "fuel_cost", "fieldtype": "Currency", "width": 100},
		{"label": _("Driver Cost"), "fieldname": "driver_cost", "fieldtype": "Currency", "width": 100},
		{"label": _("Total Cost"), "fieldname": "total_cost", "fieldtype": "Currency", "width": 100},
		{"label": _("Profit"), "fieldname": "profit", "fieldtype": "Currency", "width": 100},
		{"label": _("Profit / Km"), "fieldname": "profit_per_km", "fieldtype": "Currency", "width": 100},
		{"label": _("Margin %"), "fieldname": "margin_percent", "fieldtype": "Percent", "width": 90},
	]


def get_data(filters):
	from_date = getdate(filters.get("from_date")) if filters.get("from_date") else getdate(today()).replace(day=1)
	to_date = getdate(filters.get("to_date")) if filters.get("to_date") else getdate(today())

	conditions = ["t.trip_date between %(from_date)s and %(to_date)s", "t.status = 'Completed'"]
	values = {"from_date": from_date, "to_date": to_date}

	for field in ("truck", "driver", "route", "company"):
		if filters.get(field):
			conditions.append(f"t.{field} = %({field})s")
			values[field] = filters.get(field)

	where_clause = " and ".join(conditions)

	trips = frappe.db.sql(
		f"""
		select
			t.name, t.trip_date, t.truck, t.driver, emp.employee_name as driver_name,
			t.route, r.origin, r.destination, r.driver_rate,
			t.customer, t.distance_km, t.revenue
		from `tabTruck Trip` t
		left join `tabEmployee` emp on emp.name = t.driver
		left join `tabRoute` r on r.name = t.route
		where {where_clause}
		order by t.trip_date desc
		""",
		values,
		as_dict=True,
	)

	trip_names = [t.name for t in trips]
	fuel_by_trip = {}
	if trip_names:
		fuel_rows = frappe.db.sql(
			"""
			select truck_trip, sum(total_amount) as fuel_cost
			from `tabTruck Fuel Log`
			where docstatus = 1 and reason_for_fuelling = 'For Trip'
			and truck_trip in %(trips)s
			group by truck_trip
			""",
			{"trips": trip_names},
			as_dict=True,
		)
		fuel_by_trip = {r.truck_trip: flt(r.fuel_cost) for r in fuel_rows}

	data = []
	for t in trips:
		fuel_cost = fuel_by_trip.get(t.name, 0)
		driver_cost = flt(t.driver_rate) if t.route else 0
		total_cost = fuel_cost + driver_cost
		revenue = flt(t.revenue)
		profit = revenue - total_cost

		data.append({
			"name": t.name,
			"trip_date": t.trip_date,
			"truck": t.truck,
			"driver": t.driver,
			"driver_name": t.driver_name,
			"route": t.route,
			"customer": t.customer,
			"origin": t.origin,
			"destination": t.destination,
			"distance_km": flt(t.distance_km),
			"revenue": revenue,
			"fuel_cost": fuel_cost,
			"driver_cost": driver_cost,
			"total_cost": total_cost,
			"profit": profit,
			"profit_per_km": (profit / t.distance_km) if t.distance_km else 0,
			"margin_percent": (profit / revenue * 100) if revenue else 0,
		})

	return data


def get_summary(data):
	if not data:
		return []

	total_revenue = sum(r["revenue"] for r in data)
	total_cost = sum(r["total_cost"] for r in data)
	total_profit = sum(r["profit"] for r in data)
	total_distance = sum(r["distance_km"] for r in data)

	return [
		{"label": _("Trips"), "value": len(data), "datatype": "Int"},
		{"label": _("Total Revenue"), "value": flt(total_revenue, 2), "datatype": "Currency"},
		{"label": _("Total Cost"), "value": flt(total_cost, 2), "datatype": "Currency"},
		{"label": _("Total Profit"), "value": flt(total_profit, 2), "datatype": "Currency"},
		{
			"label": _("Overall Profit / Km"),
			"value": flt(total_profit / total_distance, 2) if total_distance else 0,
			"datatype": "Currency",
		},
	]
