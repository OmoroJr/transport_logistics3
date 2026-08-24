// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Route", {
	refresh(frm) {
		frm.add_custom_button(__("Fetch Distance from Google Maps"), () => {
			fetch_distance(frm);
		});
	},
});

function fetch_distance(frm) {
	if (!frm.doc.origin || !frm.doc.destination) {
		frappe.msgprint(__("Please set both Origin and Destination first."));
		return;
	}

	frappe.call({
		method: "transport_logistics.transport_logistics.google_maps.get_distance",
		args: {
			origin: frm.doc.origin,
			destination: frm.doc.destination,
		},
		freeze: true,
		freeze_message: __("Fetching distance from Google Maps..."),
		callback(r) {
			if (!r.message) return;
			frm.set_value("distance_km", r.message.distance_km);
			frappe.show_alert({
				message: __("Distance set to {0} Km (approx. driving time: {1})", [
					format_number(r.message.distance_km, null, 1),
					r.message.duration_text || "—",
				]),
				indicator: "green",
			});
		},
	});
}
