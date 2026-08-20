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

		if (frm.doc.enable_email_alerts) {
			frm.add_custom_button(__("Send Test Email"), () => {
				if (!frm.doc.email_test_recipient) {
					frappe.msgprint(__("Enter a Test Recipient under Email Alerts > Test Connection first."));
					return;
				}
				if (frm.is_dirty()) {
					frappe.msgprint(__("Save Settings first, then send the test email."));
					return;
				}
				frappe.call({
					method: "transport_logistics.transport_logistics.email_alerts.test_email_connection",
					args: { to_email: frm.doc.email_test_recipient },
					freeze: true,
					freeze_message: __("Sending..."),
				});
			});
		}

		if (frm.doc.enable_sms) {
			frm.add_custom_button(__("Send Test SMS"), () => {
				if (!frm.doc.sms_test_number) {
					frappe.msgprint(__("Enter a Test Number under SMS Alerts > Test Connection first."));
					return;
				}
				if (frm.is_dirty()) {
					frappe.msgprint(__("Save Settings first, then send the test SMS."));
					return;
				}
				frappe.call({
					method: "transport_logistics.transport_logistics.sms.test_sms_connection",
					args: { to_number: frm.doc.sms_test_number },
					freeze: true,
					freeze_message: __("Sending..."),
				});
			});
		}
	},
});

