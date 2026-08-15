# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class DriverMileagePayment(Document):
	def validate(self):
		compute_amounts(self)

	def on_submit(self):
		if not self.payment_date:
			self.db_set("payment_date", frappe.utils.today(), update_modified=False)
		# Cash / Bank Transfer are assumed settled at the point of submission.
		# M-Pesa is only marked Paid once the B2C callback confirms it, unless
		# the user is just logging a payment they already made manually
		# (in which case they'll have typed in a transaction code themselves).
		if self.payment_method != "M-Pesa" and self.payment_status == "Unpaid":
			self.db_set("payment_status", "Paid", update_modified=False)
		elif self.payment_method == "M-Pesa" and self.mpesa_transaction_code and self.payment_status == "Unpaid":
			self.db_set("payment_status", "Paid", update_modified=False)


def compute_amounts(doc, method=None):
	total = 0.0
	for row in doc.routes:
		row.amount = flt(row.rate) * flt(row.number_of_trips)
		total += row.amount
	doc.computed_amount = total
	doc.total_amount = flt(doc.computed_amount) + flt(doc.other_allowance)


@frappe.whitelist()
def get_route_trip_counts(driver, truck=None, from_date=None, to_date=None):
	"""Groups the driver's Completed Truck Trips in the period by Route and
	counts trips per route. Powers the 'Fetch Trips for Period' button —
	only trips with a Route set are counted, since ad-hoc trips without a
	standard route have no per-destination rate to look up."""
	conditions = ""
	values = {"driver": driver}
	if truck:
		conditions += " and truck = %(truck)s"
		values["truck"] = truck
	if from_date:
		conditions += " and trip_date >= %(from_date)s"
		values["from_date"] = from_date
	if to_date:
		conditions += " and trip_date <= %(to_date)s"
		values["to_date"] = to_date

	rows = frappe.db.sql(
		f"""
		select route, count(*) as trip_count
		from `tabTruck Trip`
		where driver = %(driver)s and status = 'Completed'
		and route is not null and route != ''
		{conditions}
		group by route
		""",
		values,
		as_dict=True,
	)

	result = []
	for row in rows:
		rate = frappe.db.get_value("Route", row.route, "driver_rate") or 0
		result.append({
			"route": row.route,
			"number_of_trips": row.trip_count,
			"rate": rate,
			"amount": flt(rate) * row.trip_count,
		})
	return result
