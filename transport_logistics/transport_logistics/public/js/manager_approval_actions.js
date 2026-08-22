// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

/*
 * Approve/Reject buttons directly on the document form for anything gated
 * by manager_approval.py (Truck Trip, Trailer Coupling Log, Truck Fuel Log,
 * Tyre Movement Log, Workshop Job Card). This is deliberately the simplest
 * possible surface for it: each doctype's own client script (already
 * auto-loaded by Frappe from doctype/<name>/<name>.js — no extra hook
 * wiring needed) just calls transport_logistics.manager_approval.add_buttons(frm)
 * from its refresh handler.
 *
 * This exists alongside the navbar Approvals widget and the Manager
 * Approval Report — use whichever is most convenient; they all call the
 * same approve_request()/reject_request() endpoints, so a decision made
 * from any one of them is immediately reflected in the others.
 */

frappe.provide("transport_logistics.manager_approval");

transport_logistics.manager_approval.add_buttons = function (frm) {
	if (frm.is_new()) return;
	if (frm.doc.manager_approval_status !== "Pending Approval") return;
	if (!frappe.user_roles || !frappe.user_roles.includes("System Manager")) return;

	frm.add_custom_button(
		__("Approve"),
		() => {
			frappe.confirm(__("Approve this request?"), () => {
				frappe.call({
					method: "transport_logistics.transport_logistics.manager_approval.approve_request",
					args: { doctype: frm.doctype, name: frm.docname },
					freeze: true,
					callback: () => {
						frappe.show_alert({ message: __("Approved"), indicator: "green" });
						frm.reload_doc();
					},
				});
			});
		},
		__("Manager Approval")
	);

	frm.add_custom_button(
		__("Reject"),
		() => {
			frappe.prompt(
				[
					{
						fieldname: "remarks",
						fieldtype: "Small Text",
						label: __("Rejection Remarks"),
						reqd: 1,
					},
				],
				(values) => {
					frappe.call({
						method: "transport_logistics.transport_logistics.manager_approval.reject_request",
						args: { doctype: frm.doctype, name: frm.docname, remarks: values.remarks },
						freeze: true,
						callback: () => {
							frappe.show_alert({ message: __("Rejected"), indicator: "orange" });
							frm.reload_doc();
						},
					});
				},
				__("Reject Request"),
				__("Reject")
			);
		},
		__("Manager Approval")
	);
};
