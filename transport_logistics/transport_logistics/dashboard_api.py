# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Backend for the Truck Cost Dashboard page. Deliberately reuses the exact
same per-truck helper functions as the Truck Cost Analysis report (imported
below) rather than re-deriving the numbers a second time — so the dashboard
and the report can never silently disagree with each other.
"""

import calendar

import frappe
from frappe.utils import flt, getdate, date_diff, add_months, get_first_day, get_last_day

from transport_logistics.transport_logistics.report.truck_cost_analysis.truck_cost_analysis import (
	get_distance,
	get_fuel,
	get_tyre_cost,
	get_maintenance_cost,
	get_accident_cost,
	get_other_expenses,
	get_revenue,
	get_depreciation,
)

BREAKDOWN_COLORS = {
	"Fuel": "#2E86C1",
	"Maintenance": "#1B4F72",
	"Tyres": "#5DADE2",
	"Depreciation": "#85929E",
	"Other Expenses": "#F1C40F",
	"Accidents": "#E67E22",
}

TREND_MONTHS = 6


@frappe.whitelist()
def get_truck_cost_dashboard(truck=None, from_date=None, to_date=None, company=None):
	if not from_date or not to_date:
		frappe.throw("From Date and To Date are required")

	trucks = _get_trucks(truck, company)
	period_days = date_diff(to_date, from_date) + 1

	totals = _zero_totals()
	for t in trucks:
		_accumulate(totals, t, from_date, to_date, period_days)

	total_cost = (
		totals["fuel_cost"] + totals["tyre_cost"] + totals["maintenance_cost"]
		+ totals["accident_cost"] + totals["other_expense_cost"] + totals["depreciation_cost"]
	)
	avg_efficiency = (totals["distance_km"] / totals["fuel_qty"]) if totals["fuel_qty"] else 0
	cost_per_km = (total_cost / totals["distance_km"]) if totals["distance_km"] else 0
	profit_loss = totals["revenue"] - total_cost
	profit_per_km = (profit_loss / totals["distance_km"]) if totals["distance_km"] else 0

	breakdown = _build_breakdown(totals, total_cost)
	trend = _build_trend(trucks, to_date)

	return {
		"distance_km": totals["distance_km"],
		"fuel_qty": totals["fuel_qty"],
		"fuel_cost": totals["fuel_cost"],
		"tyre_cost": totals["tyre_cost"],
		"maintenance_cost": totals["maintenance_cost"],
		"accident_cost": totals["accident_cost"],
		"other_expense_cost": totals["other_expense_cost"],
		"depreciation_cost": totals["depreciation_cost"],
		"total_cost": total_cost,
		"avg_efficiency": avg_efficiency,
		"cost_per_km": cost_per_km,
		"revenue": totals["revenue"],
		"profit_loss": profit_loss,
		"profit_per_km": profit_per_km,
		"breakdown": breakdown,
		"trend": trend,
		"truck_count": len(trucks),
	}


def _get_trucks(truck, company):
	filters = {}
	if truck:
		filters["name"] = truck
	if company:
		filters["company"] = company
	return frappe.get_all(
		"Truck",
		filters=filters,
		fields=["name", "purchase_cost", "purchase_date", "depreciation_rate_percent", "salvage_value", "company"],
	)


def _get_trip_distance(truck, from_date, to_date):
	result = frappe.db.sql(
		"""
		select sum(distance_km)
		from `tabTruck Trip`
		where truck = %(truck)s and status = 'Completed'
		and trip_date between %(from_date)s and %(to_date)s
		""",
		{"truck": truck, "from_date": from_date, "to_date": to_date},
	)
	return flt(result[0][0]) if result and result[0][0] else 0


def _get_total_distance(truck, from_date, to_date):
	"""Distance can come from two independent sources that won't always both
	be populated: Truck Fuel Log odometer readings (min/max in range), or
	Truck Trip distance_km. Neither alone is reliable if the fleet only uses
	one of the two logging habits, so take whichever is larger rather than
	silently showing 0 just because one source is empty. This deliberately
	doesn't add them together, since that would double-count trips that were
	also captured by a fuel-log odometer reading covering the same driving."""
	fuel_log_distance = get_distance(truck, from_date, to_date)
	trip_distance = _get_trip_distance(truck, from_date, to_date)
	return max(fuel_log_distance, trip_distance)


def _zero_totals():
	return {
		"distance_km": 0.0, "fuel_qty": 0.0, "fuel_cost": 0.0, "tyre_cost": 0.0,
		"maintenance_cost": 0.0, "accident_cost": 0.0, "other_expense_cost": 0.0,
		"depreciation_cost": 0.0, "revenue": 0.0,
	}


def _accumulate(totals, truck_row, from_date, to_date, period_days):
	name = truck_row["name"]
	totals["distance_km"] += _get_total_distance(name, from_date, to_date)
	fuel_qty, fuel_cost = get_fuel(name, from_date, to_date)
	totals["fuel_qty"] += fuel_qty
	totals["fuel_cost"] += fuel_cost
	totals["tyre_cost"] += get_tyre_cost(name, from_date, to_date)
	totals["maintenance_cost"] += get_maintenance_cost(name, from_date, to_date)
	totals["accident_cost"] += get_accident_cost(name, from_date, to_date)
	totals["other_expense_cost"] += get_other_expenses(name, from_date, to_date)
	totals["revenue"] += get_revenue(name, from_date, to_date)
	totals["depreciation_cost"] += get_depreciation(frappe._dict(truck_row), period_days)


def _build_breakdown(totals, total_cost):
	if not total_cost:
		return []
	segments = [
		("Fuel", totals["fuel_cost"]),
		("Maintenance", totals["maintenance_cost"]),
		("Tyres", totals["tyre_cost"]),
		("Depreciation", totals["depreciation_cost"]),
		("Other Expenses", totals["other_expense_cost"]),
		("Accidents", totals["accident_cost"]),
	]
	breakdown = []
	for label, value in segments:
		if value <= 0:
			continue
		breakdown.append({
			"label": label,
			"value": value,
			"percent": (value / total_cost) * 100,
			"color": BREAKDOWN_COLORS.get(label, "#95A5A6"),
		})
	return breakdown


def _build_trend(trucks, to_date):
	"""Trailing N months of Total Cost vs Revenue, ending at to_date's month,
	independent of the from_date/to_date range used for the KPI cards above —
	this gives useful historical context even when a single month is selected."""
	anchor = get_last_day(getdate(to_date))
	trend = []

	for i in range(TREND_MONTHS - 1, -1, -1):
		month_end = get_last_day(add_months(anchor, -i))
		month_start = get_first_day(month_end)
		period_days = date_diff(month_end, month_start) + 1

		month_total_cost = 0.0
		month_revenue = 0.0
		for t in trucks:
			name = t["name"]
			fuel_qty, fuel_cost = get_fuel(name, month_start, month_end)
			cost = (
				fuel_cost
				+ get_tyre_cost(name, month_start, month_end)
				+ get_maintenance_cost(name, month_start, month_end)
				+ get_accident_cost(name, month_start, month_end)
				+ get_other_expenses(name, month_start, month_end)
				+ get_depreciation(frappe._dict(t), period_days)
			)
			month_total_cost += cost
			month_revenue += get_revenue(name, month_start, month_end)

		trend.append({
			"month": f"{calendar.month_abbr[month_end.month]} {month_end.year}",
			"total_cost": month_total_cost,
			"revenue": month_revenue,
		})

	return trend


@frappe.whitelist()
def get_cost_component_details(component, truck=None, from_date=None, to_date=None, company=None):
	"""Powers the click-to-drill-down on each KPI card: returns the actual
	underlying records that sum to the figure shown, not just the total.
	Returns {"columns": [...], "rows": [[...], ...], "total_label": str}."""
	if not from_date or not to_date:
		frappe.throw("From Date and To Date are required")

	trucks = _get_trucks(truck, company)
	truck_names = [t["name"] for t in trucks]
	if not truck_names:
		return {"columns": [], "rows": [], "total_label": None}

	handler = _COMPONENT_HANDLERS.get(component)
	if not handler:
		frappe.throw(f"Unknown component: {component}")

	return handler(truck_names, trucks, from_date, to_date)


def _in_clause(names):
	placeholders = ", ".join(["%s"] * len(names))
	return placeholders


def _fuel_details(truck_names, trucks, from_date, to_date):
	rows = frappe.db.sql(
		f"""
		select truck, date, fuel_qty_litres, rate_per_litre, total_amount,
		       fuel_station, fuel_efficiency_km_per_litre
		from `tabTruck Fuel Log`
		where docstatus = 1 and truck in ({_in_clause(truck_names)})
		and date between %s and %s
		order by date desc
		""",
		(*truck_names, from_date, to_date),
		as_dict=True,
	)
	return {
		"columns": ["Truck", "Date", "Qty (L)", "Rate", "Amount", "Station", "Km/L"],
		"rows": [
			[r.truck, str(r.date), flt(r.fuel_qty_litres, 1), flt(r.rate_per_litre, 2),
			 flt(r.total_amount, 2), r.fuel_station or "", flt(r.fuel_efficiency_km_per_litre, 2)]
			for r in rows
		],
		"total_label": "Fuel Cost",
	}


def _maintenance_details(truck_names, trucks, from_date, to_date):
	rows = frappe.db.sql(
		f"""
		select truck, date, maintenance_type, description, vendor,
		       parts_cost, labour_cost, other_cost, total_cost
		from `tabTruck Maintenance Log`
		where docstatus = 1 and truck in ({_in_clause(truck_names)})
		and date between %s and %s
		order by date desc
		""",
		(*truck_names, from_date, to_date),
		as_dict=True,
	)
	return {
		"columns": ["Truck", "Date", "Type", "Vendor", "Parts", "Labour", "Other", "Total"],
		"rows": [
			[r.truck, str(r.date), r.maintenance_type, r.vendor or "",
			 flt(r.parts_cost, 2), flt(r.labour_cost, 2), flt(r.other_cost, 2), flt(r.total_cost, 2)]
			for r in rows
		],
		"total_label": "Maintenance Cost",
	}


def _tyre_details(truck_names, trucks, from_date, to_date):
	rows = frappe.db.sql(
		f"""
		select truck, tyre, date, movement_type, position, cost, vendor
		from `tabTyre Movement Log`
		where docstatus = 1 and truck in ({_in_clause(truck_names)})
		and date between %s and %s and cost > 0
		order by date desc
		""",
		(*truck_names, from_date, to_date),
		as_dict=True,
	)
	return {
		"columns": ["Truck", "Tyre", "Date", "Movement", "Position", "Vendor", "Cost"],
		"rows": [
			[r.truck, r.tyre, str(r.date), r.movement_type, r.position or "",
			 r.vendor or "", flt(r.cost, 2)]
			for r in rows
		],
		"total_label": "Tyre Cost",
	}


def _other_expense_details(truck_names, trucks, from_date, to_date):
	rows = frappe.db.sql(
		f"""
		select truck, date, expense_type, amount, reference_no
		from `tabTruck Expense`
		where docstatus = 1 and truck in ({_in_clause(truck_names)})
		and date between %s and %s
		order by date desc
		""",
		(*truck_names, from_date, to_date),
		as_dict=True,
	)
	return {
		"columns": ["Truck", "Date", "Expense Type", "Reference", "Amount"],
		"rows": [
			[r.truck, str(r.date), r.expense_type, r.reference_no or "", flt(r.amount, 2)]
			for r in rows
		],
		"total_label": "Other Expenses",
	}


def _accident_details(truck_names, trucks, from_date, to_date):
	rows = frappe.db.sql(
		f"""
		select truck, date_of_accident, severity, repair_cost, other_cost,
		       claim_amount_recovered, net_cost
		from `tabAccident Report`
		where docstatus = 1 and truck in ({_in_clause(truck_names)})
		and date(date_of_accident) between %s and %s
		order by date_of_accident desc
		""",
		(*truck_names, from_date, to_date),
		as_dict=True,
	)
	return {
		"columns": ["Truck", "Date", "Severity", "Repair", "Other", "Recovered", "Net Cost"],
		"rows": [
			[r.truck, str(r.date_of_accident), r.severity, flt(r.repair_cost, 2),
			 flt(r.other_cost, 2), flt(r.claim_amount_recovered, 2), flt(r.net_cost, 2)]
			for r in rows
		],
		"total_label": "Accident Cost",
	}


def _depreciation_details(truck_names, trucks, from_date, to_date):
	period_days = date_diff(to_date, from_date) + 1
	rows = []
	for t in trucks:
		dep = get_depreciation(frappe._dict(t), period_days)
		if dep <= 0:
			continue
		rows.append([
			t["name"], flt(t.get("purchase_cost"), 2), flt(t.get("depreciation_rate_percent") or 20, 1),
			flt(t.get("salvage_value"), 2), period_days, flt(dep, 2),
		])
	return {
		"columns": ["Truck", "Purchase Cost", "Rate %/yr", "Salvage Value", "Days in Period", "Depreciation"],
		"rows": rows,
		"total_label": "Depreciation",
	}


def _distance_details(truck_names, trucks, from_date, to_date):
	trips = frappe.db.sql(
		f"""
		select truck, trip_date, origin, destination, route, distance_km
		from `tabTruck Trip`
		where status = 'Completed' and truck in ({_in_clause(truck_names)})
		and trip_date between %s and %s
		order by trip_date desc
		""",
		(*truck_names, from_date, to_date),
		as_dict=True,
	)
	return {
		"columns": ["Truck", "Date", "Route", "Origin", "Destination", "Distance (Km)"],
		"rows": [
			[r.truck, str(r.trip_date), r.route or "", r.origin or "", r.destination or "", flt(r.distance_km, 1)]
			for r in trips
		],
		"total_label": "Distance (from logged Trips; fuel-log odometer readings may add further distance not tied to a specific Trip)",
	}


def _total_cost_details(truck_names, trucks, from_date, to_date):
	period_days = date_diff(to_date, from_date) + 1
	totals = _zero_totals()
	for t in trucks:
		_accumulate(totals, t, from_date, to_date, period_days)
	total_cost = (
		totals["fuel_cost"] + totals["tyre_cost"] + totals["maintenance_cost"]
		+ totals["accident_cost"] + totals["other_expense_cost"] + totals["depreciation_cost"]
	)
	breakdown = _build_breakdown(totals, total_cost)
	return {
		"columns": ["Category", "Amount", "% of Total"],
		"rows": [[b["label"], flt(b["value"], 2), f"{b['percent']:.1f}%"] for b in breakdown],
		"total_label": "Total Cost",
	}


_COMPONENT_HANDLERS = {
	"fuel": _fuel_details,
	"maintenance": _maintenance_details,
	"tyre": _tyre_details,
	"other": _other_expense_details,
	"accident": _accident_details,
	"depreciation": _depreciation_details,
	"distance": _distance_details,
	"total": _total_cost_details,
}
