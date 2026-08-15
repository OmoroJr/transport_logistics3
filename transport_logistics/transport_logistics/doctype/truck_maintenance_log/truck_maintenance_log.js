frappe.ui.form.on("Truck Maintenance Log", {
	parts_cost(frm) { calc_total(frm); },
	labour_cost(frm) { calc_total(frm); },
	other_cost(frm) { calc_total(frm); },
});

function calc_total(frm) {
	frm.set_value(
		"total_cost",
		(frm.doc.parts_cost || 0) + (frm.doc.labour_cost || 0) + (frm.doc.other_cost || 0)
	);
}
