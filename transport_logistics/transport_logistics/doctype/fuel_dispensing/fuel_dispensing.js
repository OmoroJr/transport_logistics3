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

	setup(frm) {
		frm.set_query("truck_trip", () => ({
			filters: { truck: frm.doc.truck || "" },
		}));
		frm.set_query("authority_to_load", () => ({
			filters: {
				truck: frm.doc.truck || "",
				truck_trip: frm.doc.truck_trip || "",
				docstatus: 1,
				all_checks_passed: 1,
			},
		}));
	},

	truck(frm) {
		frm.set_value("truck_trip", "");
		frm.set_value("authority_to_load", "");
	},

	reason_for_fuelling(frm) {
		if (frm.doc.reason_for_fuelling !== "For Trip") {
			frm.set_value("truck_trip", "");
			frm.set_value("authority_to_load", "");
		}
	},

	truck_trip(frm) {
		frm.set_value("authority_to_load", "");
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
