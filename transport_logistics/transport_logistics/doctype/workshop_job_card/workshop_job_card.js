// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Workshop Job Card", {
	onload(frm) {
		if (frm.is_new() && !frm.doc.labour_rate) {
			frappe.db.get_single_value("Transport Logistics Settings", "default_labour_rate").then((rate) => {
				if (rate) frm.set_value("labour_rate", rate);
			});
		}
		if (frm.is_new() && !frm.doc.warehouse) {
			frappe.db.get_single_value("Transport Logistics Settings", "default_workshop_warehouse").then((wh) => {
				if (wh) frm.set_value("warehouse", wh);
			});
		}
	},

	labour_hours(frm) { calc_totals(frm); },
	labour_rate(frm) { calc_totals(frm); },
	other_cost(frm) { calc_totals(frm); },

	refresh(frm) {
		transport_logistics.manager_approval.add_buttons(frm);

		if (!frm.is_new() && frm.doc.maintenance_log) {
			frm.add_custom_button(__("View Maintenance Log"), () => {
				frappe.set_route("Form", "Truck Maintenance Log", frm.doc.maintenance_log);
			});
		}
		if (!frm.is_new() && frm.doc.stock_entry) {
			frm.add_custom_button(__("View Stock Entry"), () => {
				frappe.set_route("Form", "Stock Entry", frm.doc.stock_entry);
			});
		}
	},
});

frappe.ui.form.on("Workshop Job Card Item", {
	qty(frm, cdt, cdn) { calc_row(frm, cdt, cdn); },
	rate(frm, cdt, cdn) { calc_row(frm, cdt, cdn); },
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.item_code) {
			frappe.db.get_value("Item", row.item_code, "valuation_rate").then((r) => {
				if (r.message && r.message.valuation_rate && !row.rate) {
					frappe.model.set_value(cdt, cdn, "rate", r.message.valuation_rate);
				}
			});
		}
	},
	items_remove(frm) { calc_totals(frm); },
});

function calc_row(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "amount", (row.qty || 0) * (row.rate || 0));
	calc_totals(frm);
}

function calc_totals(frm) {
	let parts_cost = 0;
	(frm.doc.items || []).forEach((row) => {
		parts_cost += (row.qty || 0) * (row.rate || 0);
	});
	let labour_cost = (frm.doc.labour_hours || 0) * (frm.doc.labour_rate || 0);
	frm.set_value("parts_cost", parts_cost);
	frm.set_value("labour_cost", labour_cost);
	frm.set_value("total_cost", parts_cost + labour_cost + (frm.doc.other_cost || 0));
}
