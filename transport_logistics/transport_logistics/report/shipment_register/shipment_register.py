# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Register of all Shipment records with a profitability view (billable vs
company cost, drawn from the child Shipment Charge table's totals). No
explicit booking-date field exists on Shipment, so the date range filters
on `creation` instead.
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
		{"label": _("Shipment"), "fieldname": "name", "fieldtype": "Link", "options": "Shipment", "width": 130},
		{"label": _("Client"), "fieldname": "client", "fieldtype": "Link", "options": "Customer", "width": 130},
		{"label": _("Type"), "fieldname": "shipment_type", "fieldtype": "Data", "width": 80},
		{"label": _("Mode"), "fieldname": "mode_of_transport", "fieldtype": "Data", "width": 70},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 130},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 120},
		{"label": _("Assigned Agent"), "fieldname": "assigned_agent", "fieldtype": "Link", "options": "Employee", "width": 120},
		{"label": _("Assigned Truck"), "fieldname": "assigned_truck", "fieldtype": "Link", "options": "Truck", "width": 100},
		{"label": _("Bill of Lading"), "fieldname": "bill_of_lading_no", "fieldtype": "Data", "width": 120},
		{"label": _("Vessel/Flight"), "fieldname": "vessel_or_flight", "fieldtype": "Data", "width": 100},
		{"label": _("Container No"), "fieldname": "container_no", "fieldtype": "Data", "width": 110},
		{"label": _("Port of Loading"), "fieldname": "port_of_loading", "fieldtype": "Data", "width": 110},
		{"label": _("Port of Discharge"), "fieldname": "port_of_discharge", "fieldtype": "Data", "width": 120},
		{"label": _("ETA"), "fieldname": "eta", "fieldtype": "Date", "width": 95},
		{"label": _("ATA"), "fieldname": "ata", "fieldtype": "Date", "width": 95},
		{"label": _("Packages"), "fieldname": "number_of_packages", "fieldtype": "Int", "width": 85},
		{"label": _("Weight (Kg)"), "fieldname": "weight_kg", "fieldtype": "Float", "width": 95},
		{"label": _("CBM"), "fieldname": "cbm", "fieldtype": "Float", "width": 80},
		{"label": _("Total Billable"), "fieldname": "total_billable", "fieldtype": "Currency", "width": 110},
		{"label": _("Total Company Cost"), "fieldname": "total_company_cost", "fieldtype": "Currency", "width": 120},
		{"label": _("Profit"), "fieldname": "profit", "fieldtype": "Currency", "width": 100},
		{"label": _("Margin %"), "fieldname": "margin_percent", "fieldtype": "Percent", "width": 90},
		{"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 120},
	]


def get_data(filters):
	conditions, values = get_conditions(filters)

	rows = frappe.db.sql(
		f"""
		select
			sh.name, sh.client, sh.shipment_type, sh.mode_of_transport, sh.status,
			sh.company, sh.assigned_agent, sh.assigned_truck,
			sh.bill_of_lading_no, sh.vessel_or_flight, sh.container_no,
			sh.port_of_loading, sh.port_of_discharge, sh.eta, sh.ata,
			sh.number_of_packages, sh.weight_kg, sh.cbm,
			sh.total_billable, sh.total_company_cost, sh.sales_invoice
		from `tabShipment` sh
		where 1=1 {conditions}
		order by sh.creation desc
		""",
		values,
		as_dict=True,
	)

	for row in rows:
		row["profit"] = flt(row.total_billable) - flt(row.total_company_cost)
		row["margin_percent"] = (
			(row["profit"] / flt(row.total_billable) * 100) if row.total_billable else 0
		)

	return rows


def get_conditions(filters):
	conditions = ""
	values = {}

	if filters.get("company"):
		conditions += " and sh.company = %(company)s"
		values["company"] = filters.get("company")
	if filters.get("client"):
		conditions += " and sh.client = %(client)s"
		values["client"] = filters.get("client")
	if filters.get("shipment_type"):
		conditions += " and sh.shipment_type = %(shipment_type)s"
		values["shipment_type"] = filters.get("shipment_type")
	if filters.get("mode_of_transport"):
		conditions += " and sh.mode_of_transport = %(mode_of_transport)s"
		values["mode_of_transport"] = filters.get("mode_of_transport")
	if filters.get("status"):
		conditions += " and sh.status = %(status)s"
		values["status"] = filters.get("status")
	if filters.get("assigned_agent"):
		conditions += " and sh.assigned_agent = %(assigned_agent)s"
		values["assigned_agent"] = filters.get("assigned_agent")
	if filters.get("assigned_truck"):
		conditions += " and sh.assigned_truck = %(assigned_truck)s"
		values["assigned_truck"] = filters.get("assigned_truck")
	if filters.get("from_date"):
		conditions += " and date(sh.creation) >= %(from_date)s"
		values["from_date"] = filters.get("from_date")
	if filters.get("to_date"):
		conditions += " and date(sh.creation) <= %(to_date)s"
		values["to_date"] = filters.get("to_date")
	if filters.get("only_unbilled"):
		conditions += " and (sh.sales_invoice is null or sh.sales_invoice = '')"

	return conditions, values


def get_chart(data):
	if not data:
		return None

	type_profit = {}
	for row in data:
		key = row.shipment_type or _("Unspecified")
		type_profit[key] = type_profit.get(key, 0) + flt(row.profit)

	return {
		"data": {
			"labels": list(type_profit.keys()),
			"datasets": [
				{"name": "Profit", "values": [flt(v, 2) for v in type_profit.values()]},
			],
		},
		"type": "bar",
		"colors": ["#28B463"],
	}


def get_summary(data):
	if not data:
		return []

	total_billable = sum(flt(r.total_billable) for r in data)
	total_cost = sum(flt(r.total_company_cost) for r in data)
	total_profit = sum(flt(r.profit) for r in data)
	avg_margin = (total_profit / total_billable * 100) if total_billable else 0
	unbilled = [r for r in data if not r.sales_invoice]

	return [
		{"label": _("Total Shipments"), "value": len(data), "datatype": "Int"},
		{"label": _("Total Billable"), "value": flt(total_billable, 2), "datatype": "Currency"},
		{"label": _("Total Company Cost"), "value": flt(total_cost, 2), "datatype": "Currency"},
		{"label": _("Total Profit"), "value": flt(total_profit, 2), "datatype": "Currency"},
		{"label": _("Avg Margin %"), "value": flt(avg_margin, 1), "datatype": "Percent"},
		{
			"label": _("Unbilled Shipments"),
			"value": len(unbilled),
			"datatype": "Int",
			"indicator": "Red" if unbilled else "Green",
		},
	]
