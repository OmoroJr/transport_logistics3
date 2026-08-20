# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

# Status values, reached in this order, that are worth a customer-facing
# WhatsApp update. Booked/Documents Received/Customs Entry Filed/Customs
# Released are internal processing milestones the client doesn't need a
# message for; these four are the ones they're actually waiting on.
CUSTOMER_NOTIFY_STATUSES = ("Customs Released", "In Transit", "Delivered", "Completed")


class Shipment(Document):
	def validate(self):
		compute_charge_totals(self)
		auto_fill_client_whatsapp_number(self)
		auto_fill_client_email(self)
		notify_client_on_status_change(self)


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


def auto_fill_client_whatsapp_number(doc, method=None):
	"""Fills Client WhatsApp Number from the client's primary Contact mobile
	number, if one is on file and the field is still blank. Only fills in,
	never overwrites — the same "don't clobber a manual correction" rule
	used elsewhere in this app (see e.g. Highway Breakdown's GPS
	auto-fill)."""
	if doc.client_whatsapp_number or not doc.client:
		return

	primary_contact = frappe.db.get_value(
		"Dynamic Link",
		{"link_doctype": "Customer", "link_name": doc.client, "parenttype": "Contact"},
		"parent",
	)
	if not primary_contact:
		return

	mobile = frappe.db.get_value("Contact", primary_contact, "mobile_no")
	if mobile:
		doc.client_whatsapp_number = mobile


def auto_fill_client_email(doc, method=None):
	"""Same idea as auto_fill_client_whatsapp_number() above, but fills
	Client Email from the client's primary Contact email, if on file and
	the field is still blank."""
	if doc.client_email or not doc.client:
		return

	primary_contact = frappe.db.get_value(
		"Dynamic Link",
		{"link_doctype": "Customer", "link_name": doc.client, "parenttype": "Contact"},
		"parent",
	)
	if not primary_contact:
		return

	email = frappe.db.get_value("Contact", primary_contact, "email_id")
	if email:
		doc.client_email = email


def notify_client_on_status_change(doc, method=None):
	"""Sends a WhatsApp update to the client when Status moves to one of the
	milestones in CUSTOMER_NOTIFY_STATUSES. Runs in validate() (before this
	save is committed) so the previous status can still be read from the
	database for comparison — same pattern used for status transitions in
	Truck Trip. Silently does nothing if WhatsApp isn't enabled, customer
	notifications are switched off, or there's no number to send to."""
	if doc.status not in CUSTOMER_NOTIFY_STATUSES:
		return

	if not doc.is_new():
		previous_status = frappe.db.get_value("Shipment", doc.name, "status")
		if previous_status == doc.status:
			return

	settings = frappe.get_cached_doc("Transport Logistics Settings")

	status_messages = {
		"Customs Released": f"Good news — your shipment {doc.name} has cleared customs and is being prepared for onward transport.",
		"In Transit": f"Your shipment {doc.name} is now in transit" + (f" to {doc.port_of_discharge}." if doc.port_of_discharge else "."),
		"Delivered": f"Your shipment {doc.name} has been delivered. Thank you for shipping with us.",
		"Completed": f"Your shipment {doc.name} is now fully completed and closed out.",
	}
	message = status_messages.get(doc.status, f"Update on your shipment {doc.name}: status is now {doc.status}.")

	if doc.client_whatsapp_number and settings.enable_whatsapp and settings.whatsapp_notify_customer:
		from transport_logistics.transport_logistics.whatsapp import send_whatsapp_message

		send_whatsapp_message(
			doc.client_whatsapp_number,
			message,
			reference_doctype="Shipment",
			reference_name=doc.name,
			settings=settings,
		)

	if doc.client_email and settings.enable_email_alerts and settings.email_notify_customer:
		from transport_logistics.transport_logistics.email_alerts import send_email_alert

		send_email_alert(
			doc.client_email,
			f"Shipment {doc.name} update: {doc.status}",
			message,
			reference_doctype="Shipment",
			reference_name=doc.name,
			settings=settings,
		)

	if doc.client_whatsapp_number and settings.enable_sms and settings.sms_notify_customer:
		from transport_logistics.transport_logistics.sms import send_sms

		send_sms(
			doc.client_whatsapp_number,
			message,
			reference_doctype="Shipment",
			reference_name=doc.name,
			settings=settings,
		)


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
