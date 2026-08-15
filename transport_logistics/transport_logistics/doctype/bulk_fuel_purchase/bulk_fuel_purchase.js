// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bulk Fuel Purchase", {
	qty_litres(frm) { calc_total(frm); },
	rate_per_litre(frm) { calc_total(frm); },

	refresh(frm) {
		if (!frm.is_new() && frm.doc.stock_entry) {
			frm.add_custom_button(__("View Stock Entry"), () => {
				frappe.set_route("Form", "Stock Entry", frm.doc.stock_entry);
			});
		}
	},
});

function calc_total(frm) {
	frm.set_value("total_amount", (frm.doc.qty_litres || 0) * (frm.doc.rate_per_litre || 0));
}
