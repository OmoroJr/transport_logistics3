# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Shared approval gate used by the five operationally-sensitive actions that
must be signed off by a System Manager before they take effect:

  1. Driver Change            -> Truck Trip
  2. Trailer Decoupling       -> Trailer Coupling Log (action = "Decoupled")
  3. Extra Fuel (over route standard) -> Truck Fuel Log (extra_fuel_litres > 0)
  4. Tyre Change (Fitted/Removed)     -> Tyre Movement Log
  5. Spare Part Issuance      -> Workshop Job Card (parts_cost > 0)

Each of the doctypes above carries three common fields:
  manager_approval_status : Not Required / Pending Approval / Approved / Rejected
  approved_by              : User who approved/rejected
  approved_on              : Datetime of that decision

flag_pending_approval() is called from each doctype's own validate() to flip
Not Required -> Pending Approval the moment the record starts describing one
of the five sensitive actions. block_submit_if_not_approved() is then called
so submission (docstatus 1) is refused until a System Manager has approved.

approve_request()/reject_request() are the only way manager_approval_status
can move to Approved/Rejected — the field itself is read-only on every
doctype, so a Transport Manager/User can request but never self-approve.

get_pending_approvals() backs the navbar "Approvals" notification widget
(public/js/approval_notifications.js): it lists everything currently
Pending Approval, System Manager-only, by reusing the Manager Approval
Report's row-building logic so there is one source of truth for "what
counts as a pending request" across the report and the widget. A request
disappears from the widget the moment it's approved/rejected — approve_request()/
reject_request() broadcast a realtime ping so it drops off every connected
System Manager's list immediately, and it also simply stops matching the
Pending Approval filter on the next poll.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

APPROVER_ROLES = ("System Manager",)
APPROVAL_UPDATE_EVENT = "transport_logistics_approval_update"

# doctype -> (label shown in messages/report, function that decides whether
# THIS particular save currently describes a sensitive action)
APPROVAL_REQUIRED_CHECKS = {}


def register(doctype, requires_approval_fn, label):
	APPROVAL_REQUIRED_CHECKS[doctype] = (requires_approval_fn, label)


def flag_pending_approval(doc, requires_approval_fn):
	"""Call from validate(). Moves a fresh/blank status to Pending Approval
	as soon as the record describes a sensitive action; leaves an existing
	Approved/Rejected/Pending status alone (re-validating an already-decided
	record shouldn't silently reopen it), except once the underlying
	sensitive detail changes after a Rejection, which re-opens it for a
	fresh request."""
	needs_approval = requires_approval_fn(doc)

	if not needs_approval:
		if doc.get("manager_approval_status") in (None, "", "Not Required"):
			doc.manager_approval_status = "Not Required"
		return

	if not doc.get("manager_approval_status") or doc.manager_approval_status in ("Not Required",):
		doc.manager_approval_status = "Pending Approval"
		doc.approved_by = None
		doc.approved_on = None
		# Best-effort nudge for the navbar widget; if validate() goes on to
		# throw for an unrelated reason the save never lands so nothing was
		# actually raised, but the ping already fired -- harmless, since the
		# widget just re-fetches the (unchanged) pending list.
		_notify_approval_change()


def block_submit_if_not_approved(doc, label):
	"""Call from validate(); by the time validate() runs during submit,
	doc.docstatus is already 1, so this only fires on the actual submit
	transition — plain saves as Pending Approval are never blocked."""
	if doc.docstatus != 1:
		return
	if doc.get("manager_approval_status") in (None, "", "Not Required", "Approved"):
		return
	if doc.manager_approval_status == "Pending Approval":
		frappe.throw(
			_(
				"This {0} involves {1}, which requires System Manager approval before it can "
				"be submitted. Save it and ask a System Manager to approve it from the Manager "
				"Approval Report, then submit again."
			).format(frappe.bold(doc.doctype), label)
		)
	if doc.manager_approval_status == "Rejected":
		frappe.throw(
			_("This {0} was rejected by a System Manager and cannot be submitted as-is. "
			  "Update the details to raise a fresh approval request.").format(frappe.bold(doc.doctype))
		)


def _check_is_approver():
	user_roles = frappe.get_roles(frappe.session.user)
	if not any(role in user_roles for role in APPROVER_ROLES):
		frappe.throw(
			_("You don't have permission to approve or reject this request. This action is "
			  "restricted to System Manager."),
			frappe.PermissionError,
		)


def _notify_approval_change():
	"""Ping every connected user so the navbar approvals widget refreshes.
	No user/room is passed, so this broadcasts site-wide; that's fine here
	because the endpoint it triggers a refresh of (get_pending_approvals)
	is itself System Manager-gated, so non-approvers just get an empty
	list back."""
	frappe.publish_realtime(APPROVAL_UPDATE_EVENT, {})


@frappe.whitelist()
def get_pending_approvals():
	"""Everything currently Pending Approval, for the navbar widget. Reuses
	the Manager Approval Report's row builder so the widget and the report
	can never disagree about what's pending."""
	_check_is_approver()

	from transport_logistics.transport_logistics.report.manager_approval_report.manager_approval_report import (
		get_data,
	)

	rows = get_data(frappe._dict({"status": "Pending Approval"}))
	return [
		{
			"request_type": r.get("request_type"),
			"reference_doctype": r.get("reference_doctype"),
			"reference_name": r.get("reference_name"),
			"truck": r.get("truck"),
			"details": r.get("details"),
			"requested_by": r.get("requested_by"),
			"date": str(r["date"]) if r.get("date") else None,
		}
		for r in rows
	]


def _apply_approved_effect(doc):
	"""Doctype-specific effect of an approval, applied to the in-memory doc
	before it's saved. Every doctype except Truck Trip just needs the status
	flip (the sensitive action they describe was already fully recorded on
	the document); Truck Trip's Driver field is deliberately only updated
	here, once approved."""
	if doc.doctype == "Truck Trip" and doc.new_driver_requested:
		doc.driver = doc.new_driver_requested


@frappe.whitelist()
def approve_request(doctype, name):
	_check_is_approver()
	doc = frappe.get_doc(doctype, name)

	if doc.get("manager_approval_status") != "Pending Approval":
		frappe.throw(_("Only a request that is Pending Approval can be approved."))

	doc.manager_approval_status = "Approved"
	doc.approved_by = frappe.session.user
	doc.approved_on = now_datetime()
	_apply_approved_effect(doc)
	doc.save(ignore_permissions=True)
	_notify_approval_change()
	return doc.name


@frappe.whitelist()
def reject_request(doctype, name, remarks=None):
	_check_is_approver()
	doc = frappe.get_doc(doctype, name)

	if doc.get("manager_approval_status") != "Pending Approval":
		frappe.throw(_("Only a request that is Pending Approval can be rejected."))

	if not remarks or not remarks.strip():
		frappe.throw(_("A reason is required when rejecting a request — please explain why."))

	doc.manager_approval_status = "Rejected"
	doc.approved_by = frappe.session.user
	doc.approved_on = now_datetime()
	if doc.meta.has_field("approval_remarks"):
		doc.approval_remarks = remarks.strip()
	doc.save(ignore_permissions=True)
	_notify_approval_change()
	return doc.name
