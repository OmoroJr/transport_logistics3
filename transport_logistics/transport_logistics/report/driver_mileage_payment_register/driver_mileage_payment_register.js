// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.query_reports["Driver Mileage Payment Register"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "driver",
			label: __("Driver"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "truck",
			label: __("Truck"),
			fieldtype: "Link",
			options: "Truck",
		},
		{
			fieldname: "payment_method",
			label: __("Payment Method"),
			fieldtype: "Select",
			options: "\nCash\nM-Pesa\nBank Transfer",
		},
		{
			fieldname: "payment_status",
			label: __("Payment Status"),
			fieldtype: "Select",
			options: "\nUnpaid\nProcessing\nPaid\nFailed",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			description: __("Filters on the payment's covered period (From Date / To Date fields)."),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "include_unsubmitted",
			label: __("Include Draft / Cancelled Payments"),
			fieldtype: "Check",
			description: __("By default only submitted payments are included."),
		},
	],
};
