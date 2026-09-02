// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.query_reports["Highway Breakdown Analysis"] = {
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
			fieldname: "breakdown_type",
			label: __("Breakdown Type"),
			fieldtype: "Select",
			options: "\nEngine\nTyre / Puncture\nElectrical\nBrakes\nTransmission\nFuel System\nCooling System\nSuspension\nOther",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nReported\nRecovery Dispatched\nUnder Repair (Roadside)\nTowed to Workshop\nResolved",
		},
		{
			fieldname: "preventable",
			label: __("Only Show Preventable Breakdowns"),
			fieldtype: "Check",
		},
		{
			fieldname: "towed",
			label: __("Only Show Towed"),
			fieldtype: "Check",
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
			fieldname: "include_unsubmitted",
			label: __("Include Draft / Cancelled Reports"),
			fieldtype: "Check",
			description: __("By default only submitted breakdown reports are included."),
		},
	],
};
