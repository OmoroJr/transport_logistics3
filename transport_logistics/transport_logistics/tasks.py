# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Scheduled (daily) job that checks every active Truck's compliance
expiry dates (Insurance, License, Inspection, COMESA/Yellow Card) and
raises a Notification + ToDo for the configured role when a document is
within N days of expiry (or already expired), per Transport Logistics
Settings.
"""

import frappe
from frappe.utils import today, date_diff, getdate

EXPIRY_FIELDS = {
	"insurance_expiry_date": "Insurance",
	"license_expiry_date": "License",
	"inspection_expiry_date": "Inspection",
	"comesa_expiry_date": "COMESA / Yellow Card",
}


def check_document_expiry():
	settings = frappe.get_cached_doc("Transport Logistics Settings")
	days_before = settings.expiry_alert_days_before or 30
	notify_role = settings.notify_role or "Transport Manager"

	user_list = _get_users_with_role(notify_role)
	if not user_list:
		return

	trucks = frappe.get_all(
		"Truck",
		filters={"status": ["!=", "Disposed"]},
		fields=["name", "registration_number", *EXPIRY_FIELDS.keys()],
	)

	today_date = getdate(today())

	for truck in trucks:
		for fieldname, label in EXPIRY_FIELDS.items():
			exp_date = truck.get(fieldname)
			if not exp_date:
				continue
			days_left = date_diff(exp_date, today_date)
			# Alert on anything expired, or expiring within the configured window.
			if days_left <= days_before:
				_raise_alert(truck, label, exp_date, days_left, user_list)


def _get_users_with_role(role):
	rows = frappe.get_all(
		"Has Role", filters={"role": role, "parenttype": "User"}, fields=["parent"]
	)
	users = []
	for row in rows:
		if frappe.db.get_value("User", row.parent, "enabled"):
			users.append(row.parent)
	return users


def notify_users(subject, message, reference_doctype, reference_name, priority="Medium", role=None):
	"""Shared helper: raises a Notification Log for every user holding `role`
	(defaults to the configured Transport Logistics Settings notify role),
	plus one actionable ToDo. Used both by the daily expiry check and by
	immediate high-severity accident/incident alerts."""
	if not role:
		settings = frappe.get_cached_doc("Transport Logistics Settings")
		role = settings.notify_role or "Transport Manager"

	user_list = _get_users_with_role(role)
	if not user_list:
		return

	for user in user_list:
		already_notified = frappe.db.exists(
			"Notification Log",
			{
				"for_user": user,
				"document_type": reference_doctype,
				"document_name": reference_name,
				"subject": subject,
			},
		)
		if already_notified:
			continue

		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": user,
				"subject": subject,
				"type": "Alert",
				"document_type": reference_doctype,
				"document_name": reference_name,
				"from_user": frappe.session.user or "Administrator",
			}
		).insert(ignore_permissions=True)

	todo_exists = frappe.db.exists(
		"ToDo",
		{
			"reference_type": reference_doctype,
			"reference_name": reference_name,
			"status": "Open",
		},
	)
	if not todo_exists:
		frappe.get_doc(
			{
				"doctype": "ToDo",
				"allocated_to": user_list[0],
				"description": message,
				"reference_type": reference_doctype,
				"reference_name": reference_name,
				"priority": priority,
			}
		).insert(ignore_permissions=True)


def check_driver_license_expiry():
	"""Same idea as check_document_expiry() above, but for drivers' Driving
	License Expiry Date (a Custom Field on Employee — see fixtures/
	custom_field.json). Only Employees who actually have that field filled
	in are checked, so this naturally scopes itself to drivers without
	needing a separate 'is this employee a driver' flag."""
	settings = frappe.get_cached_doc("Transport Logistics Settings")
	days_before = settings.expiry_alert_days_before or 30
	notify_role = settings.notify_role or "Transport Manager"

	user_list = _get_users_with_role(notify_role)
	if not user_list:
		return

	if "driving_license_expiry_date" not in frappe.db.get_table_columns("Employee"):
		# Custom Field fixture (fixtures/custom_field.json) hasn't been
		# migrated on this site yet — skip quietly rather than crashing
		# the whole scheduled job every night.
		return

	employees = frappe.get_all(
		"Employee",
		filters={"status": "Active", "driving_license_expiry_date": ["is", "set"]},
		fields=["name", "employee_name", "driving_license_expiry_date"],
	)

	today_date = getdate(today())

	for emp in employees:
		days_left = date_diff(emp.driving_license_expiry_date, today_date)
		if days_left <= days_before:
			_raise_driver_license_alert(emp, emp.driving_license_expiry_date, days_left, user_list)


def _raise_driver_license_alert(emp, exp_date, days_left, user_list):
	if days_left < 0:
		status = f"expired {abs(days_left)} day(s) ago"
		priority = "High"
	else:
		status = f"expires in {days_left} day(s)"
		priority = "High" if days_left <= 7 else "Medium"

	subject = f"Driving License for {emp.employee_name} ({emp.name}) {status}"
	message = (
		f"Driving License for {emp.employee_name} ({emp.name}) {status} (due {exp_date}). "
		"Please arrange renewal before assigning further trips."
	)
	notify_users(subject, message, "Employee", emp.name, priority=priority)


def _raise_alert(truck, label, exp_date, days_left, user_list):
	if days_left < 0:
		status = f"expired {abs(days_left)} day(s) ago"
		priority = "High"
	else:
		status = f"expires in {days_left} day(s)"
		priority = "High" if days_left <= 7 else "Medium"

	subject = f"{label} for {truck.name} ({truck.registration_number}) {status}"
	message = (
		f"{label} for Truck {truck.name} ({truck.registration_number}) {status} "
		f"(due {exp_date}). Please arrange renewal."
	)
	notify_users(subject, message, "Truck", truck.name, priority=priority)
