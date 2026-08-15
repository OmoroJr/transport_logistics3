// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.query_reports["Tyre Replacement Due"] = {
	filters: [
		{
			fieldname: "truck",
			label: __("Truck"),
			fieldtype: "Link",
			options: "Truck",
		},
		{
			fieldname: "status",
			label: __("Tyre Status"),
			fieldtype: "Select",
			options: "\nFitted\nIn Stock",
		},
		{
			fieldname: "threshold_percent",
			label: __("Show Tyres Above % Life Used"),
			fieldtype: "Int",
			default: 80,
		},
	],
};
