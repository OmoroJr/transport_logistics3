// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.query_reports["Tyre Replacement Due"] = {
	filters: [
		{
			fieldname: "vehicle_type",
			label: __("Vehicle Type"),
			fieldtype: "Select",
			options: "\nTruck\nTrailer",
		},
		{
			fieldname: "truck",
			label: __("Truck"),
			fieldtype: "Link",
			options: "Truck",
		},
		{
			fieldname: "trailer",
			label: __("Trailer"),
			fieldtype: "Link",
			options: "Trailer",
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
