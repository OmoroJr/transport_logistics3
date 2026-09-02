// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.query_reports["Accident Report Register"] = {
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
			fieldname: "severity",
			label: __("Severity"),
			fieldtype: "Select",
			options: "\nMinor\nModerate\nMajor\nFatal",
		},
		{
			fieldname: "accident_type",
			label: __("Accident Type"),
			fieldtype: "Select",
			options: "\nCollision\nRollover\nFire\nTheft\nMechanical Failure\nOther",
		},
		{
			fieldname: "at_fault",
			label: __("At Fault"),
			fieldtype: "Select",
			options: "\nDriver\nThird Party\nMechanical\nUndetermined",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nReported\nUnder Investigation\nClosed",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -3),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "only_with_injuries",
			label: __("Only Show Accidents With Injuries or Fatalities"),
			fieldtype: "Check",
		},
		{
			fieldname: "include_unsubmitted",
			label: __("Include Draft / Cancelled Reports"),
			fieldtype: "Check",
			description: __("By default only submitted accident reports are included."),
		},
	],
};
