frappe.ui.form.on("Trailer Coupling Log", {
	trailer(frm) {
		if (frm.doc.trailer && frm.is_new()) {
			frappe.db.get_value("Trailer", frm.doc.trailer, "current_truck").then((r) => {
				if (r.message && r.message.current_truck) {
					frm.set_value("action", "Decoupled");
					frm.set_value("truck", r.message.current_truck);
				} else {
					frm.set_value("action", "Coupled");
				}
			});
		}
	},
});
