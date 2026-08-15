// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Authority to Load", {
	setup(frm) {
		frm.set_query("truck_trip", () => ({
			filters: { truck: frm.doc.truck, status: "Planned" },
		}));
	},

	refresh(frm) {
		if (!frm.is_new() && frm.doc.docstatus === 0) {
			frm.dashboard.add_indicator(
				frm.doc.all_checks_passed
					? __("All compliance checks passed")
					: __("Compliance checks failed — see Failure Reason(s)"),
				frm.doc.all_checks_passed ? "green" : "red"
			);
		}
		if (frm.doc.docstatus === 1) {
			frm.dashboard.add_indicator(__("Authority Issued"), "green");
		}
	},
});
