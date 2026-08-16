// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

const SIDE_OPTIONS = "\nLeft\nRight\nLeft Outer\nLeft Inner\nRight Outer\nRight Inner";

function update_axle_description(dialog) {
	const values = dialog.get_values(true) || {};
	if (!values.vehicle_type) return;

	const vehicle = values.vehicle_type === "Truck" ? values.truck : values.trailer;
	if (!vehicle) return;

	frappe.call({
		method:
			"transport_logistics.transport_logistics.doctype.tyre_movement_log.tyre_movement_log.get_axle_config",
		args: { vehicle_type: values.vehicle_type, vehicle },
		callback(r) {
			if (!r.message) return;
			let description;
			if (values.vehicle_type === "Truck") {
				description = __("This truck has {0} front axle(s) and {1} rear axle(s).", [
					r.message.front_axle_count,
					r.message.rear_axle_count,
				]);
			} else {
				description = __("This trailer has {0} axle(s).", [r.message.axle_count]);
			}
			dialog.set_df_property("axle_number", "description", description);
		},
	});
}

frappe.ui.form.on("Tyre", {
	refresh(frm) {
		if (frm.doc.__islocal) return;

		if (frm.doc.status === "In Stock" || frm.doc.status === "Retreaded") {
			frm.add_custom_button(__("Fit to Vehicle"), () => {
				const dialog = new frappe.ui.Dialog({
					title: __("Fit Tyre {0} to a Vehicle", [frm.doc.name]),
					fields: [
						{
							fieldtype: "Select",
							fieldname: "vehicle_type",
							label: __("Vehicle Type"),
							options: "\nTruck\nTrailer",
							reqd: 1,
							onchange: () => update_axle_description(dialog),
						},
						{
							fieldtype: "Link",
							fieldname: "truck",
							label: __("Truck"),
							options: "Truck",
							depends_on: 'eval:doc.vehicle_type=="Truck"',
							mandatory_depends_on: 'eval:doc.vehicle_type=="Truck"',
							onchange: () => update_axle_description(dialog),
						},
						{
							fieldtype: "Link",
							fieldname: "trailer",
							label: __("Trailer"),
							options: "Trailer",
							depends_on: 'eval:doc.vehicle_type=="Trailer"',
							mandatory_depends_on: 'eval:doc.vehicle_type=="Trailer"',
							onchange: () => update_axle_description(dialog),
						},
						{
							fieldtype: "Check",
							fieldname: "is_spare",
							label: __("This is the Spare"),
						},
						{
							fieldtype: "Select",
							fieldname: "axle_type",
							label: __("Axle Type"),
							options: "\nFront\nRear",
							depends_on: 'eval:doc.vehicle_type=="Truck" && !doc.is_spare',
						},
						{
							fieldtype: "Int",
							fieldname: "axle_number",
							label: __("Axle Number"),
							depends_on: "eval:!doc.is_spare",
						},
						{
							fieldtype: "Select",
							fieldname: "side",
							label: __("Side"),
							options: SIDE_OPTIONS,
							depends_on: "eval:!doc.is_spare",
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
							label: __("Odometer Reading (Km)"),
							description: __("Used as the baseline to track Km run on this tyre."),
						},
					],
					primary_action_label: __("Fit"),
					primary_action(values) {
						if (!values.is_spare && (!values.axle_number || !values.side)) {
							frappe.msgprint(
								__("Axle Number and Side are required, or tick 'This is the Spare'.")
							);
							return;
						}
						if (values.vehicle_type === "Truck" && !values.is_spare && !values.axle_type) {
							frappe.msgprint(__("Axle Type (Front/Rear) is required for a truck position."));
							return;
						}
						frappe.call({
							method:
								"transport_logistics.transport_logistics.doctype.tyre_movement_log.tyre_movement_log.create_fitment",
							args: {
								tyre: frm.doc.name,
								vehicle_type: values.vehicle_type,
								truck: values.truck,
								trailer: values.trailer,
								is_spare: values.is_spare,
								axle_type: values.axle_type,
								axle_number: values.axle_number,
								side: values.side,
								date: values.date,
								odometer_reading: values.odometer_reading,
							},
							freeze: true,
							callback() {
								dialog.hide();
								frm.reload_doc();
								frappe.show_alert({
									message: __("Tyre fitted."),
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
			const vehicle_label =
				frm.doc.current_vehicle_type === "Trailer" ? frm.doc.current_trailer : frm.doc.current_truck;
			frm.dashboard.add_indicator(
				__("Fitted: {0} — {1}", [vehicle_label, frm.doc.current_position]),
				"green"
			);

			frm.add_custom_button(__("Remove from Vehicle"), () => {
				const dialog = new frappe.ui.Dialog({
					title: __("Remove Tyre {0} from {1}", [frm.doc.name, vehicle_label]),
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
							label: __("Odometer Reading (Km)"),
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
									message: __("Tyre removed from vehicle."),
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
