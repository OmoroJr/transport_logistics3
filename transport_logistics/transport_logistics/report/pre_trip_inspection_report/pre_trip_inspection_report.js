// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.query_reports["Pre Trip Inspection Report"] = {
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
			fieldname: "overall_status",
			label: __("Overall Status"),
			fieldtype: "Select",
			options: "\nPass\nFail",
		},
		{
			fieldname: "only_submitted",
			label: __("Only Submitted"),
			fieldtype: "Check",
			default: 1,
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

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "overall_status") {
			const colors = { Pass: "var(--green-600)", Fail: "var(--red-600)" };
			value = `<span style="color: ${colors[data.overall_status] || "inherit"}; font-weight: 600;">${value}</span>`;
		}

		if (column.fieldname === "tyre_pressure_issues" && data.tyre_pressure_issues) {
			value = `<span style="color: var(--orange-600);">${value}</span>`;
		}

		return value;
	},
};
