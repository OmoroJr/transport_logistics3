frappe.ui.form.on("Transport Logistics Settings", {
	refresh(frm) {
		if (frm.doc.enable_whatsapp) {
			frm.add_custom_button(__("Send Test Message"), () => {
				if (!frm.doc.whatsapp_test_number) {
					frappe.msgprint(__("Enter a Test Number under WhatsApp Integration > Test Connection first."));
					return;
				}
				if (frm.is_dirty()) {
					frappe.msgprint(__("Save Settings first, then send the test message."));
					return;
				}
				frappe.call({
					method: "transport_logistics.transport_logistics.whatsapp.test_whatsapp_connection",
					args: { to_number: frm.doc.whatsapp_test_number },
					freeze: true,
					freeze_message: __("Sending..."),
				});
			});
		}
	},
});
