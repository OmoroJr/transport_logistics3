// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.query_reports["Trailer Utilization"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "trailer",
			label: __("Trailer"),
			fieldtype: "Link",
			options: "Trailer",
		},
		{
			fieldname: "trailer_type",
			label: __("Trailer Type"),
			fieldtype: "Select",
			options: "\nTipper\nFlatbed\nLow Loader\nCurtain Sider\nTanker\nSkeletal\nReefer\nOther",
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
	],
};
