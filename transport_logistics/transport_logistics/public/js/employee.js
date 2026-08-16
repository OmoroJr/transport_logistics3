// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee", {
	refresh(frm) {
		if (!frm.doc.driving_license_expiry_date) return;

		const days_left = frappe.datetime.get_diff(
			frm.doc.driving_license_expiry_date,
			frappe.datetime.get_today()
		);

		let indicator = "green";
		let label = __("Driving License valid until {0}", [frm.doc.driving_license_expiry_date]);

		if (days_left < 0) {
			indicator = "red";
			label = __("Driving License expired {0} day(s) ago", [Math.abs(days_left)]);
		} else if (days_left <= 30) {
			indicator = "orange";
			label = __("Driving License expires in {0} day(s)", [days_left]);
		}

		frm.dashboard.add_indicator(label, indicator);
	},
});
