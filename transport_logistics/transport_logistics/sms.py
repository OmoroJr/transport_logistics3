# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Optional SMS integration via Africa's Talking (africastalking.com) - the
most widely used bulk SMS gateway for Kenya/East Africa, and the only
provider wired up today (see sms_provider on Transport Logistics Settings;
selecting anything else fails clearly rather than silently no-op'ing). Used
across the app for the same three kinds of messages as whatsapp.py, each
independently toggled in Transport Logistics Settings > SMS Alerts:

  1. Internal alerts   - breakdowns, high-severity accidents/incidents,
                          document expiry - to the configured Notify Role
                          (piggybacks on tasks.notify_users()).
  2. Driver-facing      - trip dispatch, Authority to Load result, fuel
                          confirmation - to the driver's Employee cell
                          number.
  3. Customer-facing    - Shipment status milestones - to the client's
                          number on the Shipment (Client WhatsApp Number is
                          reused as the SMS number too - it's just a phone
                          number field, not WhatsApp-specific storage).

Setup required in Transport Logistics Settings before enabling:
  1. An Africa's Talking account (africastalking.com) with an SMS
     application (sandbox for testing, or a live/production app once
     approved and a Sender ID or shortcode assigned).
  2. The app's Username and API Key (Account > API Key in the dashboard;
     use "sandbox" as the username for the free sandbox environment).

Every send attempt - success or failure - is logged to SMS Message Log for
audit/debugging. Sending never blocks or fails the document transaction
it's triggered from: errors are caught and logged, not raised, except in
test_sms_connection() which is a deliberate manual "does this work" check
from Settings.
"""

import frappe

from transport_logistics.transport_logistics.whatsapp import normalize_number

SANDBOX_URL = "https://api.sandbox.africastalking.com/version1/messaging"
PRODUCTION_URL = "https://api.africastalking.com/version1/messaging"


def _settings():
	return frappe.get_cached_doc("Transport Logistics Settings")


def is_enabled(settings=None):
	settings = settings or _settings()
	return bool(settings.enable_sms)


def _api_url(settings):
	return SANDBOX_URL if settings.sms_environment == "Sandbox" else PRODUCTION_URL


def _log_message(status, recipient, message, reference_doctype=None, reference_name=None,
	sms_message_id=None, error=None):
	try:
		frappe.get_doc(
			{
				"doctype": "SMS Message Log",
				"status": status,
				"recipient": recipient or "",
				"message": message,
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"sms_message_id": sms_message_id,
				"error": error,
			}
		).insert(ignore_permissions=True)
	except Exception:
		# Logging must never be the reason a message send (or the calling
		# document transaction) fails.
		frappe.log_error(frappe.get_traceback(), "SMS Message Log failed to save")


def send_sms(to_number, message, reference_doctype=None, reference_name=None,
	settings=None, raise_on_error=False):
	"""Send a single SMS via Africa's Talking. Best-effort by default: on
	failure this logs to SMS Message Log and Error Log and returns None
	rather than raising, so a notification failure never blocks the
	document that triggered it. Pass raise_on_error=True (used by the
	Settings 'Send Test SMS' action) to surface failures to the caller
	instead."""
	settings = settings or _settings()

	if not is_enabled(settings):
		return None

	if settings.sms_provider and settings.sms_provider != "Africa's Talking":
		message_out = f"SMS provider '{settings.sms_provider}' is not yet wired up. Only Africa's Talking is supported today."
		if raise_on_error:
			frappe.throw(message_out)
		frappe.log_error(message_out, "SMS send failed")
		return None

	number = normalize_number(to_number, settings)
	if not number:
		return None
	# Africa's Talking expects E.164 format (a leading '+').
	if not number.startswith("+"):
		number = f"+{number}"

	# Skip if this exact message was already sent to this recipient for this
	# reference document - guards against duplicate sends when a document is
	# re-saved and the calling hook fires again (mirrors the dedup check in
	# whatsapp.send_whatsapp_message() and tasks.notify_users()).
	if reference_doctype and reference_name:
		already_sent = frappe.db.exists(
			"SMS Message Log",
			{
				"status": "Sent",
				"recipient": number,
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"message": message,
			},
		)
		if already_sent:
			return None

	import requests

	payload = {
		"username": settings.sms_username,
		"to": number,
		"message": message,
	}
	if settings.sms_sender_id:
		payload["from"] = settings.sms_sender_id

	try:
		response = requests.post(
			_api_url(settings),
			data=payload,
			headers={
				"apiKey": settings.get_password("sms_api_key"),
				"Accept": "application/json",
				"Content-Type": "application/x-www-form-urlencoded",
			},
			timeout=30,
		)
		result = response.json()
	except Exception as e:
		_log_message("Failed", number, message, reference_doctype, reference_name, error=str(e))
		frappe.log_error(frappe.get_traceback(), "SMS send failed")
		if raise_on_error:
			frappe.throw(f"SMS could not be sent: {e}")
		return None

	recipients_result = (result.get("SMSMessageData") or {}).get("Recipients") or []
	first = recipients_result[0] if recipients_result else {}
	status_code = first.get("statusCode")

	# Africa's Talking uses statusCode 101 (or 100 in some accounts) for a
	# successfully queued message.
	if status_code in (100, 101):
		message_id = first.get("messageId")
		_log_message("Sent", number, message, reference_doctype, reference_name, sms_message_id=message_id)
		return message_id

	error_detail = first.get("status") or (result.get("SMSMessageData") or {}).get("Message") or response.text
	_log_message("Failed", number, message, reference_doctype, reference_name, error=error_detail)
	frappe.log_error(str(result), "SMS send failed")
	if raise_on_error:
		frappe.throw(f"SMS could not be sent: {error_detail}")
	return None


@frappe.whitelist()
def test_sms_connection(to_number):
	"""Bound to the 'Send Test SMS' button on Transport Logistics Settings.
	Raises a visible error on failure instead of failing silently, since
	this is a deliberate manual check that the configuration works."""
	settings = _settings()
	if not settings.enable_sms:
		frappe.throw("Enable SMS Alerts first, and save Settings.")

	message_id = send_sms(
		to_number,
		"Transport Logistics: this is a test SMS confirming your SMS integration is working.",
		raise_on_error=True,
	)
	if message_id:
		frappe.msgprint(f"Test SMS sent (message ID: {message_id}).")
	return message_id
