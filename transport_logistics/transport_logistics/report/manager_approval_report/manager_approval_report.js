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
		// Inline Approve/Reject links (rendered per-row by the formatter
		// below) are the primary action -- they don't depend on the
		// datatable's checkbox column, which isn't reliably present on
		// script reports. Delegate the click from the report's wrapper so
		// it keeps working after every refresh/re-render. report.page.wrapper
		// is a plain DOM node, not a jQuery object, so it must be wrapped
		// with $() before .on() is usable.
		$(report.page.wrapper).on("click", ".manager-approval-action", function (e) {
			e.preventDefault();
			const $el = $(this);
			const action = $el.data("action");
			const doctype = $el.data("doctype");
			const name = $el.data("name");
			handle_decision(report, action, doctype, name);
		});
	},

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "status") {
			const colors = {
				"Pending Approval": "var(--orange-600)",
				Approved: "var(--green-600)",
				Rejected: "var(--red-600)",
			};
			value = `<span style="color: ${colors[data.status] || "inherit"}; font-weight: 600;">${value}</span>`;
		}

		if (column.fieldname === "actions" && data.status === "Pending Approval") {
			const doctype = frappe.utils.escape_html(data.reference_doctype || "");
			const name = frappe.utils.escape_html(data.reference_name || "");
			value = `
				<a href="#" class="manager-approval-action" data-action="approve"
				   data-doctype="${doctype}" data-name="${name}">${__("Approve")}</a>
				&nbsp;|&nbsp;
				<a href="#" class="manager-approval-action text-danger" data-action="reject"
				   data-doctype="${doctype}" data-name="${name}">${__("Reject")}</a>
			`;
		}

		return value;
	},
};

function handle_decision(report, action, doctype, name) {
	// System Manager-only is enforced server-side in
	// manager_approval.approve_request/reject_request regardless of what
	// happens client-side here.
	if (action === "approve") {
		frappe.confirm(__("Approve this {0} request ({1})?", [doctype, name]), () => {
			call_decision(report, "approve_request", doctype, name);
		});
		return;
	}

	frappe.prompt(
		[{ fieldname: "remarks", fieldtype: "Small Text", label: __("Rejection Remarks") }],
		(values) => call_decision(report, "reject_request", doctype, name, values.remarks),
		__("Reject Request"),
		__("Reject")
	);
}

function call_decision(report, method_name, doctype, name, remarks) {
	frappe.call({
		method: `transport_logistics.transport_logistics.manager_approval.${method_name}`,
		args: { doctype, name, remarks },
		freeze: true,
		callback: function () {
			frappe.show_alert({ message: __("Done"), indicator: "green" });
			report.refresh();
		},
	});
}
