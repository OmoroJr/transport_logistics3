# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Optional integration that posts Transport Logistics costs into ERPNext's
General Ledger as Journal Entries. Controlled entirely by
'Transport Logistics Settings' -> Post Costs to General Ledger.

Each source doctype (Truck Fuel Log, Truck Maintenance Log, Truck Expense,
Tyre Movement Log) has a read-only 'journal_entry' field that stores the
resulting Journal Entry name, so postings are never duplicated and are
cancelled automatically if the source document is cancelled.
"""

import frappe
from frappe.utils import flt


def _get_settings():
	return frappe.get_cached_doc("Transport Logistics Settings")


def _create_journal_entry(
	company, posting_date, expense_account, amount, cost_center, remark, credit_account=None
):
	if not amount:
		return None

	settings = _get_settings()
	payment_account = credit_account or settings.default_payment_account

	if not company:
		frappe.msgprint(
			"GL posting skipped: no Company could be determined for this entry.", alert=True
		)
		return None

	if not (expense_account and payment_account):
		frappe.msgprint(
			"GL posting skipped: please configure the relevant expense account and "
			"a credit/payment account in Transport Logistics Settings.",
			alert=True,
		)
		return None

	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.company = company
	je.posting_date = posting_date
	je.user_remark = remark
	je.append(
		"accounts",
		{
			"account": expense_account,
			"debit_in_account_currency": flt(amount),
			"cost_center": cost_center or settings.default_cost_center,
		},
	)
	je.append(
		"accounts",
		{
			"account": payment_account,
			"credit_in_account_currency": flt(amount),
			"cost_center": cost_center or settings.default_cost_center,
		},
	)
	je.insert(ignore_permissions=True)
	je.submit()
	return je.name


def post_fuel_log_to_gl(doc, method=None):
	# Internally-dispensed fuel is expensed via the Fuel Dispensing record's
	# own GL posting (Dr Fuel Expense / Cr Fuel Stock Asset) instead — the
	# cash already left the business at Bulk Fuel Purchase time, so posting
	# here too would double-count the outflow.
	if doc.get("source") == "Internal Bulk Dispensing":
		return
	settings = _get_settings()
	if not settings.enable_gl_posting or doc.get("journal_entry"):
		return
	je_name = _create_journal_entry(
		doc.company,
		doc.date,
		settings.fuel_expense_account,
		doc.total_amount,
		settings.default_cost_center,
		f"Fuel Log {doc.name} - Truck {doc.truck} ({flt(doc.fuel_qty_litres)} L)",
	)
	if je_name:
		doc.db_set("journal_entry", je_name, update_modified=False)


def post_maintenance_log_to_gl(doc, method=None):
	settings = _get_settings()
	if not settings.enable_gl_posting or doc.get("journal_entry"):
		return
	je_name = _create_journal_entry(
		doc.company,
		doc.date,
		settings.maintenance_expense_account,
		doc.total_cost,
		settings.default_cost_center,
		f"Maintenance Log {doc.name} - Truck {doc.truck} ({doc.maintenance_type})",
	)
	if je_name:
		doc.db_set("journal_entry", je_name, update_modified=False)


def post_expense_to_gl(doc, method=None):
	settings = _get_settings()
	if not settings.enable_gl_posting or doc.get("journal_entry"):
		return
	je_name = _create_journal_entry(
		doc.company,
		doc.date,
		settings.other_expense_account,
		doc.amount,
		settings.default_cost_center,
		f"Truck Expense {doc.name} - Truck {doc.truck} ({doc.expense_type})",
	)
	if je_name:
		doc.db_set("journal_entry", je_name, update_modified=False)


def post_tyre_movement_to_gl(doc, method=None):
	# Only retreading has a real cost worth posting; fitting/rotating/removing don't.
	if doc.movement_type != "Retreaded" or not doc.cost:
		return

	settings = _get_settings()
	if not settings.enable_gl_posting or doc.get("journal_entry"):
		return

	company = doc.get("company")
	if not company and doc.truck:
		company = frappe.get_cached_value("Truck", doc.truck, "company")

	je_name = _create_journal_entry(
		company,
		doc.date,
		settings.tyre_expense_account,
		doc.cost,
		settings.default_cost_center,
		f"Tyre Retread {doc.name} - Tyre {doc.tyre}",
	)
	if je_name:
		doc.db_set("journal_entry", je_name, update_modified=False)


def post_accident_to_gl(doc, method=None):
	"""Posts the net cost (repair + other − insurance recovered) of an accident."""
	settings = _get_settings()
	if not settings.enable_gl_posting or doc.get("journal_entry"):
		return
	if not doc.net_cost or doc.net_cost <= 0:
		return
	je_name = _create_journal_entry(
		doc.company,
		frappe.utils.getdate(doc.date_of_accident),
		settings.accident_expense_account,
		doc.net_cost,
		settings.default_cost_center,
		f"Accident Report {doc.name} - Truck {doc.truck} ({doc.severity})",
	)
	if je_name:
		doc.db_set("journal_entry", je_name, update_modified=False)


def post_breakdown_to_gl(doc, method=None):
	"""Posts the total cost (repair + towing + other) of a highway breakdown."""
	settings = _get_settings()
	if not settings.enable_gl_posting or doc.get("journal_entry"):
		return
	if not doc.total_cost or doc.total_cost <= 0:
		return
	je_name = _create_journal_entry(
		doc.company,
		frappe.utils.getdate(doc.date_time_of_breakdown),
		settings.breakdown_expense_account,
		doc.total_cost,
		settings.default_cost_center,
		f"Highway Breakdown {doc.name} - Truck {doc.truck} ({doc.breakdown_type})",
	)
	if je_name:
		doc.db_set("journal_entry", je_name, update_modified=False)


def post_bulk_fuel_purchase_to_gl(doc, method=None):
	"""Bulk fuel bought into a tank is a stock asset, not yet an expense —
	debit the Fuel Stock Asset account, credit however it was paid for."""
	settings = _get_settings()
	if not settings.enable_gl_posting or doc.get("journal_entry"):
		return
	je_name = _create_journal_entry(
		doc.company,
		doc.date,
		settings.fuel_stock_asset_account,
		doc.total_amount,
		settings.default_cost_center,
		f"Bulk Fuel Purchase {doc.name} - Tank {doc.tank}",
	)
	if je_name:
		doc.db_set("journal_entry", je_name, update_modified=False)


def post_fuel_dispensing_to_gl(doc, method=None):
	"""Dispensing fuel from the tank into a truck is when the cost actually
	becomes a Fuel Expense — debit Fuel Expense, credit Fuel Stock Asset
	(the same account bulk purchases debited into)."""
	settings = _get_settings()
	if not settings.enable_gl_posting or doc.get("journal_entry"):
		return
	if not doc.get("total_amount"):
		return
	je_name = _create_journal_entry(
		doc.company,
		doc.date,
		settings.fuel_expense_account,
		doc.total_amount,
		settings.default_cost_center,
		f"Fuel Dispensing {doc.name} - Truck {doc.truck} from Tank {doc.tank}",
		credit_account=settings.fuel_stock_asset_account,
	)
	if je_name:
		doc.db_set("journal_entry", je_name, update_modified=False)


def post_driver_payment_to_gl(doc, method=None):
	"""Posts a Driver Mileage Payment, crediting Cash/M-Pesa/Bank depending
	on how it was paid, per the accounts configured in Transport Logistics
	Settings."""
	settings = _get_settings()
	if not settings.enable_gl_posting or doc.get("journal_entry"):
		return

	credit_account = {
		"Cash": settings.cash_account,
		"M-Pesa": settings.mpesa_account,
		"Bank Transfer": settings.default_payment_account,
	}.get(doc.payment_method)

	je_name = _create_journal_entry(
		doc.company,
		doc.payment_date or frappe.utils.today(),
		settings.driver_payment_expense_account,
		doc.total_amount,
		settings.default_cost_center,
		f"Driver Mileage Payment {doc.name} - Driver {doc.driver} ({doc.payment_method})",
		credit_account=credit_account,
	)
	if je_name:
		doc.db_set("journal_entry", je_name, update_modified=False)


def cancel_linked_journal_entry(doc, method=None):
	"""Generic on_cancel handler: cancels the Journal Entry created for this doc, if any."""
	je_name = doc.get("journal_entry")
	if je_name and frappe.db.exists("Journal Entry", je_name):
		je = frappe.get_doc("Journal Entry", je_name)
		if je.docstatus == 1:
			je.cancel()
