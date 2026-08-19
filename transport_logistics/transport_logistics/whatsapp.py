# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Optional WhatsApp integration via Meta's WhatsApp Business Cloud API (the
official Graph API, not a third-party wrapper). Used across the app for
three kinds of messages, each independently toggled in Transport Logistics
Settings:

  1. Internal alerts   - breakdowns, high-severity accidents/incidents,
                          document expiry - to the configured Notify Role
                          (piggybacks on tasks.notify_users()).
  2. Driver-facing      - trip dispatch, Authority to Load result, fuel
                          confirmation - to the driver's Employee cell number.
  3. Customer-facing    - Shipment status milestones - to the client's
                          WhatsApp number on the Shipment.

Setup required in Transport Logistics Settings before enabling:
  1. A Meta Business + WhatsApp Business Platform app (business.facebook.com),
     with a registered phone number.
  2. The Phone Number ID for that number (Cloud API dashboard).
  3. A permanent access token (System User token from a Meta Business
     integration, not the 24-hour test token).

Outside Meta's 24-hour customer-service window, freeform text messages can
only be delivered to numbers that have messaged your business number first;
otherwise use a pre-approved Message Template (send_whatsapp_template below).
Every send attempt - success or failure - is logged to WhatsApp Message Log
for audit/debugging. Sending never blocks or fails the document transaction
it's triggered from: errors are caught and logged, not raised, except in
test_whatsapp_connection() which is a deliberate manual "does this work"
check from Settings.
"""

import json

import frappe

GRAPH_BASE_URL = "https://graph.facebook.com"


def _settings():
	return frappe.get_cached_doc("Transport Logistics Settings")


def is_enabled(settings=None):
	settings = settings or _settings()
	return bool(settings.enable_whatsapp)


def normalize_number(number, settings=None):
	"""Reduce a phone number to the digits-only, country-coded format the
	Cloud API expects (e.g. 254712345678). Strips spaces, dashes, brackets
	and a leading '+'. A number starting with a single leading '0' (the
	common local format, e.g. 0712345678) has that '0' replaced with the
	configured Default Country Code. Returns None if nothing usable is left,
	so callers can skip silently rather than firing a request at a blank
	number."""
	if not number:
		return None

	settings = settings or _settings()
	digits = "".join(ch for ch in str(number) if ch.isdigit())
	if not digits:
		return None

	if number.strip().startswith("0") and not number.strip().startswith("00"):
		country_code = (settings.default_country_code or "").strip()
		if country_code:
			digits = country_code.lstrip("+") + digits[1:]

	return digits


def _api_url(settings):
	version = settings.whatsapp_api_version or "v21.0"
	return f"{GRAPH_BASE_URL}/{version}/{settings.whatsapp_phone_number_id}/messages"


def _log_message(direction, status, recipient, message, reference_doctype=None,
	reference_name=None, whatsapp_message_id=None, error=None):
	try:
		frappe.get_doc(
			{
				"doctype": "WhatsApp Message Log",
				"direction": direction,
				"status": status,
				"recipient": recipient or "",
				"message": message,
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"whatsapp_message_id": whatsapp_message_id,
				"error": error,
			}
		).insert(ignore_permissions=True)
	except Exception:
		# Logging must never be the reason a message send (or the calling
		# document transaction) fails.
		frappe.log_error(frappe.get_traceback(), "WhatsApp Message Log failed to save")


def send_whatsapp_message(to_number, message, reference_doctype=None, reference_name=None,
	settings=None, raise_on_error=False):
	"""Send a freeform text message. Best-effort by default: on failure this
	logs to WhatsApp Message Log and Error Log and returns None rather than
	raising, so a notification failure never blocks the document that
	triggered it. Pass raise_on_error=True (used by the Settings 'Send Test
	Message' action) to surface failures to the caller instead."""
	settings = settings or _settings()

	if not is_enabled(settings):
		return None

	number = normalize_number(to_number, settings)
	if not number:
		return None

	# Skip if this exact message was already sent to this recipient for this
	# reference document - guards against duplicate sends when a document is
	# re-saved and the calling hook fires again (mirrors the dedup check in
	# tasks.notify_users()).
	if reference_doctype and reference_name:
		already_sent = frappe.db.exists(
			"WhatsApp Message Log",
			{
				"direction": "Outgoing",
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
		"messaging_product": "whatsapp",
		"to": number,
		"type": "text",
		"text": {"body": message},
	}

	try:
		response = requests.post(
			_api_url(settings),
			json=payload,
			headers={"Authorization": f"Bearer {settings.get_password('whatsapp_access_token')}"},
			timeout=30,
		)
		result = response.json()
	except Exception as e:
		_log_message("Outgoing", "Failed", number, message, reference_doctype, reference_name, error=str(e))
		frappe.log_error(frappe.get_traceback(), "WhatsApp send failed")
		if raise_on_error:
			frappe.throw(f"WhatsApp message could not be sent: {e}")
		return None

	if response.status_code == 200 and result.get("messages"):
		message_id = result["messages"][0].get("id")
		_log_message("Outgoing", "Sent", number, message, reference_doctype, reference_name, whatsapp_message_id=message_id)
		return message_id

	error_detail = result.get("error", {}).get("message") or response.text
	_log_message("Outgoing", "Failed", number, message, reference_doctype, reference_name, error=error_detail)
	frappe.log_error(json.dumps(result), "WhatsApp send failed")
	if raise_on_error:
		frappe.throw(f"WhatsApp message could not be sent: {error_detail}")
	return None


def send_whatsapp_template(to_number, template_name, language_code="en", parameters=None,
	reference_doctype=None, reference_name=None, settings=None, raise_on_error=False):
	"""Send a pre-approved Message Template - required to reach a number
	that hasn't messaged your business number within the last 24 hours.
	`parameters` is an ordered list of strings filling the template's {{1}},
	{{2}}, ... placeholders in its body. Template messages must be created
	and approved in Meta Business Manager before use; this simply invokes
	one by name."""
	settings = settings or _settings()

	if not is_enabled(settings):
		return None

	number = normalize_number(to_number, settings)
	if not number:
		return None

	import requests

	components = []
	if parameters:
		components.append(
			{
				"type": "body",
				"parameters": [{"type": "text", "text": str(p)} for p in parameters],
			}
		)

	payload = {
		"messaging_product": "whatsapp",
		"to": number,
		"type": "template",
		"template": {
			"name": template_name,
			"language": {"code": language_code},
			"components": components,
		},
	}

	log_text = f"[template: {template_name}] " + ", ".join(str(p) for p in (parameters or []))

	try:
		response = requests.post(
			_api_url(settings),
			json=payload,
			headers={"Authorization": f"Bearer {settings.get_password('whatsapp_access_token')}"},
			timeout=30,
		)
		result = response.json()
	except Exception as e:
		_log_message("Outgoing", "Failed", number, log_text, reference_doctype, reference_name, error=str(e))
		if raise_on_error:
			frappe.throw(f"WhatsApp template message could not be sent: {e}")
		return None

	if response.status_code == 200 and result.get("messages"):
		message_id = result["messages"][0].get("id")
		_log_message("Outgoing", "Sent", number, log_text, reference_doctype, reference_name, whatsapp_message_id=message_id)
		return message_id

	error_detail = result.get("error", {}).get("message") or response.text
	_log_message("Outgoing", "Failed", number, log_text, reference_doctype, reference_name, error=error_detail)
	if raise_on_error:
		frappe.throw(f"WhatsApp template message could not be sent: {error_detail}")
	return None


@frappe.whitelist()
def test_whatsapp_connection(to_number):
	"""Bound to the 'Send Test Message' button on Transport Logistics
	Settings. Raises a visible error on failure instead of failing silently,
	since this is a deliberate manual check that the configuration works."""
	settings = _settings()
	if not settings.enable_whatsapp:
		frappe.throw("Enable WhatsApp Integration first, and save Settings.")

	message_id = send_whatsapp_message(
		to_number,
		"Transport Logistics: this is a test message confirming your WhatsApp integration is working.",
		raise_on_error=True,
	)
	if message_id:
		frappe.msgprint(f"Test message sent (WhatsApp message ID: {message_id}).")
	return message_id


# --- Webhook: inbound messages and delivery status updates -----------------


@frappe.whitelist(allow_guest=True)
def webhook():
	"""Single endpoint for both parts of Meta's webhook contract:

	GET  - the subscription verification handshake. Meta calls this once
	       when you register the webhook URL, with hub.mode=subscribe,
	       hub.verify_token, and hub.challenge query params. Must echo back
	       hub.challenge verbatim if the token matches, or the subscription
	       is rejected.
	POST - actual event delivery: inbound messages from customers/drivers,
	       and delivery/read status updates for messages you sent. Both are
	       logged to WhatsApp Message Log for visibility; no automated
	       reply logic is implemented; that's naturally the next layer to
	       add here if inbound conversations become part of the workflow.

	Set this as your webhook URL in Meta App settings:
	https://your-site/api/method/transport_logistics.transport_logistics.whatsapp.webhook
	"""
	settings = _settings()

	if frappe.request.method == "GET":
		args = frappe.local.form_dict
		if (
			args.get("hub.mode") == "subscribe"
			and args.get("hub.verify_token") == settings.whatsapp_webhook_verify_token
		):
			frappe.response.type = "text"
			return args.get("hub.challenge")
		frappe.local.response.http_status_code = 403
		return "Verification token mismatch"

	data = frappe.request.get_json(silent=True) or {}

	try:
		for entry in data.get("entry", []):
			for change in entry.get("changes", []):
				value = change.get("value", {})
				_log_inbound_messages(value)
				_log_status_updates(value)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "WhatsApp webhook processing failed")

	# Meta expects a 200 response regardless of what was inside, or it will
	# keep retrying delivery of the same event.
	return {"status": "received"}


def _log_inbound_messages(value):
	for msg in value.get("messages", []):
		sender = msg.get("from")
		text = (msg.get("text") or {}).get("body") or f"[{msg.get('type', 'non-text')} message]"
		_log_message("Incoming", "Received", sender, text, whatsapp_message_id=msg.get("id"))


def _log_status_updates(value):
	status_map = {"sent": "Sent", "delivered": "Delivered", "read": "Read", "failed": "Failed"}
	for status in value.get("statuses", []):
		message_id = status.get("id")
		mapped_status = status_map.get(status.get("status"))
		if not (message_id and mapped_status):
			continue
		existing = frappe.db.get_value("WhatsApp Message Log", {"whatsapp_message_id": message_id}, "name")
		if existing:
			frappe.db.set_value("WhatsApp Message Log", existing, "status", mapped_status)
