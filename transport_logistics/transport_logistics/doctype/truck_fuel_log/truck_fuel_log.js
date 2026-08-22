frappe.ui.form.on("Truck Fuel Log", {
	refresh(frm) {
		transport_logistics.manager_approval.add_buttons(frm);
	},

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
		fetch_standard_fuel(frm);
	},
	fuel_qty_litres(frm) {
		calc_amount(frm);
		calc_extra_fuel(frm);
	},
	rate_per_litre(frm) { calc_amount(frm); },
});

function calc_amount(frm) {
	frm.set_value("total_amount", (frm.doc.fuel_qty_litres || 0) * (frm.doc.rate_per_litre || 0));
}

function fetch_standard_fuel(frm) {
	// Live preview only — the server recomputes standard_fuel_litres and
	// extra_fuel_litres authoritatively on save, this just gives the user
	// a heads-up before they submit so they aren't surprised by the reason
	// requirement.
	if (frm.doc.reason_for_fuelling !== "For Trip" || !frm.doc.truck_trip) {
		frm.set_value("standard_fuel_litres", 0);
		calc_extra_fuel(frm);
		return;
	}
	frappe.db.get_value("Truck Trip", frm.doc.truck_trip, "route").then(({ message }) => {
		const route = message && message.route;
		if (!route) {
			frm.set_value("standard_fuel_litres", 0);
			calc_extra_fuel(frm);
			return;
		}
		frappe.db.get_value("Route", route, "standard_fuel_litres").then((r) => {
			frm.set_value("standard_fuel_litres", (r.message && r.message.standard_fuel_litres) || 0);
			calc_extra_fuel(frm);
		});
	});
}

function calc_extra_fuel(frm) {
	const standard = frm.doc.standard_fuel_litres || 0;
	const extra = standard ? Math.max(0, (frm.doc.fuel_qty_litres || 0) - standard) : 0;
	frm.set_value("extra_fuel_litres", extra);
}
