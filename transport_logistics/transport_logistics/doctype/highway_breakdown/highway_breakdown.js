// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Highway Breakdown", {
	repair_cost(frm) { calc_cost(frm); },
	towing_cost(frm) { calc_cost(frm); },
	other_cost(frm) { calc_cost(frm); },

	refresh(frm) {
		if (frm.doc.status && frm.doc.status !== "Resolved") {
			frm.dashboard.set_headline_alert(
				__("Truck {0} is currently down on the highway — Status: {1}", [
					frm.doc.truck,
					frm.doc.status,
				]),
				"red"
			);
		}

		if (frm.doc.docstatus === 0 && !frm.doc.__islocal) {
			frm.dashboard.add_indicator(
				__(
					frm.doc.status === "Resolved"
						? "Ready to submit"
						: "Draft — update Status as recovery progresses, submit once Resolved"
				),
				frm.doc.status === "Resolved" ? "green" : "orange"
			);
		}
	},
});

function calc_cost(frm) {
	const total =
		(frm.doc.repair_cost || 0) + (frm.doc.towing_cost || 0) + (frm.doc.other_cost || 0);
	frm.set_value("total_cost", total);
}
