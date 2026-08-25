# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, date_diff


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	return columns, data, None, chart


def get_columns():
	return [
		{"label": _("Truck"), "fieldname": "truck", "fieldtype": "Link", "options": "Truck", "width": 110},
		{"label": _("Registration No"), "fieldname": "registration_number", "fieldtype": "Data", "width": 120},
		{"label": _("Distance Run (Km)"), "fieldname": "distance_km", "fieldtype": "Float", "width": 120},
		{"label": _("Fuel Qty (L)"), "fieldname": "fuel_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Avg Efficiency (Km/L)"), "fieldname": "avg_efficiency", "fieldtype": "Float", "width": 130, "precision": 2},
		{"label": _("Fuel Cost"), "fieldname": "fuel_cost", "fieldtype": "Currency", "width": 110},
		{"label": _("Tyre Cost"), "fieldname": "tyre_cost", "fieldtype": "Currency", "width": 110},
		{"label": _("Maintenance Cost"), "fieldname": "maintenance_cost", "fieldtype": "Currency", "width": 130},
		{"label": _("Accident Cost"), "fieldname": "accident_cost", "fieldtype": "Currency", "width": 110},
		{"label": _("Other Expenses"), "fieldname": "other_expense_cost", "fieldtype": "Currency", "width": 120},
		{"label": _("Driver Allowance"), "fieldname": "driver_allowance_cost", "fieldtype": "Currency", "width": 130},
		{"label": _("Depreciation"), "fieldname": "depreciation_cost", "fieldtype": "Currency", "width": 110},
		{"label": _("Total Cost"), "fieldname": "total_cost", "fieldtype": "Currency", "width": 120},
		{"label": _("Cost per Km"), "fieldname": "cost_per_km", "fieldtype": "Currency", "width": 110, "precision": 2},
		{"label": _("Revenue"), "fieldname": "revenue", "fieldtype": "Currency", "width": 110},
		{"label": _("Profit/Loss"), "fieldname": "profit_loss", "fieldtype": "Currency", "width": 110},
	]


def get_data(filters):
	conditions, values = get_conditions(filters)
	trucks = frappe.db.sql(
		f"""
		select name, registration_number, purchase_cost, purchase_date,
		       depreciation_rate_percent, salvage_value, company
		from `tabTruck`
		where 1=1 {conditions}
		order by name
		""",
		values,
		as_dict=True,
	)

	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	period_days = date_diff(to_date, from_date) + 1 if (from_date and to_date) else 365

	rows = []
	for truck in trucks:
		distance_km = get_distance(truck.name, from_date, to_date)
		fuel_qty, fuel_cost = get_fuel(truck.name, from_date, to_date)
		tyre_cost = get_tyre_cost(truck.name, from_date, to_date)
		maintenance_cost = get_maintenance_cost(truck.name, from_date, to_date)
		accident_cost = get_accident_cost(truck.name, from_date, to_date)
		other_expense_cost = get_other_expenses(truck.name, from_date, to_date)
		driver_allowance_cost = get_driver_allowance_cost(truck.name, from_date, to_date)
		revenue = get_revenue(truck.name, from_date, to_date)
		depreciation_cost = get_depreciation(truck, period_days)

		total_cost = flt(fuel_cost) + flt(tyre_cost) + flt(maintenance_cost) + \
			flt(accident_cost) + flt(other_expense_cost) + flt(driver_allowance_cost) + flt(depreciation_cost)

		avg_efficiency = (distance_km / fuel_qty) if fuel_qty else 0
		cost_per_km = (total_cost / distance_km) if distance_km else 0
		profit_loss = flt(revenue) - total_cost

		rows.append({
			"truck": truck.name,
			"registration_number": truck.registration_number,
			"distance_km": distance_km,
			"fuel_qty": fuel_qty,
			"avg_efficiency": avg_efficiency,
			"fuel_cost": fuel_cost,
			"tyre_cost": tyre_cost,
			"maintenance_cost": maintenance_cost,
			"accident_cost": accident_cost,
			"other_expense_cost": other_expense_cost,
			"driver_allowance_cost": driver_allowance_cost,
			"depreciation_cost": depreciation_cost,
			"total_cost": total_cost,
			"cost_per_km": cost_per_km,
			"revenue": revenue,
			"profit_loss": profit_loss,
		})

	return rows


def get_conditions(filters):
	conditions = ""
	values = {}
	if filters.get("truck"):
		conditions += " and name = %(truck)s"
		values["truck"] = filters.get("truck")
	if filters.get("company"):
		conditions += " and company = %(company)s"
		values["company"] = filters.get("company")
	return conditions, values


def date_conditions(field, from_date, to_date):
	conditions = " and docstatus = 1"
	values = {}
	if from_date:
		conditions += f" and {field} >= %(from_date)s"
		values["from_date"] = from_date
	if to_date:
		conditions += f" and {field} <= %(to_date)s"
		values["to_date"] = to_date
	return conditions, values


def get_distance(truck, from_date, to_date):
	conditions, values = date_conditions("date", from_date, to_date)
	values["truck"] = truck
	result = frappe.db.sql(
		f"""
		select min(odometer_reading), max(odometer_reading)
		from `tabTruck Fuel Log`
		where truck = %(truck)s {conditions}
		""",
		values,
	)
	if result and result[0][0] is not None and result[0][1] is not None:
		return flt(result[0][1]) - flt(result[0][0])
	return 0


def get_fuel(truck, from_date, to_date):
	conditions, values = date_conditions("date", from_date, to_date)
	values["truck"] = truck
	result = frappe.db.sql(
		f"""
		select sum(fuel_qty_litres), sum(total_amount)
		from `tabTruck Fuel Log`
		where truck = %(truck)s {conditions}
		""",
		values,
	)
	if result and result[0][0]:
		return flt(result[0][0]), flt(result[0][1])
	return 0, 0


def get_tyre_cost(truck, from_date, to_date):
	conditions, values = date_conditions("date", from_date, to_date)
	values["truck"] = truck
	result = frappe.db.sql(
		f"""
		select sum(cost)
		from `tabTyre Movement Log`
		where truck = %(truck)s {conditions}
		""",
		values,
	)
	return flt(result[0][0]) if result and result[0][0] else 0


def get_maintenance_cost(truck, from_date, to_date):
	conditions, values = date_conditions("date", from_date, to_date)
	values["truck"] = truck
	result = frappe.db.sql(
		f"""
		select sum(total_cost)
		from `tabTruck Maintenance Log`
		where truck = %(truck)s {conditions}
		""",
		values,
	)
	return flt(result[0][0]) if result and result[0][0] else 0


def get_accident_cost(truck, from_date, to_date):
	"""Net cost (repair + other − insurance recovered) of accidents in range."""
	conditions, values = date_conditions("date(date_of_accident)", from_date, to_date)
	values["truck"] = truck
	result = frappe.db.sql(
		f"""
		select sum(net_cost)
		from `tabAccident Report`
		where truck = %(truck)s {conditions}
		""",
		values,
	)
	return flt(result[0][0]) if result and result[0][0] else 0


def get_other_expenses(truck, from_date, to_date):
	conditions, values = date_conditions("date", from_date, to_date)
	values["truck"] = truck
	result = frappe.db.sql(
		f"""
		select sum(amount)
		from `tabTruck Expense`
		where truck = %(truck)s {conditions}
		""",
		values,
	)
	return flt(result[0][0]) if result and result[0][0] else 0


def get_empty_return_distance(truck, from_date, to_date):
	"""Distance run on Completed 'Empty Return to Depot' legs — the
	dead-mileage portion of total distance (repositioning an empty
	container back to base, as opposed to a revenue-earning Loaded Haul).
	Split out here so it can be reported/costed separately rather than
	blended into total distance."""
	result = frappe.db.sql(
		"""
		select sum(distance_km)
		from `tabTruck Trip`
		where truck = %(truck)s and status = 'Completed' and trip_type = 'Empty Return to Depot'
		and trip_date between %(from_date)s and %(to_date)s
		""",
		{"truck": truck, "from_date": from_date, "to_date": to_date},
	)
	return flt(result[0][0]) if result and result[0][0] else 0


def get_pending_empty_returns(truck):
	"""Count of Empty Return to Depot trips still Planned or Ongoing for
	this truck — i.e. empty containers not yet handed back at the depot.
	Deliberately not date-filtered: this is a live backlog figure (what's
	outstanding right now), not a historical count for the report period."""
	return frappe.db.count(
		"Truck Trip",
		filters={
			"truck": truck,
			"trip_type": "Empty Return to Depot",
			"status": ["in", ["Planned", "Ongoing"]],
		},
	)


def get_driver_allowance_cost(truck, from_date, to_date):
	"""Driver Mileage Payment is period-based (from_date/to_date on the
	payment itself, e.g. a fortnightly run) rather than a single-date log
	like fuel or maintenance, so this matches on period overlap: any
	submitted payment for this truck whose own from_date/to_date range
	overlaps the report's requested range. Includes both the computed
	per-route mileage pay and any Other Allowance / Bonus on the same
	payment, since total_amount is the sum of both."""
	result = frappe.db.sql(
		"""
		select sum(total_amount)
		from `tabDriver Mileage Payment`
		where truck = %(truck)s and docstatus = 1
		and from_date <= %(to_date)s and to_date >= %(from_date)s
		""",
		{"truck": truck, "from_date": from_date, "to_date": to_date},
	)
	return flt(result[0][0]) if result and result[0][0] else 0


def get_revenue(truck, from_date, to_date):
	conditions = ""
	values = {"truck": truck}
	if from_date:
		conditions += " and trip_date >= %(from_date)s"
		values["from_date"] = from_date
	if to_date:
		conditions += " and trip_date <= %(to_date)s"
		values["to_date"] = to_date
	result = frappe.db.sql(
		f"""
		select sum(revenue)
		from `tabTruck Trip`
		where truck = %(truck)s and status = 'Completed' {conditions}
		""",
		values,
	)
	return flt(result[0][0]) if result and result[0][0] else 0


def get_depreciation(truck, period_days):
	"""Straight-line depreciation, prorated for the filtered period."""
	if not truck.purchase_cost:
		return 0
	rate = flt(truck.depreciation_rate_percent) or 20
	salvage = flt(truck.salvage_value)
	annual_depreciation = (flt(truck.purchase_cost) - salvage) * (rate / 100)
	if annual_depreciation <= 0:
		return 0
	daily_depreciation = annual_depreciation / 365
	return daily_depreciation * period_days


def get_chart(data):
	if not data:
		return None
	return {
		"data": {
			"labels": [row["truck"] for row in data],
			"datasets": [
				{"name": "Cost per Km", "values": [flt(row["cost_per_km"], 2) for row in data]},
			],
		},
		"type": "bar",
		"colors": ["#2E86C1"],
	}
