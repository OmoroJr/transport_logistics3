// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Workshop", {
	refresh(frm) {
		if (frm.is_new()) return;

		frappe.call({
			method: "transport_logistics.transport_logistics.doctype.workshop.workshop.get_bay_occupancy",
			args: { workshop: frm.doc.name },
			callback: (r) => {
				if (!r.message) return;
				const { bay_count, active_jobs } = r.message;
				const color = !bay_count ? "grey" : active_jobs >= bay_count ? "red" : active_jobs > 0 ? "orange" : "green";
				frm.dashboard.add_indicator(
					__("Bays in use: {0} / {1}", [active_jobs, bay_count || "?"]),
					color
				);
			},
		});

		frm.add_custom_button(__("New Workshop Job Card"), () => {
			frappe.new_doc("Workshop Job Card", { workshop: frm.doc.name });
		}, __("Create"));
	},
});
