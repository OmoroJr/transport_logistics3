# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Optional Safaricom Daraja B2C integration for paying drivers directly to
their M-Pesa number. This is entirely optional — most operators will just
record payments manually (payment_method = M-Pesa, and type in the
transaction code after paying via the M-Pesa app). This module exists for
those who have:

  1. A Safaricom B2C shortcode with Go-Live / production approval for B2C
     (sandbox works for testing without that).
  2. A Security Credential generated via the Daraja portal (encrypting your
     initiator password with Safaricom's public certificate).
  3. Consumer Key/Secret for an app with B2C API access.
  4. A publicly reachable HTTPS Result URL and Queue Timeout URL pointing at
     this site (the two whitelisted, guest-accessible endpoints below).

Configure all of the above in Transport Logistics Settings before enabling
"Enable Live M-Pesa B2C Disbursement".
"""

import json

import frappe
from frappe.utils import flt

SANDBOX_BASE = "https://sandbox.safaricom.co.ke"
PRODUCTION_BASE = "https://api.safaricom.co.ke"


def _base_url(settings):
	return PRODUCTION_BASE if settings.mpesa_environment == "Production" else SANDBOX_BASE


def _get_access_token(settings):
	import requests

	base_url = _base_url(settings)
	consumer_key = settings.mpesa_consumer_key
	consumer_secret = settings.get_password("mpesa_consumer_secret")

	response = requests.get(
		f"{base_url}/oauth/v1/generate?grant_type=client_credentials",
		auth=(consumer_key, consumer_secret),
		timeout=30,
	)
	response.raise_for_status()
	return response.json().get("access_token")


@frappe.whitelist()
def initiate_b2c_payment(payment_name):
	"""Triggers a live Safaricom Daraja B2C payment request for a Driver
	Mileage Payment. Sets payment_status to 'Processing' — the record is
	only marked 'Paid' (and submitted) once b2c_result_callback receives
	Safaricom's confirmation."""
	import requests

	settings = frappe.get_cached_doc("Transport Logistics Settings")
	if not settings.enable_mpesa_b2c:
		frappe.throw(
			"M-Pesa B2C integration is not enabled. Turn it on in Transport "
			"Logistics Settings, or just record this payment manually with a "
			"transaction code."
		)

	doc = frappe.get_doc("Driver Mileage Payment", payment_name)
	if doc.payment_method != "M-Pesa":
		frappe.throw("Payment Method must be M-Pesa to use this.")
	if not doc.mpesa_phone_number:
		frappe.throw("Driver's M-Pesa phone number is required.")
	if not doc.total_amount or flt(doc.total_amount) <= 0:
		frappe.throw("Total Amount must be greater than zero.")

	access_token = _get_access_token(settings)
	base_url = _base_url(settings)

	payload = {
		"InitiatorName": settings.mpesa_initiator_name,
		"SecurityCredential": settings.get_password("mpesa_security_credential"),
		"CommandID": "BusinessPayment",
		"Amount": int(flt(doc.total_amount)),
		"PartyA": settings.mpesa_shortcode,
		"PartyB": doc.mpesa_phone_number,
		"Remarks": f"Mileage payment {doc.name} - Driver {doc.driver}",
		"QueueTimeOutURL": settings.mpesa_queue_timeout_url,
		"ResultURL": settings.mpesa_result_url,
		"Occasion": doc.name,
	}

	response = requests.post(
		f"{base_url}/mpesa/b2c/v1/paymentrequest",
		json=payload,
		headers={"Authorization": f"Bearer {access_token}"},
		timeout=30,
	)

	try:
		result = response.json()
	except ValueError:
		frappe.throw(f"Unexpected response from Safaricom: {response.text}")

	if response.status_code == 200 and str(result.get("ResponseCode")) == "0":
		doc.db_set("mpesa_conversation_id", result.get("ConversationID"), update_modified=False)
		doc.db_set(
			"mpesa_originator_conversation_id",
			result.get("OriginatorConversationID"),
			update_modified=False,
		)
		doc.db_set("payment_status", "Processing", update_modified=False)
		frappe.msgprint("M-Pesa B2C payment request submitted. Awaiting confirmation callback.")
	else:
		frappe.throw(f"M-Pesa B2C request failed: {result.get('errorMessage') or result}")

	return result


@frappe.whitelist(allow_guest=True)
def b2c_result_callback():
	"""Safaricom posts the outcome of a B2C payment request here. Set this as
	your Result URL in Transport Logistics Settings:
	https://your-site/api/method/transport_logistics.transport_logistics.mpesa.b2c_result_callback
	"""
	data = frappe.request.get_json(silent=True) or {}
	frappe.log_error(json.dumps(data), "M-Pesa B2C Result Callback")

	result = data.get("Result", {})
	conversation_id = result.get("ConversationID")
	result_code = result.get("ResultCode")

	payment_name = frappe.db.get_value(
		"Driver Mileage Payment", {"mpesa_conversation_id": conversation_id}, "name"
	)
	if not payment_name:
		return {"ResultCode": 0, "ResultDesc": "Accepted"}

	doc = frappe.get_doc("Driver Mileage Payment", payment_name)

	if str(result_code) == "0":
		transaction_id = None
		for param in result.get("ResultParameters", {}).get("ResultParameter", []):
			if param.get("Key") == "TransactionReceipt":
				transaction_id = param.get("Value")

		doc.db_set(
			"mpesa_transaction_code", transaction_id or conversation_id, update_modified=False
		)
		doc.db_set("payment_status", "Paid", update_modified=False)
		doc.db_set("payment_date", frappe.utils.today(), update_modified=False)

		if doc.docstatus == 0:
			doc.reload()
			doc.submit()
	else:
		doc.db_set("payment_status", "Failed", update_modified=False)

	return {"ResultCode": 0, "ResultDesc": "Accepted"}


@frappe.whitelist(allow_guest=True)
def b2c_timeout_callback():
	"""Safaricom posts here if the B2C request itself times out (distinct from
	a declined payment). Set this as your Queue Timeout URL."""
	data = frappe.request.get_json(silent=True) or {}
	frappe.log_error(json.dumps(data), "M-Pesa B2C Timeout Callback")

	result = data.get("Result", {})
	conversation_id = result.get("ConversationID")
	payment_name = frappe.db.get_value(
		"Driver Mileage Payment", {"mpesa_conversation_id": conversation_id}, "name"
	)
	if payment_name:
		frappe.db.set_value("Driver Mileage Payment", payment_name, "payment_status", "Failed")

	return {"ResultCode": 0, "ResultDesc": "Accepted"}
