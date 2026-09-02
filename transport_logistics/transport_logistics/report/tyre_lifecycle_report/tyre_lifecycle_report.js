// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.query_reports["Tyre Lifecycle Report"] = {
	filters: [
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nIn Stock\nFitted\nRetreaded\nScrapped",
		},
		{
			fieldname: "brand",
			label: __("Brand"),
			fieldtype: "Data",
		},
		{
			fieldname: "current_vehicle_type",
			label: __("Current Vehicle Type"),
			fieldtype: "Select",
			options: "\nTruck\nTrailer",
		},
		{
			fieldname: "current_truck",
			label: __("Current Truck"),
			fieldtype: "Link",
			options: "Truck",
		},
		{
			fieldname: "current_trailer",
			label: __("Current Trailer"),
			fieldtype: "Link",
			options: "Trailer",
		},
		{
			fieldname: "only_flagged",
			label: __("Only Flagged for Replacement"),
			fieldtype: "Check",
		},
	],
};
