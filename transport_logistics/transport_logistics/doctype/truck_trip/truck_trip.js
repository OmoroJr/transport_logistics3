// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Truck Trip", {
	setup(frm) {
		frm.set_query("sales_order", () => {
			if (!frm.doc.customer) {
				return {};
			}
			return { filters: { customer: frm.doc.customer, docstatus: 1 } };
		});
	},

	start_odometer(frm) { calc_distance(frm); },
	end_odometer(frm) { calc_distance(frm); },

	customer(frm) {
		// Changing customer invalidates any previously-linked Sales Order for a different customer
		if (frm.doc.sales_order) {
			frappe.db.get_value("Sales Order", frm.doc.sales_order, "customer").then((r) => {
				if (r.message && r.message.customer !== frm.doc.customer) {
					frm.set_value("sales_order", "");
				}
			});
		}
	},

	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.status === "Planned") {
			frm.add_custom_button(__("Request Authority to Load"), () => {
				frappe.new_doc("Authority to Load", { truck: frm.doc.truck, truck_trip: frm.doc.name });
			});
		}

		if (frm.doc.status === "Ongoing" && frm.doc.offload_status === "Not Offloaded") {
			frm.add_custom_button(__("Offload at Client"), () => {
				const dialog = new frappe.ui.Dialog({
					title: __("Offload Truck at Client Premises"),
					fields: [
						{
							fieldtype: "Float",
							fieldname: "offload_odometer",
							label: __("Odometer Reading at Offload (Km)"),
							default: frm.doc.start_odometer || null,
						},
						{
							fieldtype: "Link",
							fieldname: "offloaded_by",
							label: __("Confirmed By"),
							options: "Employee",
						},
					],
					primary_action_label: __("Confirm Offload"),
					primary_action(values) {
						frappe.call({
							method: "transport_logistics.transport_logistics.doctype.truck_trip.truck_trip.offload_truck",
							args: {
								trip_name: frm.doc.name,
								offload_odometer: values.offload_odometer,
								offloaded_by: values.offloaded_by,
							},
							freeze: true,
							callback() {
								dialog.hide();
								frm.reload_doc();
								frappe.show_alert({
									message: __("Truck offloaded — trip completed and truck is now available."),
									indicator: "green",
								});
							},
						});
					},
				});
				dialog.show();
			}).addClass("btn-primary");

			frm.dashboard.add_indicator(__("Loaded — En Route to {0}", [frm.doc.destination || "client"]), "orange");
		} else if (frm.doc.offload_status === "Offloaded") {
			frm.dashboard.add_indicator(__("Offloaded — Empty"), "green");
		}
	},
});

function calc_distance(frm) {
	if (frm.doc.start_odometer && frm.doc.end_odometer) {
		frm.set_value("distance_km", frm.doc.end_odometer - frm.doc.start_odometer);
	}
}
