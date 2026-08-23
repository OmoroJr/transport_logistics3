# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
On-Time / Late delivery tracking, based on comparing each offloaded Truck
Trip's actual offload_datetime against its expected_delivery_datetime (a
field added specifically to support this report — see truck_trip.json).

Both fields are optional, so a trip only counts as "On-Time" or "Late" if
someone actually recorded a promised delivery time for it. A trip with no
Expected Delivery Date & Time set shows as "Not Tracked" — it is NOT
counted in the On-Time % calculation either way, since there's no promise
to judge it against. Silently excluding it from the denominator (rather
than defaulting it to On-Time, which would flatter the numbers) is the
honest way to handle partially-adopted data.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, time_diff_in_hours


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	summary = get_summary(data)
	return columns, data, None, None, summary


def get_columns():
	return [
		{"label": _("Trip"), "fieldname": "name", "fieldtype": "Link", "options": "Truck Trip", "width": 110},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 110},
		{"label": _("Truck"), "fieldname": "truck", "fieldtype": "Link", "options": "Truck", "width": 100},
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Link", "options": "Employee", "width": 100},
		{"label": _("Route"), "fieldname": "route", "fieldtype": "Link", "options": "Route", "width": 100},
		{"label": _("Destination"), "fieldname": "destination", "fieldtype": "Data", "width": 110},
		{"label": _("Expected Delivery"), "fieldname": "expected_delivery_datetime", "fieldtype": "Datetime", "width": 150},
		{"label": _("Actual Delivery"), "fieldname": "offload_datetime", "fieldtype": "Datetime", "width": 150},
		{"label": _("Delay (Hours)"), "fieldname": "delay_hours", "fieldtype": "Float", "width": 110},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Reason for Delay"), "fieldname": "delivery_delay_reason", "fieldtype": "Data", "width": 200},
	]


def get_data(filters):
	conditions = ["t.offload_status = 'Offloaded'", "t.offload_datetime is not null"]
	values = {}

	if filters.get("from_date"):
		conditions.append("date(t.offload_datetime) >= %(from_date)s")
		values["from_date"] = filters.get("from_date")
	if filters.get("to_date"):
		conditions.append("date(t.offload_datetime) <= %(to_date)s")
		values["to_date"] = filters.get("to_date")
	for field in ("truck", "driver", "route", "customer", "company"):
		if filters.get(field):
			conditions.append(f"t.{field} = %({field})s")
			values[field] = filters.get(field)

	where_clause = " and ".join(conditions)

	trips = frappe.db.sql(
		f"""
		select
			t.name, t.customer, t.truck, t.driver, t.route, t.destination,
			t.expected_delivery_datetime, t.offload_datetime, t.delivery_delay_reason
		from `tabTruck Trip` t
		where {where_clause}
		order by t.offload_datetime desc
		""",
		values,
		as_dict=True,
	)

	data = []
	for t in trips:
		if not t.expected_delivery_datetime:
			status = "Not Tracked"
			delay_hours = None
		else:
			delay_hours = round(time_diff_in_hours(t.offload_datetime, t.expected_delivery_datetime), 1)
			status = "On-Time" if delay_hours <= 0 else "Late"

		if filters.get("status") and status != filters.get("status"):
			continue

		data.append({
			"name": t.name,
			"customer": t.customer,
			"truck": t.truck,
			"driver": t.driver,
			"route": t.route,
			"destination": t.destination,
			"expected_delivery_datetime": t.expected_delivery_datetime,
			"offload_datetime": t.offload_datetime,
			"delay_hours": delay_hours,
			"status": status,
			"delivery_delay_reason": t.delivery_delay_reason,
		})

	return data


def get_summary(data):
	if not data:
		return []

	tracked = [r for r in data if r["status"] != "Not Tracked"]
	on_time = [r for r in tracked if r["status"] == "On-Time"]
	late = [r for r in tracked if r["status"] == "Late"]

	return [
		{"label": _("Total Deliveries"), "value": len(data), "datatype": "Int"},
		{"label": _("Tracked (has Expected Delivery)"), "value": len(tracked), "datatype": "Int"},
		{"label": _("On-Time"), "value": len(on_time), "datatype": "Int"},
		{"label": _("Late"), "value": len(late), "datatype": "Int"},
		{
			"label": _("On-Time %  (of tracked deliveries)"),
			"value": flt(len(on_time) / len(tracked) * 100, 1) if tracked else 0,
			"datatype": "Percent",
		},
	]
