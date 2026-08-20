# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Optional email notifications, sent via Frappe's own outgoing Email Account
(Settings > Email Account) through frappe.sendmail() — no separate SMTP
credentials are needed here, only the toggles below. Mirrors whatsapp.py's
three independently-toggled channels, set up under Transport Logistics
Settings > Email Alerts:

  1. Internal alerts   - breakdowns, high-severity accidents/incidents,
                          document expiry - to every enabled user holding
                          the Notify Role (piggybacks on tasks.notify_users()).
  2. Driver-facing      - trip dispatch, Authority to Load result, fuel
                          confirmation - to the driver's Employee email
                          (Company Email, falling back to Personal Email).
  3. Customer-facing    - Shipment status milestones - to the Client Email
                          on the Shipment.

Every send attempt is recorded as a Communication against the reference
document by frappe.sendmail() itself (visible in that document's Activity
tab) — there is no separate log doctype for email, unlike WhatsApp/SMS which
talk to an external HTTP API and need their own audit trail. Sending never
blocks or fails the document transaction it's triggered from: errors are
caught and logged, not raised, except in test_email_connection() which is a
deliberate manual "does this work" check from Settings.
"""

import frappe


def _settings():
	return frappe.get_cached_doc("Transport Logistics Settings")


def is_enabled(settings=None):
	settings = settings or _settings()
	return bool(settings.enable_email_alerts)


def send_email_alert(recipients, subject, message, reference_doctype=None, reference_name=None,
	settings=None, raise_on_error=False):
	"""Send a plain-text-style email. Best-effort by default: on failure this
	logs to Error Log and returns False rather than raising, so a
	notification failure never blocks the document that triggered it. Pass
	raise_on_error=True (used by the Settings 'Send Test Email' action) to
	surface failures to the caller instead. `recipients` may be a single
	email string or a list of them."""
	settings = settings or _settings()

	if not is_enabled(settings):
		return False

	if isinstance(recipients, str):
		recipients = [recipients]
	recipients = [r for r in (recipients or []) if r]
	if not recipients:
		return False

	# Guard against duplicate sends when a document is re-saved and the
	# calling hook fires again - same dedup idea used by
	# whatsapp.send_whatsapp_message() and tasks.notify_users().
	if reference_doctype and reference_name:
		already_sent = frappe.db.exists(
			"Communication",
			{
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"subject": subject,
				"communication_type": "Communication",
				"sent_or_received": "Sent",
			},
		)
		if already_sent:
			return False

	try:
		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			message=message.replace("\n", "<br>"),
			reference_doctype=reference_doctype,
			reference_name=reference_name,
			now=True,
		)
		return True
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Email alert failed to send")
		if raise_on_error:
			frappe.throw(f"Email could not be sent: {e}")
		return False


@frappe.whitelist()
def test_email_connection(to_email):
	"""Bound to the 'Send Test Email' button on Transport Logistics
	Settings. Raises a visible error on failure instead of failing
	silently, since this is a deliberate manual check that the site's
	Email Account is configured and working."""
	settings = _settings()
	if not settings.enable_email_alerts:
		frappe.throw("Enable Email Alerts first, and save Settings.")

	sent = send_email_alert(
		to_email,
		"Transport Logistics: test email",
		"This is a test email confirming your Transport Logistics email alerts are working.",
		raise_on_error=True,
	)
	if sent:
		frappe.msgprint(f"Test email sent to {to_email}.")
	return sent
