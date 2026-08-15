// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Truck", {
	status(frm) {
		if (frm.doc.status === "Active" && !frm.doc.assigned_driver) {
			frappe.msgprint(__("A driver must be assigned before this truck can be set to Active."));
		}
	},

	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button("Cost Analysis", () => {
				frappe.set_route("query-report", "Truck Cost Analysis", { truck: frm.doc.name });
			});
			frm.add_custom_button("New Fuel Log", () => {
				frappe.new_doc("Truck Fuel Log", { truck: frm.doc.name });
			}, "Create");
			frm.add_custom_button("New Maintenance Log", () => {
				frappe.new_doc("Truck Maintenance Log", { truck: frm.doc.name });
			}, "Create");
			frm.add_custom_button("New Trip", () => {
				frappe.new_doc("Truck Trip", { truck: frm.doc.name });
			}, "Create");
			frm.add_custom_button("New Accident Report", () => {
				frappe.new_doc("Accident Report", { truck: frm.doc.name });
			}, "Create");
			frm.add_custom_button("New Job Card", () => {
				frappe.new_doc("Workshop Job Card", { truck: frm.doc.name });
			}, "Create");
			frm.add_custom_button("New Mileage Payment", () => {
				frappe.new_doc("Driver Mileage Payment", {
					truck: frm.doc.name,
					driver: frm.doc.assigned_driver,
				});
			}, "Create");
			frm.add_custom_button("New Gate Pass", () => {
				frappe.new_doc("Gate Pass", { pass_type: "Vehicle", truck: frm.doc.name });
			}, "Create");
			frm.add_custom_button("Couple/Decouple Trailer", () => {
				frappe.new_doc("Trailer Coupling Log", { truck: frm.doc.name });
			}, "Create");

			frm.add_custom_button("Utilization Report", () => {
				frappe.set_route("query-report", "Truck Utilization", { truck: frm.doc.name });
			});
			frm.add_custom_button("Fleet Dashboard", () => {
				frappe.set_route("dashboard-view", "Transport Logistics");
			});
			frm.add_custom_button("Cost Dashboard (this truck)", () => {
				frappe.route_options = { truck: frm.doc.name };
				frappe.set_route("truck-cost-dashboard");
			});

			if (frm.doc.current_trailer) {
				frm.dashboard.add_indicator(
					__("Trailer coupled: {0}", [frm.doc.current_trailer]),
					"blue"
				);
			}

			frm.dashboard.add_indicator(
				__("Current Odometer: {0} km", [frm.doc.current_odometer || 0]),
				"blue"
			);

			if (frm.doc.enable_gps_tracking) {
				if (frm.doc.last_gps_update) {
					frm.dashboard.add_indicator(
						__("GPS last updated: {0}", [frappe.datetime.prettyDate(frm.doc.last_gps_update)]),
						"green"
					);
				} else {
					frm.dashboard.add_indicator(__("GPS: no position received yet"), "orange");
				}

				frm.add_custom_button(__("Sync GPS Now"), () => {
					frappe.show_alert({ message: __("Syncing GPS position..."), indicator: "blue" });
					frappe.call({
						method: "transport_logistics.transport_logistics.gps_tracking.sync_now",
						args: { truck: frm.doc.name },
						callback: () => frm.reload_doc(),
					});
				});

				if (frm.doc.last_latitude && frm.doc.last_longitude) {
					frm.add_custom_button(__("View on Map"), () => {
						window.open(
							`https://www.google.com/maps?q=${frm.doc.last_latitude},${frm.doc.last_longitude}`,
							"_blank"
						);
					});
				}
			}
		}
	},
});
