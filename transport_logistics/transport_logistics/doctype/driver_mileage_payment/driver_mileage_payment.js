// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Driver Mileage Payment", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Fetch Trips for Period"), () => {
				frappe.call({
					method:
						"transport_logistics.transport_logistics.doctype.driver_mileage_payment.driver_mileage_payment.get_route_trip_counts",
					args: {
						driver: frm.doc.driver,
						truck: frm.doc.truck,
						from_date: frm.doc.from_date,
						to_date: frm.doc.to_date,
					},
					callback(r) {
						if (r.message && r.message.length) {
							frm.clear_table("routes");
							r.message.forEach((row) => {
								const child = frm.add_child("routes");
								child.route = row.route;
								child.number_of_trips = row.number_of_trips;
								child.rate = row.rate;
								child.amount = row.amount;
							});
							frm.refresh_field("routes");
							calc_totals(frm);
							frappe.show_alert({
								message: __("Routes fetched from completed trips in this period"),
								indicator: "green",
							});
						} else {
							frappe.show_alert({
								message: __("No completed trips with a Route found in this period"),
								indicator: "orange",
							});
						}
					},
				});
			});
		}

		if (
			frm.doc.docstatus === 0 &&
			frm.doc.payment_method === "M-Pesa" &&
			frm.doc.payment_status !== "Paid"
		) {
			frm.add_custom_button(
				__("Initiate M-Pesa Payment"),
				() => {
					frappe.confirm(
						__("This sends a live B2C payment request to Safaricom for {0} to {1}. Continue?", [
							format_currency(frm.doc.total_amount, frm.doc.currency),
							frm.doc.mpesa_phone_number,
						]),
						() => {
							frappe.call({
								method: "transport_logistics.transport_logistics.mpesa.initiate_b2c_payment",
								args: { payment_name: frm.doc.name },
								freeze: true,
								freeze_message: __("Contacting Safaricom..."),
								callback() {
									frm.reload_doc();
								},
							});
						}
					);
				},
				__("M-Pesa")
			);
		}
	},

	other_allowance(frm) { calc_totals(frm); },
});

frappe.ui.form.on("Driver Mileage Payment Route", {
	route(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.route) {
			frappe.db.get_value("Route", row.route, "driver_rate").then((r) => {
				if (r.message && r.message.driver_rate) {
					frappe.model.set_value(cdt, cdn, "rate", r.message.driver_rate);
				}
			});
		}
	},
	number_of_trips(frm, cdt, cdn) { calc_row(frm, cdt, cdn); },
	rate(frm, cdt, cdn) { calc_row(frm, cdt, cdn); },
	routes_remove(frm) { calc_totals(frm); },
});

function calc_row(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "amount", (row.number_of_trips || 0) * (row.rate || 0));
	calc_totals(frm);
}

function calc_totals(frm) {
	let computed = 0;
	(frm.doc.routes || []).forEach((row) => {
		computed += (row.number_of_trips || 0) * (row.rate || 0);
	});
	frm.set_value("computed_amount", computed);
	frm.set_value("total_amount", computed + (frm.doc.other_allowance || 0));
}
