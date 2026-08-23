// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.query_reports["Visitors On Site"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "pass_type",
			label: __("Pass Type"),
			fieldtype: "Select",
			options: "\nVehicle\nPedestrian",
		},
	],
};
