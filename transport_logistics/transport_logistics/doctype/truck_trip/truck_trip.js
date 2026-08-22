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

		frm.set_query("delivery_note", () => {
			const filters = { docstatus: 1 };
			if (frm.doc.customer) filters.customer = frm.doc.customer;
			return { filters };
		});

		frm.set_query("pre_trip_fuel_log", () => {
			const filters = { docstatus: 1, full_tank: 1 };
			if (frm.doc.truck) filters.truck = frm.doc.truck;
			if (frm.doc.trip_date) filters.date = ["<=", frm.doc.trip_date];
			return { filters };
		});

		frm.set_query("pre_trip_inspection", () => {
			const filters = { docstatus: 1, overall_status: "Pass" };
			if (frm.doc.truck) filters.truck = frm.doc.truck;
			if (!frm.is_new()) filters.truck_trip = frm.doc.name;
			return { filters };
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

		transport_logistics.manager_approval.add_buttons(frm);

		if (frm.doc.status === "Planned") {
			frm.add_custom_button(__("Request Authority to Load"), () => {
				frappe.new_doc("Authority to Load", { truck: frm.doc.truck, truck_trip: frm.doc.name });
			});

			if (!frm.doc.pre_trip_inspection) {
				frm.add_custom_button(__("Create Pre-Trip Inspection"), () => {
					frappe.new_doc("Trip Pre Inspection", { truck: frm.doc.truck, truck_trip: frm.doc.name });
				});
			}
		}

		if (frm.doc.status === "Ongoing" && frm.doc.offload_status === "Not Offloaded") {
			frm.add_custom_button(__("Offload at Client"), () => {
				if (!frm.doc.delivery_note) {
					frappe.msgprint(
						__(
							"This trip has no Delivery Note on file. It's normally generated automatically from the Sales Order when the trip starts — if there's no Sales Order linked, add a Delivery Note manually before offloading."
						)
					);
					return;
				}

				const dialog = new frappe.ui.Dialog({
					title: __("Offload Truck at Client Premises"),
					fields: [
						{
							fieldtype: "HTML",
							fieldname: "delivery_note_reference",
							options: `<div class="text-muted" style="margin-bottom: 10px;">${__(
								"Delivery Note issued to the driver at departure"
							)}: <strong>${frm.doc.delivery_note}</strong></div>`,
						},
						{
							fieldtype: "Float",
							fieldname: "offload_odometer",
							label: __("Odometer Reading at Offload (Km)"),
							default: frm.doc.start_odometer || null,
							reqd: 1,
						},
						{
							fieldtype: "Link",
							fieldname: "offloaded_by",
							label: __("Confirmed By"),
							options: "Employee",
							reqd: 1,
						},
						{
							fieldtype: "Data",
							fieldname: "delivery_number",
							label: __("Delivery Number"),
							description: __(
								"Transcribe this from the physical Delivery Note the driver is returning with — it must match the Delivery Note shown above."
							),
							reqd: 1,
						},
						{
							fieldtype: "Attach",
							fieldname: "proof_of_delivery",
							label: __("Proof of Delivery"),
							description: __(
								"Photo or scan of the signed delivery note confirming the client received the load."
							),
							reqd: 1,
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
								delivery_number: values.delivery_number,
								proof_of_delivery: values.proof_of_delivery,
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
			frm.dashboard.add_indicator(
				__("Offloaded — Empty · Delivery # {0}", [frm.doc.delivery_number || "—"]),
				"green"
			);

			if (frm.doc.pod_authenticated) {
				frm.dashboard.add_indicator(
					__("POD Authenticated by {0}", [frm.doc.pod_authenticated_by]),
					"green"
				);
			} else {
				frm.dashboard.add_indicator(__("POD Pending Authentication"), "orange");
				frm.add_custom_button(__("Authenticate Proof of Delivery"), () => {
					frappe.confirm(
						__(
							"Confirm you have independently verified the scanned document at {0} against Delivery Number {1} and it is genuine?",
							[frm.doc.proof_of_delivery, frm.doc.delivery_number]
						),
						() => {
							frappe.call({
								method: "transport_logistics.transport_logistics.doctype.truck_trip.truck_trip.authenticate_pod",
								args: { trip_name: frm.doc.name },
								freeze: true,
								callback() {
									frm.reload_doc();
									frappe.show_alert({
										message: __("Proof of Delivery authenticated."),
										indicator: "green",
									});
								},
							});
						}
					);
				});
			}
		}
	},
});

function calc_distance(frm) {
	if (frm.doc.start_odometer && frm.doc.end_odometer) {
		frm.set_value("distance_km", frm.doc.end_odometer - frm.doc.start_odometer);
	}
}
