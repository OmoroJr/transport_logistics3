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

		if (frm.doc.status === "Planned" && frm.doc.trip_type !== "Empty Return to Depot") {
			frm.add_custom_button(__("Request Authority to Load"), () => {
				frappe.new_doc("Authority to Load", { truck: frm.doc.truck, truck_trip: frm.doc.name });
			});

			if (!frm.doc.pre_trip_inspection) {
				frm.add_custom_button(__("Create Pre-Trip Inspection"), () => {
					frappe.new_doc("Trip Pre Inspection", { truck: frm.doc.truck, truck_trip: frm.doc.name });
				});
			}
		} else if (frm.doc.status === "Planned") {
			if (!frm.doc.pre_trip_inspection) {
				frm.add_custom_button(__("Create Pre-Trip Inspection"), () => {
					frappe.new_doc("Trip Pre Inspection", { truck: frm.doc.truck, truck_trip: frm.doc.name });
				});
			}
		}

		if (
			frm.doc.status === "Ongoing" &&
			frm.doc.offload_status === "Not Offloaded" &&
			frm.doc.trip_type === "Empty Return to Depot"
		) {
			frm.add_custom_button(__("Return Empty Container to Depot"), () => {
				const planned_depot = frm.doc.planned_depot || frm.doc.destination || null;

				const dialog = new frappe.ui.Dialog({
					title: __("Confirm Empty Container Returned to Depot"),
					fields: [
						{
							fieldtype: "HTML",
							fieldname: "planned_depot_reference",
							options: `<div class="text-muted" style="margin-bottom: 10px;">${__(
								"Planned Depot / Yard"
							)}: <strong>${planned_depot || __("(not set)")}</strong></div>`,
						},
						{
							fieldtype: "Float",
							fieldname: "offload_odometer",
							label: __("Odometer Reading at Return (Km)"),
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
							fieldname: "depot",
							label: __("Actual Depot / Yard"),
							description: __(
								"Where the container was actually handed back. Defaults to the planned depot above — change it if the driver was redirected elsewhere."
							),
							default: planned_depot,
							reqd: 1,
						},
						{
							fieldtype: "Small Text",
							fieldname: "depot_change_reason",
							label: __("Reason for Depot Change"),
							description: __(
								"Required only if Actual Depot / Yard above is different from the Planned Depot / Yard."
							),
							depends_on: () => planned_depot && dialog.get_value("depot") &&
								dialog.get_value("depot").trim().toLowerCase() !== planned_depot.trim().toLowerCase(),
						},
						{
							fieldtype: "Data",
							fieldname: "interchange_no",
							label: __("Interchange Number"),
							description: __(
								"Transcribe this from the interchange receipt issued at the depot/CFS confirming the empty container was accepted back."
							),
							reqd: 1,
						},
						{
							fieldtype: "Date",
							fieldname: "interchange_date",
							label: __("Interchange Date"),
							default: frappe.datetime.get_today(),
						},
						{
							fieldtype: "Attach",
							fieldname: "interchange_receipt",
							label: __("Interchange Receipt"),
							description: __(
								"Optional: photo or scan of the interchange receipt issued at the depot/CFS."
							),
						},
					],
					primary_action_label: __("Confirm Return"),
					primary_action(values) {
						const depot_changed =
							planned_depot &&
							values.depot &&
							values.depot.trim().toLowerCase() !== planned_depot.trim().toLowerCase();
						if (depot_changed && !values.depot_change_reason) {
							frappe.msgprint(
								__(
									"Actual Depot / Yard is different from the Planned Depot / Yard — a Reason for Depot Change is required."
								)
							);
							return;
						}

						frappe.call({
							method: "transport_logistics.transport_logistics.doctype.truck_trip.truck_trip.return_empty_container",
							args: {
								trip_name: frm.doc.name,
								offload_odometer: values.offload_odometer,
								offloaded_by: values.offloaded_by,
								depot: values.depot,
								depot_change_reason: values.depot_change_reason,
								interchange_no: values.interchange_no,
								interchange_date: values.interchange_date,
								interchange_receipt: values.interchange_receipt,
							},
							freeze: true,
							callback() {
								dialog.hide();
								frm.reload_doc();
								frappe.show_alert({
									message: __("Empty container returned — trip completed and truck is now available."),
									indicator: "green",
								});
							},
						});
					},
				});
				dialog.show();
			}).addClass("btn-primary");

			frm.dashboard.add_indicator(__("Empty — En Route to Depot {0}", [frm.doc.destination || ""]), "orange");
			if (frm.doc.driver_mileage_payment) {
				frm.dashboard.add_indicator(__("Driver Allowance: {0}", [frm.doc.driver_mileage_payment]), "blue");
			} else if (frm.doc.driver && !frm.doc.route) {
				frm.dashboard.add_indicator(__("No Driver Allowance — trip has no Route"), "grey");
			}
		} else if (frm.doc.status === "Ongoing" && frm.doc.offload_status === "Not Offloaded") {
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
			if (frm.doc.driver_mileage_payment) {
				frm.dashboard.add_indicator(__("Driver Allowance: {0}", [frm.doc.driver_mileage_payment]), "blue");
			} else if (frm.doc.driver && !frm.doc.route) {
				frm.dashboard.add_indicator(__("No Driver Allowance — trip has no Route"), "grey");
			}
		} else if (frm.doc.offload_status === "Offloaded" && frm.doc.trip_type === "Empty Return to Depot") {
			frm.dashboard.add_indicator(
				__("Returned — Interchange # {0}", [frm.doc.interchange_no || "—"]),
				"green"
			);
			if (frm.doc.depot_changed) {
				frm.dashboard.add_indicator(
					__("Returned to {0} instead of planned {1}", [frm.doc.depot || "—", frm.doc.planned_depot || "—"]),
					"yellow"
				);
			}
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
