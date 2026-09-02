# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Payroll-style register of Driver Mileage Payment records: who was paid, for
which period, by which method, and whether the M-Pesa / bank reference has
settled. Date filters apply to the payment's covered period (from_date /
to_date fields on the doctype), not the payment_date, so a manager can see
"which periods have and haven't been paid out yet".
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
		{"label": _("Payment"), "fieldname": "name", "fieldtype": "Link", "options": "Driver Mileage Payment", "width": 130},
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Link", "options": "Employee", "width": 100},
		{"label": _("Driver Name"), "fieldname": "driver_name", "fieldtype": "Data", "width": 130},
		{"label": _("Truck"), "fieldname": "truck", "fieldtype": "Link", "options": "Truck", "width": 100},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 120},
		{"label": _("Period From"), "fieldname": "from_date", "fieldtype": "Date", "width": 95},
		{"label": _("Period To"), "fieldname": "to_date", "fieldtype": "Date", "width": 95},
		{"label": _("Trips"), "fieldname": "number_of_trips", "fieldtype": "Int", "width": 70},
		{"label": _("Computed Amount"), "fieldname": "computed_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Other Allowance"), "fieldname": "other_allowance", "fieldtype": "Currency", "width": 110},
		{"label": _("Total Amount"), "fieldname": "total_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Payment Method"), "fieldname": "payment_method", "fieldtype": "Data", "width": 110},
		{"label": _("Payment Status"), "fieldname": "payment_status", "fieldtype": "Data", "width": 100},
		{"label": _("Payment Date"), "fieldname": "payment_date", "fieldtype": "Date", "width": 95},
		{"label": _("M-Pesa Code"), "fieldname": "mpesa_transaction_code", "fieldtype": "Data", "width": 110},
		{"label": _("Bank Reference"), "fieldname": "bank_reference", "fieldtype": "Data", "width": 110},
		{"label": _("Status"), "fieldname": "docstatus_label", "fieldtype": "Data", "width": 90},
	]


def get_data(filters):
	conditions, values = get_conditions(filters)

	rows = frappe.db.sql(
		f"""
		select
			dmp.name, dmp.driver, emp.employee_name as driver_name,
			dmp.truck, dmp.company, dmp.from_date, dmp.to_date,
			dmp.computed_amount, dmp.other_allowance, dmp.total_amount,
			dmp.payment_method, dmp.payment_status, dmp.payment_date,
			dmp.mpesa_transaction_code, dmp.bank_reference, dmp.docstatus,
			(select sum(number_of_trips) from `tabDriver Mileage Payment Route` r
				where r.parent = dmp.name) as number_of_trips
		from `tabDriver Mileage Payment` dmp
		left join `tabEmployee` emp on emp.name = dmp.driver
		where 1=1 {conditions}
		order by dmp.from_date desc, dmp.name desc
		""",
		values,
		as_dict=True,
	)

	docstatus_label = {0: _("Draft"), 1: _("Submitted"), 2: _("Cancelled")}
	for row in rows:
		row["docstatus_label"] = docstatus_label.get(row.docstatus)

	return rows


def get_conditions(filters):
	conditions = ""
	values = {}

	if not filters.get("include_unsubmitted"):
		conditions += " and dmp.docstatus = 1"

	if filters.get("from_date"):
		conditions += " and dmp.to_date >= %(from_date)s"
		values["from_date"] = filters.get("from_date")
	if filters.get("to_date"):
		conditions += " and dmp.from_date <= %(to_date)s"
		values["to_date"] = filters.get("to_date")
	if filters.get("company"):
		conditions += " and dmp.company = %(company)s"
		values["company"] = filters.get("company")
	if filters.get("driver"):
		conditions += " and dmp.driver = %(driver)s"
		values["driver"] = filters.get("driver")
	if filters.get("truck"):
		conditions += " and dmp.truck = %(truck)s"
		values["truck"] = filters.get("truck")
	if filters.get("payment_method"):
		conditions += " and dmp.payment_method = %(payment_method)s"
		values["payment_method"] = filters.get("payment_method")
	if filters.get("payment_status"):
		conditions += " and dmp.payment_status = %(payment_status)s"
		values["payment_status"] = filters.get("payment_status")

	return conditions, values


def get_chart(data):
	if not data:
		return None

	driver_totals = {}
	for row in data:
		key = row.driver_name or row.driver
		driver_totals[key] = driver_totals.get(key, 0) + flt(row.total_amount)

	top_drivers = sorted(driver_totals.items(), key=lambda x: x[1], reverse=True)[:15]

	return {
		"data": {
			"labels": [d[0] for d in top_drivers],
			"datasets": [
				{"name": "Total Amount", "values": [flt(d[1], 2) for d in top_drivers]},
			],
		},
		"type": "bar",
		"colors": ["#16A085"],
	}


def get_summary(data):
	if not data:
		return []

	total_amount = sum(flt(r.total_amount) for r in data)
	unpaid_rows = [r for r in data if r.payment_status == "Unpaid"]
	unpaid_amount = sum(flt(r.total_amount) for r in unpaid_rows)
	failed_rows = [r for r in data if r.payment_status == "Failed"]

	return [
		{"label": _("Total Payments"), "value": len(data), "datatype": "Int"},
		{"label": _("Total Amount"), "value": flt(total_amount, 2), "datatype": "Currency"},
		{
			"label": _("Unpaid Amount"),
			"value": flt(unpaid_amount, 2),
			"datatype": "Currency",
			"indicator": "Red" if unpaid_rows else "Green",
		},
		{"label": _("Unpaid Count"), "value": len(unpaid_rows), "datatype": "Int"},
		{
			"label": _("Failed Payments"),
			"value": len(failed_rows),
			"datatype": "Int",
			"indicator": "Red" if failed_rows else "Green",
		},
	]
