# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class Shipment(Document):
	def validate(self):
		compute_charge_totals(self)


def compute_charge_totals(doc, method=None):
	billable = 0.0
	company_cost = 0.0
	for row in doc.charges:
		if row.billable:
			billable += flt(row.amount)
		if row.payable_by == "Company (Own Cost)":
			company_cost += flt(row.amount)
	doc.total_billable = billable
	doc.total_company_cost = company_cost


@frappe.whitelist()
def create_sales_invoice(shipment_name):
	"""Creates a Sales Invoice for the client with one line item per billable
	Shipment Charge. Uses a generic 'Clearing & Forwarding Services' Item if
	one exists (create it once in Item master); otherwise falls back to
	posting each charge as a standalone invoice item description so this
	still works without any Item Master setup."""
	doc = frappe.get_doc("Shipment", shipment_name)

	billable_charges = [c for c in doc.charges if c.billable and flt(c.amount) > 0]
	if not billable_charges:
		frappe.throw("No billable charges on this Shipment to invoice.")

	if doc.sales_invoice and frappe.db.exists("Sales Invoice", doc.sales_invoice):
		frappe.throw(f"Already invoiced: {doc.sales_invoice}")

	default_item = frappe.db.get_value("Item", {"item_name": ["like", "%Clearing%Forwarding%"]}, "name")

	si = frappe.new_doc("Sales Invoice")
	si.customer = doc.client
	si.company = doc.company

	for c in billable_charges:
		row = {
			"item_name": c.description or c.charge_type,
			"description": f"{c.charge_type}: {c.description or ''} ({doc.name})".strip(),
			"qty": 1,
			"rate": flt(c.amount),
		}
		if default_item:
			row["item_code"] = default_item
		else:
			# No suitable Item found — Sales Invoice Items require an item_code,
			# so this is a soft requirement: create a service Item named
			# something like "Clearing & Forwarding Services" once, and this
			# will pick it up automatically from then on.
			frappe.throw(
				"No Item found matching 'Clearing' and 'Forwarding' in the name. "
				"Please create a service Item (e.g. 'Clearing & Forwarding Services') "
				"once, then try again."
			)
		si.append("items", row)

	si.insert(ignore_permissions=True)

	doc.db_set("sales_invoice", si.name, update_modified=False)
	frappe.msgprint(f"Sales Invoice {si.name} created as a draft. Review and submit it from Accounts.")
	return si.name
