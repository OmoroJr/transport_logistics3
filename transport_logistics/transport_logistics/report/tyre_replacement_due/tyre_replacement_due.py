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
	return columns, data, None, chart


def get_columns():
	return [
		{"label": _("Tyre"), "fieldname": "name", "fieldtype": "Link", "options": "Tyre", "width": 110},
		{"label": _("Brand"), "fieldname": "brand", "fieldtype": "Data", "width": 100},
		{"label": _("Size"), "fieldname": "size", "fieldtype": "Data", "width": 100},
		{"label": _("Vehicle Type"), "fieldname": "current_vehicle_type", "fieldtype": "Data", "width": 90},
		{"label": _("Truck"), "fieldname": "current_truck", "fieldtype": "Link", "options": "Truck", "width": 100},
		{"label": _("Trailer"), "fieldname": "current_trailer", "fieldtype": "Link", "options": "Trailer", "width": 100},
		{"label": _("Position"), "fieldname": "current_position", "fieldtype": "Data", "width": 150},
		{"label": _("Km Run"), "fieldname": "total_km_run", "fieldtype": "Float", "width": 100},
		{"label": _("Expected Life (Km)"), "fieldname": "expected_life_km", "fieldtype": "Float", "width": 130},
		{"label": _("% Used"), "fieldname": "percent_used", "fieldtype": "Percent", "width": 90},
		{"label": _("Retreads"), "fieldname": "retread_count", "fieldtype": "Int", "width": 80},
		{"label": _("Status"), "fieldname": "replacement_status", "fieldtype": "Data", "width": 100},
	]


def get_data(filters):
	threshold = flt(filters.get("threshold_percent")) or 80

	conditions = "where t.status in ('Fitted', 'In Stock')"
	values = {}
	if filters.get("truck"):
		conditions += " and t.current_truck = %(truck)s"
		values["truck"] = filters.get("truck")
	if filters.get("trailer"):
		conditions += " and t.current_trailer = %(trailer)s"
		values["trailer"] = filters.get("trailer")
	if filters.get("vehicle_type"):
		conditions += " and t.current_vehicle_type = %(vehicle_type)s"
		values["vehicle_type"] = filters.get("vehicle_type")
	if filters.get("status"):
		conditions += " and t.status = %(status)s"
		values["status"] = filters.get("status")

	tyres = frappe.db.sql(
		f"""
		select t.name, t.brand, t.size, t.current_vehicle_type, t.current_truck,
		       t.current_trailer, t.current_position,
		       t.total_km_run, t.expected_life_km, t.retread_count, t.status
		from `tabTyre` t
		{conditions}
		order by (t.total_km_run / nullif(t.expected_life_km, 0)) desc
		""",
		values,
		as_dict=True,
	)

	rows = []
	for tyre in tyres:
		if not tyre.expected_life_km:
			continue
		percent_used = (flt(tyre.total_km_run) / flt(tyre.expected_life_km)) * 100

		if percent_used < threshold:
			continue  # only surface tyres that need attention

		replacement_status = "Overdue" if percent_used >= 100 else "Due Soon"

		rows.append(
			{
				"name": tyre.name,
				"brand": tyre.brand,
				"size": tyre.size,
				"current_vehicle_type": tyre.current_vehicle_type,
				"current_truck": tyre.current_truck,
				"current_trailer": tyre.current_trailer,
				"current_position": tyre.current_position,
				"total_km_run": tyre.total_km_run,
				"expected_life_km": tyre.expected_life_km,
				"percent_used": percent_used,
				"retread_count": tyre.retread_count,
				"replacement_status": replacement_status,
			}
		)

	return rows


def get_chart(data):
	if not data:
		return None
	return {
		"data": {
			"labels": [row["name"] for row in data],
			"datasets": [
				{"name": "% of Expected Life Used", "values": [flt(row["percent_used"], 1) for row in data]},
			],
		},
		"type": "bar",
		"colors": ["#E67E22"],
	}
