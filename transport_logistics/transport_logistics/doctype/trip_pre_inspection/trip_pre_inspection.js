// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Trip Pre Inspection", {
	setup(frm) {
		frm.set_query("truck_trip", () => {
			const filters = { status: ["in", ["Planned", "Ongoing"]] };
			if (frm.doc.truck) filters.truck = frm.doc.truck;
			return { filters };
		});
	},

	truck_trip(frm) {
		// Convenience only — the server still enforces the match in
		// validate_truck_trip() regardless of what happens here.
		if (!frm.doc.truck_trip) return;
		frappe.db.get_value("Truck Trip", frm.doc.truck_trip, "truck").then((r) => {
			if (r.message && r.message.truck && !frm.doc.truck) {
				frm.set_value("truck", r.message.truck);
			}
		});
	},

	refresh(frm) {
		if (frm.doc.overall_status === "Fail") {
			frm.dashboard.set_headline_alert(
				__(
					frm.doc.workshop_job_card
						? "This inspection failed — the truck has been sent to workshop and cannot depart on a new trip until a passing inspection is on file."
						: "This inspection failed — the truck cannot depart on a new trip until a passing inspection is on file."
				),
				"red"
			);
		}
	},
});

frappe.ui.form.on("Trip Pre Inspection Item", {
	status(frm, cdt, cdn) {
		// Purely a client-side nudge -- the server enforces this same
		// requirement in validate_items() regardless of what happens here.
		const row = frappe.get_doc(cdt, cdn);
		if (row.status === "Not OK" && !row.remarks) {
			frappe.show_alert({
				message: __("Add a Remarks note describing the fault for this item."),
				indicator: "orange",
			});
		}
	},
});
