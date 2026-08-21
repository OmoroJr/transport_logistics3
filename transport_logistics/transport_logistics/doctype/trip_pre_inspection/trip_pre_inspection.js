// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Trip Pre Inspection", {
	refresh(frm) {
		if (frm.doc.overall_status === "Fail") {
			frm.dashboard.set_headline_alert(
				__("This inspection failed — the truck cannot depart on a new trip until a passing inspection is on file."),
				"red"
			);
		}
	},
});

frappe.ui.form.on("Trip Pre Inspection Item", {
	status(frm, cdt, cdn) {
		// Purely a client-side nudge -- the server enforces this same
		// requirement in validate_items() regardless of what happens here.
		const row = frappe.get_doc(cdt, cdn);
		if (row.status === "Not OK" && !row.remarks) {
			frappe.show_alert({
				message: __("Add a Remarks note describing the fault for this item."),
				indicator: "orange",
			});
		}
	},
});
