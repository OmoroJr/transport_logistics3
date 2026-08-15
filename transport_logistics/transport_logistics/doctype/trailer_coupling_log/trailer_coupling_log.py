# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class TrailerCouplingLog(Document):
	def validate(self):
		validate_coupling(self)


def validate_coupling(doc, method=None):
	if doc.action == "Coupled":
		current_truck_of_trailer = frappe.db.get_value("Trailer", doc.trailer, "current_truck")
		if current_truck_of_trailer and current_truck_of_trailer != doc.truck:
			frappe.throw(
				f"Trailer {doc.trailer} is already coupled to Truck {current_truck_of_trailer}. "
				"Record a Decoupled entry first."
			)

		current_trailer_of_truck = frappe.db.get_value("Truck", doc.truck, "current_trailer")
		if current_trailer_of_truck and current_trailer_of_truck != doc.trailer:
			frappe.throw(
				f"Truck {doc.truck} already has Trailer {current_trailer_of_truck} coupled. "
				"A truck can only pull one trailer at a time — decouple it first before "
				f"coupling {doc.trailer}."
			)
	elif doc.action == "Decoupled":
		current = frappe.db.get_value("Trailer", doc.trailer, "current_truck")
		if current and current != doc.truck:
			frappe.throw(
				f"Trailer {doc.trailer} is currently coupled to Truck {current}, not {doc.truck}."
			)


def apply_coupling(doc, method=None):
	trailer = frappe.get_doc("Trailer", doc.trailer)

	if doc.action == "Coupled":
		trailer.current_truck = doc.truck
		trailer.save(ignore_permissions=True)
		frappe.db.set_value("Truck", doc.truck, "current_trailer", doc.trailer)

	elif doc.action == "Decoupled":
		trailer.current_truck = None
		trailer.save(ignore_permissions=True)
		linked_trailer = frappe.db.get_value("Truck", doc.truck, "current_trailer")
		if linked_trailer == doc.trailer:
			frappe.db.set_value("Truck", doc.truck, "current_trailer", None)


def reverse_coupling(doc, method=None):
	frappe.msgprint(
		f"Trailer Coupling Log {doc.name} cancelled. Please verify Trailer {doc.trailer} "
		"and Truck {doc.truck} current coupling status manually.",
		alert=True,
	)
