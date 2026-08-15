frappe.ui.form.on("Accident Report", {
	repair_cost(frm) { calc_cost(frm); },
	other_cost(frm) { calc_cost(frm); },
	claim_amount_recovered(frm) { calc_cost(frm); },
	refresh(frm) {
		if (frm.doc.severity === "Fatal" || frm.doc.severity === "Major") {
			frm.dashboard.set_headline_alert(
				__("High severity accident — ensure this is escalated and the Truck's compliance status is reviewed."),
				"red"
			);
		}
	},
});

function calc_cost(frm) {
	let total = (frm.doc.repair_cost || 0) + (frm.doc.other_cost || 0);
	frm.set_value("total_cost", total);
	frm.set_value("net_cost", total - (frm.doc.claim_amount_recovered || 0));
}
