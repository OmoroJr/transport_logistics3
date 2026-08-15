// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Gate Pass", {
	pass_type(frm) {
		// Clear out the fields that don't apply to the newly selected type,
		// so a half-filled Vehicle pass doesn't linger if switched to Pedestrian.
		if (frm.doc.pass_type === "Pedestrian") {
			frm.set_value("truck", "");
			frm.set_value("trailer", "");
			frm.set_value("driver", "");
			frm.set_value("odometer_out", "");
			frm.set_value("cargo_description", "");
			frm.set_value("seal_number", "");
		} else if (frm.doc.pass_type === "Vehicle") {
			frm.set_value("visitor_name", "");
			frm.set_value("id_number", "");
			frm.set_value("phone_number", "");
			frm.set_value("host_employee", "");
		}
	},

	refresh(frm) {
		if (!frm.is_new() && frm.doc.status === "In Yard") {
			frm.add_custom_button(__("Gate Out"), () => {
				frm.set_value("gate_out_time", frappe.datetime.now_datetime());
				frm.save();
			});
			frm.dashboard.add_indicator(__("In Yard"), "orange");
		} else if (!frm.is_new() && frm.doc.status === "Departed") {
			frm.dashboard.add_indicator(__("Departed"), "green");
		}
	},
});
