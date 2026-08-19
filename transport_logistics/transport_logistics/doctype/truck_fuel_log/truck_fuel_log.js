frappe.ui.form.on("Truck Fuel Log", {
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
	fuel_qty_litres(frm) { calc_amount(frm); },
	rate_per_litre(frm) { calc_amount(frm); },
});

function calc_amount(frm) {
	frm.set_value("total_amount", (frm.doc.fuel_qty_litres || 0) * (frm.doc.rate_per_litre || 0));
}
