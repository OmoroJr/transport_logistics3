# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Consolidated view of Trip Pre Inspection records (see
../../doctype/trip_pre_inspection/trip_pre_inspection.py), including a
summary of the optional Tyre Pressure Check section — how many tyres were
recorded and whether any came back Low/High. Tyre pressure is purely
informational here, same as on the doctype itself: it never affects
Overall Status and a truck with no tyre pressure readings at all is not
flagged as a problem.
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
		{"label": _("Inspection"), "fieldname": "name", "fieldtype": "Link", "options": "Trip Pre Inspection", "width": 150},
		{"label": _("Truck"), "fieldname": "truck", "fieldtype": "Link", "options": "Truck", "width": 110},
		{"label": _("Inspection Date"), "fieldname": "inspection_date", "fieldtype": "Date", "width": 110},
		{"label": _("Inspector"), "fieldname": "inspector", "fieldtype": "Link", "options": "Employee", "width": 140},
		{"label": _("Overall Status"), "fieldname": "overall_status", "fieldtype": "Data", "width": 110},
		{"label": _("Failed Checklist Items"), "fieldname": "failed_items", "fieldtype": "Data", "width": 220},
		{"label": _("Tyre Pressure Checked"), "fieldname": "tyre_pressure_checked", "fieldtype": "Data", "width": 130},
		{"label": _("Tyres Recorded"), "fieldname": "tyres_recorded", "fieldtype": "Int", "width": 100},
		{"label": _("Tyre Pressure Issues"), "fieldname": "tyre_pressure_issues", "fieldtype": "Data", "width": 220},
		{"label": _("Submitted"), "fieldname": "docstatus_label", "fieldtype": "Data", "width": 90},
	]


def get_data(filters):
	conditions, values = _build_conditions(filters)

	inspections = frappe.db.sql(
		f"""
		select name, truck, inspection_date, inspector, overall_status, docstatus
		from `tabTrip Pre Inspection`
		where {conditions}
		order by inspection_date desc, name desc
		""",
		values,
		as_dict=True,
	)
	if not inspections:
		return []

	names = [d.name for d in inspections]

	failed_items_by_parent = _grouped_failed_items(names)
	tyre_rows_by_parent = _grouped_tyre_pressure_rows(names)

	data = []
	for insp in inspections:
		failed_items = failed_items_by_parent.get(insp.name, [])
		tyre_rows = tyre_rows_by_parent.get(insp.name, [])
		issues = [
			f"{row.position} ({row.pressure_psi} PSI, {row.status})"
			for row in tyre_rows
			if row.status in ("Low", "High")
		]

		data.append(
			{
				"name": insp.name,
				"truck": insp.truck,
				"inspection_date": insp.inspection_date,
				"inspector": insp.inspector,
				"overall_status": insp.overall_status,
				"failed_items": ", ".join(failed_items),
				"tyre_pressure_checked": _("Yes") if tyre_rows else _("No"),
				"tyres_recorded": len(tyre_rows),
				"tyre_pressure_issues": ", ".join(issues),
				"docstatus_label": {0: _("Draft"), 1: _("Submitted"), 2: _("Cancelled")}.get(
					insp.docstatus, ""
				),
			}
		)
	return data


def _build_conditions(filters):
	conditions = ["1=1"]
	values = {}

	if filters.get("company"):
		conditions.append("truck in (select name from `tabTruck` where company = %(company)s)")
		values["company"] = filters.company
	if filters.get("truck"):
		conditions.append("truck = %(truck)s")
		values["truck"] = filters.truck
	if filters.get("overall_status"):
		conditions.append("overall_status = %(overall_status)s")
		values["overall_status"] = filters.overall_status
	if filters.get("only_submitted"):
		conditions.append("docstatus = 1")
	if filters.get("from_date"):
		conditions.append("inspection_date >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("inspection_date <= %(to_date)s")
		values["to_date"] = filters.to_date

	return " and ".join(conditions), values


def _grouped_failed_items(parent_names):
	rows = frappe.db.sql(
		"""
		select parent, inspection_item
		from `tabTrip Pre Inspection Item`
		where parent in %(parents)s and status = 'Not OK'
		order by idx
		""",
		{"parents": parent_names},
		as_dict=True,
	)
	grouped = {}
	for row in rows:
		grouped.setdefault(row.parent, []).append(row.inspection_item)
	return grouped


def _grouped_tyre_pressure_rows(parent_names):
	rows = frappe.db.sql(
		"""
		select parent, position, pressure_psi, status
		from `tabTrip Pre Inspection Tyre Pressure`
		where parent in %(parents)s
		order by idx
		""",
		{"parents": parent_names},
		as_dict=True,
	)
	grouped = {}
	for row in rows:
		grouped.setdefault(row.parent, []).append(row)
	return grouped
