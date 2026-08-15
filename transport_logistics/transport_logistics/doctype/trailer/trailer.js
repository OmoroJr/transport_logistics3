// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Trailer", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("New Coupling Log"), () => {
				frappe.new_doc("Trailer Coupling Log", { trailer: frm.doc.name });
			}, __("Create"));

			if (frm.doc.current_truck) {
				frm.dashboard.add_indicator(
					__("Coupled to: {0}", [frm.doc.current_truck]),
					"blue"
				);
			} else {
				frm.dashboard.add_indicator(__("Not currently coupled"), "grey");
			}
		}
	},
});
