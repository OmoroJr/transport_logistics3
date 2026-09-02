# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Reconciles each Fuel Tank's book stock (Stock Ledger Entry qty_after_transaction
for the tank's fuel_item + warehouse) against what Bulk Fuel Purchase (in) and
Fuel Dispensing (out) records say should have happened over the selected
period. A non-zero variance flags leakage, theft, evaporation, or a
transaction that bypassed the Bulk Fuel Purchase / Fuel Dispensing doctypes.
"""

import frappe
from frappe import _
from frappe.utils import flt, add_days, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("Please set both From Date and To Date"))

	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	summary = get_summary(data)
	return columns, data, None, chart, summary


def get_columns():
	return [
		{"label": _("Tank"), "fieldname": "name", "fieldtype": "Link", "options": "Fuel Tank", "width": 110},
		{"label": _("Fuel Type"), "fieldname": "fuel_type", "fieldtype": "Data", "width": 90},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 130},
		{"label": _("Capacity (L)"), "fieldname": "capacity_litres", "fieldtype": "Float", "width": 100},
		{"label": _("Opening Balance (L)"), "fieldname": "opening_qty", "fieldtype": "Float", "width": 130},
		{"label": _("Purchased (L)"), "fieldname": "purchased_litres", "fieldtype": "Float", "width": 110},
		{"label": _("Dispensed (L)"), "fieldname": "dispensed_litres", "fieldtype": "Float", "width": 110},
		{"label": _("Expected Closing (L)"), "fieldname": "expected_closing_qty", "fieldtype": "Float", "width": 140},
		{"label": _("Actual Closing (L)"), "fieldname": "actual_closing_qty", "fieldtype": "Float", "width": 130},
		{"label": _("Variance (L)"), "fieldname": "variance_litres", "fieldtype": "Float", "width": 100},
		{"label": _("Variance %"), "fieldname": "variance_percent", "fieldtype": "Percent", "width": 90},
	]


def get_data(filters):
	conditions, values = get_conditions(filters)

	tanks = frappe.db.sql(
		f"""
		select name, fuel_type, warehouse, fuel_item, capacity_litres
		from `tabFuel Tank`
		where 1=1 {conditions}
		order by name
		""",
		values,
		as_dict=True,
	)

	from_date = getdate(filters.get("from_date"))
	to_date = getdate(filters.get("to_date"))

	rows = []
	for tank in tanks:
		if not tank.fuel_item or not tank.warehouse:
			continue

		opening_qty = get_stock_balance_before(tank.fuel_item, tank.warehouse, from_date)
		actual_closing_qty = get_stock_balance_upto(tank.fuel_item, tank.warehouse, to_date)

		purchased_litres = flt(frappe.db.sql(
			"""
			select sum(qty_litres) from `tabBulk Fuel Purchase`
			where tank = %(tank)s and docstatus = 1
				and date between %(from_date)s and %(to_date)s
			""",
			{"tank": tank.name, "from_date": from_date, "to_date": to_date},
		)[0][0] or 0)

		dispensed_litres = flt(frappe.db.sql(
			"""
			select sum(qty_litres) from `tabFuel Dispensing`
			where tank = %(tank)s and docstatus = 1
				and date between %(from_date)s and %(to_date)s
			""",
			{"tank": tank.name, "from_date": from_date, "to_date": to_date},
		)[0][0] or 0)

		expected_closing_qty = opening_qty + purchased_litres - dispensed_litres
		variance_litres = actual_closing_qty - expected_closing_qty
		variance_percent = (
			(variance_litres / expected_closing_qty * 100) if expected_closing_qty else 0
		)

		rows.append({
			"name": tank.name,
			"fuel_type": tank.fuel_type,
			"warehouse": tank.warehouse,
			"capacity_litres": tank.capacity_litres,
			"opening_qty": opening_qty,
			"purchased_litres": purchased_litres,
			"dispensed_litres": dispensed_litres,
			"expected_closing_qty": expected_closing_qty,
			"actual_closing_qty": actual_closing_qty,
			"variance_litres": variance_litres,
			"variance_percent": variance_percent,
		})

	if filters.get("only_variance"):
		rows = [r for r in rows if abs(r["variance_litres"]) > 0.01]

	return rows


def get_stock_balance_before(item_code, warehouse, date):
	"""Book stock balance as of the end of the day before `date`."""
	return get_stock_balance_upto(item_code, warehouse, add_days(date, -1))


def get_stock_balance_upto(item_code, warehouse, date):
	value = frappe.db.sql(
		"""
		select qty_after_transaction from `tabStock Ledger Entry`
		where item_code = %(item_code)s and warehouse = %(warehouse)s
			and posting_date <= %(date)s and is_cancelled = 0
		order by posting_date desc, posting_time desc, creation desc
		limit 1
		""",
		{"item_code": item_code, "warehouse": warehouse, "date": date},
	)
	return flt(value[0][0]) if value else 0


def get_conditions(filters):
	conditions = ""
	values = {}

	if filters.get("company"):
		conditions += " and company = %(company)s"
		values["company"] = filters.get("company")
	if filters.get("tank"):
		conditions += " and name = %(tank)s"
		values["tank"] = filters.get("tank")

	return conditions, values


def get_chart(data):
	if not data:
		return None

	return {
		"data": {
			"labels": [row["name"] for row in data],
			"datasets": [
				{"name": "Variance (L)", "values": [flt(row["variance_litres"], 1) for row in data]},
			],
		},
		"type": "bar",
		"colors": ["#E67E22"],
	}


def get_summary(data):
	if not data:
		return []

	total_purchased = sum(flt(r["purchased_litres"]) for r in data)
	total_dispensed = sum(flt(r["dispensed_litres"]) for r in data)
	total_variance = sum(flt(r["variance_litres"]) for r in data)
	flagged = [r for r in data if abs(r["variance_litres"]) > 0.01]

	return [
		{"label": _("Tanks Reviewed"), "value": len(data), "datatype": "Int"},
		{"label": _("Total Purchased (L)"), "value": flt(total_purchased, 1), "datatype": "Float"},
		{"label": _("Total Dispensed (L)"), "value": flt(total_dispensed, 1), "datatype": "Float"},
		{
			"label": _("Total Variance (L)"),
			"value": flt(total_variance, 1),
			"datatype": "Float",
			"indicator": "Red" if abs(total_variance) > 0.01 else "Green",
		},
		{
			"label": _("Tanks With Variance"),
			"value": len(flagged),
			"datatype": "Int",
			"indicator": "Red" if flagged else "Green",
		},
	]
