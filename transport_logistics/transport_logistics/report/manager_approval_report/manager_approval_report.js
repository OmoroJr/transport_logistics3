// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.query_reports["Manager Approval Report"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "truck",
			label: __("Truck"),
			fieldtype: "Link",
			options: "Truck",
		},
		{
			fieldname: "request_type",
			label: __("Request Type"),
			fieldtype: "Select",
			options: "\nDriver Change\nTrailer Decoupling\nExtra Fuel\nTyre Change\nSpare Part Issuance",
		},
		{
			fieldname: "status",
			label: __("Approval Status"),
			fieldtype: "Select",
			options: "\nPending Approval\nApproved\nRejected",
			default: "Pending Approval",
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
	],

	onload: function (report) {
		report.page.add_inner_button(__("Approve..."), function () {
			prompt_for_decision(report, "approve");
		});
		report.page.add_inner_button(__("Reject..."), function () {
			prompt_for_decision(report, "reject");
		});
	},

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "status") {
			if (data.status === "Pending Approval") {
				value = `<span style="color: var(--orange-600); font-weight: 600;">${value}</span>`;
			} else if (data.status === "Approved") {
				value = `<span style="color: var(--green-600); font-weight: 600;">${value}</span>`;
			} else if (data.status === "Rejected") {
				value = `<span style="color: var(--red-600); font-weight: 600;">${value}</span>`;
			}
		}
		return value;
	},
};

function prompt_for_decision(report, action) {
	// Restricted to System Manager anyway (enforced server-side by
	// manager_approval.approve_request/reject_request), but only offered
	// here at all when a Pending Approval row is selected for convenience.
	const checked = (report.get_checked_items && report.get_checked_items()) || [];
	const pending = checked.filter((r) => r.status === "Pending Approval");

	if (!pending.length) {
		frappe.msgprint(__("Check one or more Pending Approval rows first."));
		return;
	}

	const fields = [
		{
			fieldname: "note",
			fieldtype: "HTML",
			options: `<p>${__("{0} {1} request(s)?", [action === "approve" ? __("Approve") : __("Reject"), pending.length])}</p>`,
		},
	];
	if (action === "reject") {
		fields.push({ fieldname: "remarks", fieldtype: "Small Text", label: __("Rejection Remarks") });
	}

	frappe.prompt(fields, (values) => {
		const method =
			action === "approve"
				? "transport_logistics.transport_logistics.manager_approval.approve_request"
				: "transport_logistics.transport_logistics.manager_approval.reject_request";

		frappe.run_serially(
			pending.map((row) => () =>
				frappe.call({
					method: method,
					args: {
						doctype: row.reference_doctype,
						name: row.reference_name,
						remarks: values.remarks,
					},
				})
			)
		).then(() => {
			frappe.show_alert({ message: __("Done"), indicator: "green" });
			report.refresh();
		});
	}, __(action === "approve" ? "Approve Requests" : "Reject Requests"), __("Submit"));
}
