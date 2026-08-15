// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(
				__("New Mileage Payment"),
				() => {
					frappe.new_doc("Driver Mileage Payment", { driver: frm.doc.name });
				},
				__("Create")
			);
		}
	},
});
