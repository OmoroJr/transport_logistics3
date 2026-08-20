// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Tyre Depth Inspection", {
	setup(frm) {
		frm.set_query("tyre", () => ({
			filters: { status: ["!=", "Scrapped"] },
		}));
	},

	tread_depth_mm(frm) { preview_status(frm); },
	minimum_required_mm(frm) { preview_status(frm); },

	refresh(frm) {
		if (frm.doc.status === "Fail") {
			frm.dashboard.set_headline_alert(
				__("This tyre failed its depth inspection and will be flagged for replacement on submit."),
				"red"
			);
		} else if (frm.doc.status === "Marginal") {
			frm.dashboard.set_headline_alert(
				__("Tread depth is marginal \u2014 close to the minimum. Worth planning a replacement soon."),
				"orange"
			);
		}
	},
});

function preview_status(frm) {
	// Client-side mirror of compute_status() in the controller, purely for
	// immediate visual feedback before save — the server value is authoritative.
	if (!frm.doc.tread_depth_mm || !frm.doc.minimum_required_mm) return;

	let status;
	if (frm.doc.tread_depth_mm <= frm.doc.minimum_required_mm) {
		status = "Fail";
	} else if (frm.doc.tread_depth_mm <= frm.doc.minimum_required_mm * 1.2) {
		status = "Marginal";
	} else {
		status = "Pass";
	}
	frm.set_value("status", status);
}
