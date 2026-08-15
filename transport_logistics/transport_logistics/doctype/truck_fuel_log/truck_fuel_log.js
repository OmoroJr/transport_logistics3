frappe.ui.form.on("Truck Fuel Log", {
	fuel_qty_litres(frm) { calc_amount(frm); },
	rate_per_litre(frm) { calc_amount(frm); },
});

function calc_amount(frm) {
	frm.set_value("total_amount", (frm.doc.fuel_qty_litres || 0) * (frm.doc.rate_per_litre || 0));
}
