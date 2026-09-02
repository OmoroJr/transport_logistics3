// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.query_reports["Shipment Register"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "client",
			label: __("Client"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "shipment_type",
			label: __("Shipment Type"),
			fieldtype: "Select",
			options: "\nImport\nExport\nTransit",
		},
		{
			fieldname: "mode_of_transport",
			label: __("Mode of Transport"),
			fieldtype: "Select",
			options: "\nSea\nAir\nRoad\nRail",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nBooked\nDocuments Received\nCustoms Entry Filed\nCustoms Released\nIn Transit\nDelivered\nCompleted\nCancelled",
		},
		{
			fieldname: "assigned_agent",
			label: __("Assigned Agent"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "assigned_truck",
			label: __("Assigned Truck"),
			fieldtype: "Link",
			options: "Truck",
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
			fieldname: "only_unbilled",
			label: __("Only Show Unbilled (No Sales Invoice)"),
			fieldtype: "Check",
		},
	],
};
