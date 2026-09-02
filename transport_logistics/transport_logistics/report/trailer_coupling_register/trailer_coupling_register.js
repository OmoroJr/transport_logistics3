// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.query_reports["Trailer Coupling Register"] = {
	filters: [
		{
			fieldname: "trailer",
			label: __("Trailer"),
			fieldtype: "Link",
			options: "Trailer",
		},
		{
			fieldname: "truck",
			label: __("Truck"),
			fieldtype: "Link",
			options: "Truck",
		},
		{
			fieldname: "action",
			label: __("Action"),
			fieldtype: "Select",
			options: "\nCoupled\nDecoupled",
		},
		{
			fieldname: "manager_approval_status",
			label: __("Approval Status"),
			fieldtype: "Select",
			options: "\nNot Required\nPending Approval\nApproved\nRejected",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "include_unsubmitted",
			label: __("Include Draft / Cancelled Logs"),
			fieldtype: "Check",
			description: __("By default only submitted coupling logs are included."),
		},
	],
};
