// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

const TYRE_POSITIONS =
	"\nFront Left\nFront Right\nRear Left Outer\nRear Left Inner\nRear Right Outer\nRear Right Inner\nSpare";

frappe.ui.form.on("Tyre", {
	refresh(frm) {
		if (frm.doc.__islocal) return;

		if (frm.doc.status === "In Stock" || frm.doc.status === "Retreaded") {
			frm.add_custom_button(__("Fit to Truck"), () => {
				const dialog = new frappe.ui.Dialog({
					title: __("Fit Tyre {0} to a Truck", [frm.doc.name]),
					fields: [
						{
							fieldtype: "Link",
							fieldname: "truck",
							label: __("Truck"),
							options: "Truck",
							reqd: 1,
						},
						{
							fieldtype: "Select",
							fieldname: "position",
							label: __("Position"),
							options: TYRE_POSITIONS,
							reqd: 1,
						},
						{
							fieldtype: "Date",
							fieldname: "date",
							label: __("Date"),
							default: frappe.datetime.get_today(),
							reqd: 1,
						},
						{
							fieldtype: "Float",
							fieldname: "odometer_reading",
							label: __("Truck Odometer Reading (Km)"),
							description: __("Used as the baseline to track Km run on this tyre."),
						},
					],
					primary_action_label: __("Fit"),
					primary_action(values) {
						frappe.call({
							method:
								"transport_logistics.transport_logistics.doctype.tyre_movement_log.tyre_movement_log.create_fitment",
							args: {
								tyre: frm.doc.name,
								truck: values.truck,
								position: values.position,
								date: values.date,
								odometer_reading: values.odometer_reading,
							},
							freeze: true,
							callback() {
								dialog.hide();
								frm.reload_doc();
								frappe.show_alert({
									message: __("Tyre fitted to truck."),
									indicator: "green",
								});
							},
						});
					},
				});
				dialog.show();
			}).addClass("btn-primary");
		}

		if (frm.doc.status === "Fitted") {
			frm.dashboard.add_indicator(
				__("Fitted: {0} — {1}", [frm.doc.current_truck, frm.doc.current_position]),
				"green"
			);

			frm.add_custom_button(__("Remove from Truck"), () => {
				const dialog = new frappe.ui.Dialog({
					title: __("Remove Tyre {0} from {1}", [frm.doc.name, frm.doc.current_truck]),
					fields: [
						{
							fieldtype: "Date",
							fieldname: "date",
							label: __("Date"),
							default: frappe.datetime.get_today(),
							reqd: 1,
						},
						{
							fieldtype: "Float",
							fieldname: "odometer_reading",
							label: __("Truck Odometer Reading (Km)"),
							description: __(
								"Used to calculate total Km run on this tyre since it was fitted."
							),
						},
						{
							fieldtype: "Small Text",
							fieldname: "remarks",
							label: __("Remarks"),
						},
					],
					primary_action_label: __("Remove"),
					primary_action(values) {
						frappe.call({
							method:
								"transport_logistics.transport_logistics.doctype.tyre_movement_log.tyre_movement_log.create_removal",
							args: {
								tyre: frm.doc.name,
								date: values.date,
								odometer_reading: values.odometer_reading,
								remarks: values.remarks,
							},
							freeze: true,
							callback() {
								dialog.hide();
								frm.reload_doc();
								frappe.show_alert({
									message: __("Tyre removed from truck."),
									indicator: "green",
								});
							},
						});
					},
				});
				dialog.show();
			});
		}

		frm.add_custom_button(
			__("Movement History"),
			() => {
				frappe.set_route("List", "Tyre Movement Log", { tyre: frm.doc.name });
			},
			__("View")
		);
	},
});
