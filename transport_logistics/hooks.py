from . import __version__ as app_version

app_name = "transport_logistics"
app_title = "Transport Logistics"
app_publisher = "Wycliffs"
app_description = "Truck, Fuel, Tyre and Maintenance management with per-truck cost analysis for ERPNext"
app_icon = "octicon octicon-truck"
app_color = "#2E86C1"
app_email = "admin@example.com"
app_license = "MIT"

# Include js/css in doctype views
doctype_js = {
    "Truck": "transport_logistics/doctype/truck/truck.js",
    "Trailer": "transport_logistics/doctype/trailer/trailer.js",
    "Tyre": "transport_logistics/doctype/tyre/tyre.js",
    "Employee": "public/js/employee.js",
    "Transport Logistics Settings": "transport_logistics/doctype/transport_logistics_settings/transport_logistics_settings.js",
}

doctype_list_js = {
    "Truck": "transport_logistics/doctype/truck/truck_list.js",
}

# Document Events
doc_events = {
    "Truck Fuel Log": {
        "validate": "transport_logistics.transport_logistics.doctype.truck_fuel_log.truck_fuel_log.set_computed_fields",
        "on_submit": [
            "transport_logistics.transport_logistics.doctype.truck_fuel_log.truck_fuel_log.update_truck_odometer",
            "transport_logistics.transport_logistics.gl_utils.post_fuel_log_to_gl",
            "transport_logistics.transport_logistics.doctype.truck_fuel_log.truck_fuel_log.notify_driver_fuel_confirmation",
            "transport_logistics.transport_logistics.doctype.truck_fuel_log.truck_fuel_log.notify_driver_fuel_confirmation_email",
            "transport_logistics.transport_logistics.doctype.truck_fuel_log.truck_fuel_log.notify_driver_fuel_confirmation_sms",
        ],
        "on_cancel": [
            "transport_logistics.transport_logistics.doctype.truck_fuel_log.truck_fuel_log.update_truck_odometer",
            "transport_logistics.transport_logistics.gl_utils.cancel_linked_journal_entry",
        ],
    },
    "Truck Maintenance Log": {
        "validate": "transport_logistics.transport_logistics.doctype.truck_maintenance_log.truck_maintenance_log.set_total_cost",
        "on_submit": [
            "transport_logistics.transport_logistics.doctype.truck_maintenance_log.truck_maintenance_log.update_truck_status",
            "transport_logistics.transport_logistics.gl_utils.post_maintenance_log_to_gl",
        ],
        "on_cancel": "transport_logistics.transport_logistics.gl_utils.cancel_linked_journal_entry",
    },
    "Truck Expense": {
        "on_submit": "transport_logistics.transport_logistics.gl_utils.post_expense_to_gl",
        "on_cancel": "transport_logistics.transport_logistics.gl_utils.cancel_linked_journal_entry",
    },
    "Tyre Movement Log": {
        "validate": "transport_logistics.transport_logistics.doctype.tyre_movement_log.tyre_movement_log.validate_movement",
        "on_submit": [
            "transport_logistics.transport_logistics.doctype.tyre_movement_log.tyre_movement_log.apply_movement",
            "transport_logistics.transport_logistics.gl_utils.post_tyre_movement_to_gl",
        ],
        "on_cancel": [
            "transport_logistics.transport_logistics.doctype.tyre_movement_log.tyre_movement_log.reverse_movement",
            "transport_logistics.transport_logistics.gl_utils.cancel_linked_journal_entry",
        ],
    },
    "Authority to Load": {
        "validate": "transport_logistics.transport_logistics.doctype.authority_to_load.authority_to_load.run_compliance_checks",
        "on_submit": [
            "transport_logistics.transport_logistics.doctype.authority_to_load.authority_to_load.notify_driver",
            "transport_logistics.transport_logistics.doctype.authority_to_load.authority_to_load.notify_driver_email",
            "transport_logistics.transport_logistics.doctype.authority_to_load.authority_to_load.notify_driver_sms",
        ],
    },
    "Accident Report": {
        "validate": "transport_logistics.transport_logistics.doctype.accident_report.accident_report.set_cost_fields",
        "on_submit": [
            "transport_logistics.transport_logistics.doctype.accident_report.accident_report.update_truck_status",
            "transport_logistics.transport_logistics.doctype.accident_report.accident_report.notify_high_severity",
            "transport_logistics.transport_logistics.gl_utils.post_accident_to_gl",
        ],
        "on_cancel": "transport_logistics.transport_logistics.gl_utils.cancel_linked_journal_entry",
    },
    "Highway Breakdown": {
        "after_insert": [
            "transport_logistics.transport_logistics.doctype.highway_breakdown.highway_breakdown.flag_truck_under_maintenance",
            "transport_logistics.transport_logistics.doctype.highway_breakdown.highway_breakdown.notify_breakdown",
        ],
        "on_submit": [
            "transport_logistics.transport_logistics.doctype.highway_breakdown.highway_breakdown.restore_truck_status",
            "transport_logistics.transport_logistics.gl_utils.post_breakdown_to_gl",
        ],
        "on_cancel": "transport_logistics.transport_logistics.gl_utils.cancel_linked_journal_entry",
    },
    "Tyre Depth Inspection": {
        "on_submit": "transport_logistics.transport_logistics.doctype.tyre_depth_inspection.tyre_depth_inspection.flag_tyre_on_fail",
    },
    "Driver Safety Incident": {
        "validate": "transport_logistics.transport_logistics.doctype.driver_safety_incident.driver_safety_incident.default_points_if_unset",
        "on_submit": "transport_logistics.transport_logistics.doctype.driver_safety_incident.driver_safety_incident.notify_high_severity",
    },
    "Driver Mileage Payment": {
        "on_submit": "transport_logistics.transport_logistics.gl_utils.post_driver_payment_to_gl",
        "on_cancel": "transport_logistics.transport_logistics.gl_utils.cancel_linked_journal_entry",
    },
    "Workshop Job Card": {
        "on_submit": "transport_logistics.transport_logistics.doctype.workshop_job_card.workshop_job_card.on_submit_actions",
        "on_cancel": "transport_logistics.transport_logistics.doctype.workshop_job_card.workshop_job_card.on_cancel_actions",
    },
    "Gate Pass": {
        "validate": "transport_logistics.transport_logistics.doctype.gate_pass.gate_pass.compute_status_and_duration",
    },
    "Trailer Coupling Log": {
        "validate": "transport_logistics.transport_logistics.doctype.trailer_coupling_log.trailer_coupling_log.validate_coupling",
        "on_submit": "transport_logistics.transport_logistics.doctype.trailer_coupling_log.trailer_coupling_log.apply_coupling",
        "on_cancel": "transport_logistics.transport_logistics.doctype.trailer_coupling_log.trailer_coupling_log.reverse_coupling",
    },
    "Bulk Fuel Purchase": {
        "on_submit": [
            "transport_logistics.transport_logistics.doctype.bulk_fuel_purchase.bulk_fuel_purchase.create_stock_receipt",
            "transport_logistics.transport_logistics.gl_utils.post_bulk_fuel_purchase_to_gl",
        ],
        "on_cancel": [
            "transport_logistics.transport_logistics.doctype.bulk_fuel_purchase.bulk_fuel_purchase.cancel_stock_receipt",
            "transport_logistics.transport_logistics.gl_utils.cancel_linked_journal_entry",
        ],
    },
    "Fuel Dispensing": {
        "on_submit": [
            "transport_logistics.transport_logistics.doctype.fuel_dispensing.fuel_dispensing.check_stock_and_issue",
            "transport_logistics.transport_logistics.gl_utils.post_fuel_dispensing_to_gl",
        ],
        "on_cancel": [
            "transport_logistics.transport_logistics.doctype.fuel_dispensing.fuel_dispensing.on_cancel_actions",
            "transport_logistics.transport_logistics.gl_utils.cancel_linked_journal_entry",
        ],
    },
    "Shipment": {
        "validate": "transport_logistics.transport_logistics.doctype.shipment.shipment.compute_charge_totals",
    },
}

# Scheduled Tasks
scheduler_events = {
    "daily": [
        "transport_logistics.transport_logistics.tasks.check_document_expiry",
        "transport_logistics.transport_logistics.tasks.check_driver_license_expiry",
        "transport_logistics.transport_logistics.tasks.check_port_pass_expiry",
    ],
    "cron": {
        # Live GPS location + odometer sync. Runs every 15 minutes; the job
        # itself is a no-op (returns immediately) unless GPS Tracking is
        # enabled in Transport Logistics Settings. Change the cron string
        # below if you need a different frequency.
        "*/15 * * * *": [
            "transport_logistics.transport_logistics.gps_tracking.sync_truck_locations",
        ],
    },
}

fixtures = [
    {"dt": "Role", "filters": [["role_name", "in", ["Transport Manager", "Transport User"]]]},
    {
        "dt": "Custom Field",
        "filters": [
            [
                "fieldname",
                "in",
                [
                    "section_break_driving_license",
                    "driving_license_number",
                    "column_break_driving_license",
                    "driving_license_expiry_date",
                    "section_break_port_pass",
                    "port_pass_number",
                    "column_break_port_pass",
                    "port_pass_expiry_date",
                ],
            ]
        ],
    },
]
