// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Fuel Dispensing", {
	onload(frm) {
		if (frm.is_new() && frm.doc.truck && !frm.doc.odometer_reading) {
			frappe.db.get_value("Truck", frm.doc.truck, "current_odometer").then((r) => {
				if (r.message && r.message.current_odometer) {
					frm.set_value("odometer_reading", r.message.current_odometer);
				}
			});
		}
	},

	tank(frm) {
		if (!frm.doc.tank) return;
		frappe.call({
			method: "transport_logistics.transport_logistics.doctype.fuel_tank.fuel_tank.get_stock_level",
			args: { tank_name: frm.doc.tank },
			callback(r) {
				if (r.message) {
					frm.dashboard.clear_headline();
					frm.dashboard.set_headline(
						__("Tank stock: {0} L available", [format_number(r.message.actual_qty, null, 1)])
					);
				}
			},
		});
	},

	refresh(frm) {
		if (!frm.is_new() && frm.doc.truck_fuel_log) {
			frm.add_custom_button(__("View Truck Fuel Log"), () => {
				frappe.set_route("Form", "Truck Fuel Log", frm.doc.truck_fuel_log);
			});
		}
		if (!frm.is_new() && frm.doc.stock_entry) {
			frm.add_custom_button(__("View Stock Entry"), () => {
				frappe.set_route("Form", "Stock Entry", frm.doc.stock_entry);
			});
		}
	},
});
