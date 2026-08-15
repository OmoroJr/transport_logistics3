// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.listview_settings["Truck"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Sync GPS Now (All Trucks)"), () => {
			frappe.show_alert({ message: __("Syncing GPS positions for all trucks..."), indicator: "blue" });
			frappe.call({
				method: "transport_logistics.transport_logistics.gps_tracking.sync_now",
				callback: () => {
					frappe.show_alert({ message: __("GPS sync complete."), indicator: "green" });
					listview.refresh();
				},
			});
		});
	},
};
