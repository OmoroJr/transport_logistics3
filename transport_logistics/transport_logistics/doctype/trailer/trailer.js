// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Trailer", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("New Coupling Log"), () => {
				frappe.new_doc("Trailer Coupling Log", { trailer: frm.doc.name });
			}, __("Create"));

			frm.add_custom_button(__("Fit Tyre"), () => {
				const dialog = new frappe.ui.Dialog({
					title: __("Fit Tyre to {0}", [frm.doc.name]),
					fields: [
						{
							fieldtype: "Link",
							fieldname: "tyre",
							label: __("Tyre"),
							options: "Tyre",
							reqd: 1,
							get_query: () => ({
								filters: { status: ["in", ["In Stock", "Retreaded"]] },
							}),
						},
						{
							fieldtype: "Check",
							fieldname: "is_spare",
							label: __("This is the Spare"),
						},
						{
							fieldtype: "Int",
							fieldname: "axle_number",
							label: __("Axle Number"),
							description: __("This trailer has {0} axle(s).", [frm.doc.axle_count || 3]),
							depends_on: "eval:!doc.is_spare",
						},
						{
							fieldtype: "Select",
							fieldname: "side",
							label: __("Side"),
							options: "\nLeft\nRight\nLeft Outer\nLeft Inner\nRight Outer\nRight Inner",
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
							label: __("Truck Odometer Reading (Km)"),
							description: __("The odometer of the truck currently hauling this trailer, if known."),
						},
					],
					primary_action_label: __("Fit"),
					primary_action(values) {
						if (!values.is_spare && (!values.axle_number || !values.side)) {
							frappe.msgprint(__("Axle Number and Side are required, or tick 'This is the Spare'."));
							return;
						}
						frappe.call({
							method:
								"transport_logistics.transport_logistics.doctype.tyre_movement_log.tyre_movement_log.create_fitment",
							args: {
								tyre: values.tyre,
								vehicle_type: "Trailer",
								trailer: frm.doc.name,
								is_spare: values.is_spare,
								axle_number: values.axle_number,
								side: values.side,
								date: values.date,
								odometer_reading: values.odometer_reading,
							},
							freeze: true,
							callback() {
								dialog.hide();
								frappe.show_alert({
									message: __("Tyre fitted to {0}.", [frm.doc.name]),
									indicator: "green",
								});
							},
						});
					},
				});
				dialog.show();
			}, __("Create"));

			frm.add_custom_button(__("Tyres on this Trailer"), () => {
				frappe.set_route("List", "Tyre", { current_trailer: frm.doc.name });
			}, __("View"));

			if (frm.doc.current_truck) {
				frm.dashboard.add_indicator(
					__("Coupled to: {0}", [frm.doc.current_truck]),
					"blue"
				);
			} else {
				frm.dashboard.add_indicator(__("Not currently coupled"), "grey");
			}
		}
	},
});
