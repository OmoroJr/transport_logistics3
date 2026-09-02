# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Full-life view of every Tyre: purchase cost, current fitment, cost-per-km
run so far, latest tread depth reading, and how many times it has moved
(fitted/removed/rotated/retreaded). Complements Tyre Replacement Due (which
only lists tyres nearing end of life) with the complete picture per tyre.
"""

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
		{"label": _("Tyre"), "fieldname": "name", "fieldtype": "Link", "options": "Tyre", "width": 110},
		{"label": _("Serial No"), "fieldname": "tyre_serial_no", "fieldtype": "Data", "width": 110},
		{"label": _("Brand"), "fieldname": "brand", "fieldtype": "Data", "width": 90},
		{"label": _("Model"), "fieldname": "model", "fieldtype": "Data", "width": 90},
		{"label": _("Size"), "fieldname": "size", "fieldtype": "Data", "width": 80},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
		{"label": _("Purchase Date"), "fieldname": "purchase_date", "fieldtype": "Date", "width": 100},
		{"label": _("Purchase Cost"), "fieldname": "purchase_cost", "fieldtype": "Currency", "width": 100},
		{"label": _("Expected Life (Km)"), "fieldname": "expected_life_km", "fieldtype": "Float", "width": 130},
		{"label": _("Total Km Run"), "fieldname": "total_km_run", "fieldtype": "Float", "width": 100},
		{"label": _("Life Used %"), "fieldname": "life_used_percent", "fieldtype": "Percent", "width": 100},
		{"label": _("Cost/Km"), "fieldname": "cost_per_km", "fieldtype": "Currency", "width": 90, "precision": 2},
		{"label": _("Retreads"), "fieldname": "retread_count", "fieldtype": "Int", "width": 80},
		{"label": _("Vehicle Type"), "fieldname": "current_vehicle_type", "fieldtype": "Data", "width": 100},
		{"label": _("Current Truck"), "fieldname": "current_truck", "fieldtype": "Link", "options": "Truck", "width": 100},
		{"label": _("Current Trailer"), "fieldname": "current_trailer", "fieldtype": "Link", "options": "Trailer", "width": 100},
		{"label": _("Position"), "fieldname": "current_position", "fieldtype": "Data", "width": 90},
		{"label": _("Movements"), "fieldname": "movement_count", "fieldtype": "Int", "width": 90},
		{"label": _("Last Tread Depth (mm)"), "fieldname": "last_tread_depth_mm", "fieldtype": "Float", "width": 140},
		{"label": _("Last Inspection Date"), "fieldname": "last_inspection_date", "fieldtype": "Date", "width": 130},
		{"label": _("Last Inspection Status"), "fieldname": "last_inspection_status", "fieldtype": "Data", "width": 140},
		{"label": _("Flagged for Replacement"), "fieldname": "flagged_for_replacement", "fieldtype": "Check", "width": 130},
	]


def get_data(filters):
	conditions, values = get_conditions(filters)

	rows = frappe.db.sql(
		f"""
		select
			t.name, t.tyre_serial_no, t.brand, t.model, t.size, t.status,
			t.purchase_date, t.purchase_cost, t.expected_life_km, t.total_km_run,
			t.retread_count, t.current_vehicle_type, t.current_truck,
			t.current_trailer, t.current_position, t.flagged_for_replacement,
			(select count(*) from `tabTyre Movement Log` m where m.tyre = t.name and m.docstatus = 1) as movement_count
		from `tabTyre` t
		where 1=1 {conditions}
		order by t.name
		""",
		values,
		as_dict=True,
	)

	tyre_names = [r.name for r in rows]
	last_inspections = get_last_inspections(tyre_names)

	for row in rows:
		row["life_used_percent"] = (
			(flt(row.total_km_run) / flt(row.expected_life_km) * 100) if row.expected_life_km else 0
		)
		row["cost_per_km"] = (
			(flt(row.purchase_cost) / flt(row.total_km_run)) if row.total_km_run else 0
		)
		inspection = last_inspections.get(row.name)
		if inspection:
			row["last_tread_depth_mm"] = inspection.tread_depth_mm
			row["last_inspection_date"] = inspection.inspection_date
			row["last_inspection_status"] = inspection.status

	return rows


def get_last_inspections(tyre_names):
	if not tyre_names:
		return {}

	rows = frappe.db.sql(
		"""
		select tdi.tyre, tdi.tread_depth_mm, tdi.inspection_date, tdi.status
		from `tabTyre Depth Inspection` tdi
		inner join (
			select tyre, max(inspection_date) as max_date
			from `tabTyre Depth Inspection`
			where docstatus = 1 and tyre in %(tyres)s
			group by tyre
		) latest on latest.tyre = tdi.tyre and latest.max_date = tdi.inspection_date
		where tdi.docstatus = 1
		""",
		{"tyres": tyre_names},
		as_dict=True,
	)
	return {r.tyre: r for r in rows}


def get_conditions(filters):
	conditions = ""
	values = {}

	if filters.get("status"):
		conditions += " and t.status = %(status)s"
		values["status"] = filters.get("status")
	if filters.get("brand"):
		conditions += " and t.brand like %(brand)s"
		values["brand"] = f"%{filters.get('brand')}%"
	if filters.get("current_vehicle_type"):
		conditions += " and t.current_vehicle_type = %(current_vehicle_type)s"
		values["current_vehicle_type"] = filters.get("current_vehicle_type")
	if filters.get("current_truck"):
		conditions += " and t.current_truck = %(current_truck)s"
		values["current_truck"] = filters.get("current_truck")
	if filters.get("current_trailer"):
		conditions += " and t.current_trailer = %(current_trailer)s"
		values["current_trailer"] = filters.get("current_trailer")
	if filters.get("only_flagged"):
		conditions += " and t.flagged_for_replacement = 1"

	return conditions, values


def get_chart(data):
	if not data:
		return None

	status_counts = {}
	for row in data:
		key = row.status or _("Unknown")
		status_counts[key] = status_counts.get(key, 0) + 1

	return {
		"data": {
			"labels": list(status_counts.keys()),
			"datasets": [
				{"name": "Tyre Count", "values": list(status_counts.values())},
			],
		},
		"type": "bar",
		"colors": ["#5D6D7E"],
	}


def get_summary(data):
	if not data:
		return []

	total_cost = sum(flt(r.purchase_cost) for r in data)
	total_km = sum(flt(r.total_km_run) for r in data)
	avg_cost_per_km = (total_cost / total_km) if total_km else 0
	flagged = [r for r in data if r.flagged_for_replacement]

	return [
		{"label": _("Total Tyres"), "value": len(data), "datatype": "Int"},
		{"label": _("Total Purchase Cost"), "value": flt(total_cost, 2), "datatype": "Currency"},
		{"label": _("Total Km Run"), "value": flt(total_km, 0), "datatype": "Float"},
		{"label": _("Fleet Avg Cost/Km"), "value": flt(avg_cost_per_km, 2), "datatype": "Currency"},
		{
			"label": _("Flagged for Replacement"),
			"value": len(flagged),
			"datatype": "Int",
			"indicator": "Red" if flagged else "Green",
		},
	]
