// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.query_reports["Fuel Tank Reconciliation"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "tank",
			label: __("Fuel Tank"),
			fieldtype: "Link",
			options: "Fuel Tank",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "only_variance",
			label: __("Only Show Tanks With Variance"),
			fieldtype: "Check",
			description: __("Variance = actual stock balance vs. expected balance (opening + purchased - dispensed). Non-zero can indicate leakage, theft, or unrecorded transactions."),
		},
	],
};
