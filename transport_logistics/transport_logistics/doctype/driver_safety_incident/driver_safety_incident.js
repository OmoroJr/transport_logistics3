frappe.ui.form.on("Driver Safety Incident", {
	severity(frm) {
		if (!frm.doc.points_deducted) {
			const defaults = { Low: 2, Medium: 5, High: 10 };
			frm.set_value("points_deducted", defaults[frm.doc.severity] || 2);
		}
	},
});
