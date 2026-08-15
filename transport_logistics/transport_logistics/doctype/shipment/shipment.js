// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Shipment", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.total_billable > 0 && !frm.doc.sales_invoice) {
			frm.add_custom_button(__("Create Sales Invoice"), () => {
				frappe.call({
					method: "transport_logistics.transport_logistics.doctype.shipment.shipment.create_sales_invoice",
					args: { shipment_name: frm.doc.name },
					freeze: true,
					callback() {
						frm.reload_doc();
					},
				});
			});
		}

		if (frm.doc.sales_invoice) {
			frm.add_custom_button(__("View Sales Invoice"), () => {
				frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice);
			});
		}
	},

	charges_on_form_rendered(frm) { calc_totals(frm); },
});

frappe.ui.form.on("Shipment Charge", {
	amount(frm) { calc_totals(frm); },
	billable(frm) { calc_totals(frm); },
	payable_by(frm) { calc_totals(frm); },
	charges_remove(frm) { calc_totals(frm); },
});

function calc_totals(frm) {
	let billable = 0;
	let company_cost = 0;
	(frm.doc.charges || []).forEach((row) => {
		if (row.billable) billable += row.amount || 0;
		if (row.payable_by === "Company (Own Cost)") company_cost += row.amount || 0;
	});
	frm.set_value("total_billable", billable);
	frm.set_value("total_company_cost", company_cost);
}
