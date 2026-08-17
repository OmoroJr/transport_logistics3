// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee", {
	refresh(frm) {
		add_expiry_indicator(frm, "driving_license_expiry_date", __("Driving License"));
		add_expiry_indicator(frm, "port_pass_expiry_date", __("Port Pass"));
	},
});

function add_expiry_indicator(frm, fieldname, label) {
	if (!frm.doc[fieldname]) return;

	const days_left = frappe.datetime.get_diff(frm.doc[fieldname], frappe.datetime.get_today());

	let indicator = "green";
	let text = __("{0} valid until {1}", [label, frm.doc[fieldname]]);

	if (days_left < 0) {
		indicator = "red";
		text = __("{0} expired {1} day(s) ago", [label, Math.abs(days_left)]);
	} else if (days_left <= 30) {
		indicator = "orange";
		text = __("{0} expires in {1} day(s)", [label, days_left]);
	}

	frm.dashboard.add_indicator(text, indicator);
}
