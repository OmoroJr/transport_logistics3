// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Fuel Tank", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("New Bulk Purchase"), () => {
			frappe.new_doc("Bulk Fuel Purchase", { tank: frm.doc.name });
		}, __("Create"));
		frm.add_custom_button(__("New Dispensing"), () => {
			frappe.new_doc("Fuel Dispensing", { tank: frm.doc.name });
		}, __("Create"));

		frappe.call({
			method: "transport_logistics.transport_logistics.doctype.fuel_tank.fuel_tank.get_stock_level",
			args: { tank_name: frm.doc.name },
			callback(r) {
				if (!r.message) return;
				const qty = r.message.actual_qty || 0;
				const rate = r.message.valuation_rate || 0;
				const pct = frm.doc.capacity_litres ? Math.min(100, (qty / frm.doc.capacity_litres) * 100) : null;
				const bar = pct !== null
					? `<div style="background:#eee;border-radius:6px;overflow:hidden;height:10px;margin-top:6px;">
						 <div style="width:${pct}%;background:${pct > 20 ? '#27AE60' : '#C0392B'};height:100%;"></div>
					   </div>
					   <div style="font-size:11px;color:#888;margin-top:2px;">${pct.toFixed(0)}% of capacity</div>`
					: "";
				frm.set_df_property(
					"html_stock_level",
					"options",
					`<div><b>${format_number(qty, null, 1)} L</b> in stock &nbsp;|&nbsp; Avg cost: ${format_currency(rate)}/L${bar}</div>`
				);
				frm.refresh_field("html_stock_level");
			},
		});
	},
});
