// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Tyre Movement Log", {
	refresh(frm) {
		transport_logistics.manager_approval.add_buttons(frm);
	},
});
