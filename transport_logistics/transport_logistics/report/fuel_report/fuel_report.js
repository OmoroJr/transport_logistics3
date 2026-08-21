// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.query_reports["Fuel Report"] = {
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
			fieldname: "driver",
			label: __("Driver"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "route",
			label: __("Route"),
			fieldtype: "Link",
			options: "Route",
		},
		{
			fieldname: "reason_for_fuelling",
			label: __("Reason for Fuelling"),
			fieldtype: "Select",
			options: "\nFor Trip\nYard / Standby\nGenerator\nOther",
		},
		{
			fieldname: "source",
			label: __("Source"),
			fieldtype: "Select",
			options: "\nExternal Purchase\nInternal Bulk Dispensing",
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
			fieldname: "only_extra_fuel",
			label: __("Only Show Extra Fuel (Over Route Standard)"),
			fieldtype: "Check",
		},
		{
			fieldname: "include_unsubmitted",
			label: __("Include Draft / Cancelled Logs"),
			fieldtype: "Check",
			description: __("By default only submitted fuel logs are included."),
		},
	],
};
