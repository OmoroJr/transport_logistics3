// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

/*
 * Navbar "Approvals" notification widget.
 *
 * Shows the five operationally-sensitive requests that need System Manager
 * sign-off (Driver Change, Trailer Decoupling, Extra Fuel, Tyre Change,
 * Spare Part Issuance -- see manager_approval.py) as a bell-style dropdown
 * next to the standard notifications icon, with inline Approve / Reject
 * buttons on every row.
 *
 * A request drops out of the list the instant it's attended to: on a
 * successful decision the row is removed from the DOM immediately, and a
 * realtime ping (transport_logistics_approval_update) refreshes the list
 * for every other connected System Manager so it disappears for them too.
 *
 * Only users with the System Manager role see this widget at all --
 * get_pending_approvals()/approve_request()/reject_request() enforce the
 * same restriction server-side regardless of what happens client-side.
 */

frappe.provide("transport_logistics.approvals");

transport_logistics.approvals = {
	POLL_INTERVAL_MS: 60000,
	_initialized: false,
	requests: [],

	init: function () {
		if (this._initialized) return;
		if (!frappe.user_roles || !frappe.user_roles.includes("System Manager")) return;

		const $navbarRight = $(".navbar-right, .navbar-nav.navbar-right").first();
		if (!$navbarRight.length) {
			// Navbar hasn't rendered yet on this page load -- try again shortly.
			setTimeout(() => this.init(), 500);
			return;
		}

		this._initialized = true;
		this.inject_styles();
		this.render_icon($navbarRight);
		this.bind_events();
		this.refresh();

		setInterval(() => this.refresh(), this.POLL_INTERVAL_MS);

		if (frappe.realtime && frappe.realtime.on) {
			frappe.realtime.on("transport_logistics_approval_update", () => this.refresh());
		}
	},

	render_icon: function ($navbarRight) {
		this.$wrapper = $(`
			<li class="nav-item dropdown tl-approvals-dropdown">
				<a class="nav-link tl-approvals-toggle" href="#" title="${__("Approvals")}">
					<svg viewBox="0 0 24 24" width="18" height="18" fill="none"
						stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<path d="M9 11l3 3L22 4"></path>
						<path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
					</svg>
					<span class="tl-approvals-badge" style="display:none;">0</span>
				</a>
				<div class="tl-approvals-panel" style="display:none;">
					<div class="tl-approvals-header">${__("Pending Approvals")}</div>
					<div class="tl-approvals-list">
						<div class="tl-approvals-empty text-muted">${__("Nothing pending")}</div>
					</div>
				</div>
			</li>
		`);

		const $existingNotifIcon = $navbarRight.find(".dropdown-notifications").first();
		if ($existingNotifIcon.length) {
			$existingNotifIcon.before(this.$wrapper);
		} else {
			$navbarRight.prepend(this.$wrapper);
		}

		this.$badge = this.$wrapper.find(".tl-approvals-badge");
		this.$panel = this.$wrapper.find(".tl-approvals-panel");
		this.$list = this.$wrapper.find(".tl-approvals-list");
	},

	bind_events: function () {
		const me = this;

		this.$wrapper.find(".tl-approvals-toggle").on("click", function (e) {
			e.preventDefault();
			e.stopPropagation();
			const isOpen = me.$panel.is(":visible");
			$(".tl-approvals-panel").hide();
			if (!isOpen) {
				me.$panel.show();
			}
		});

		$(document).on("click", function (e) {
			if (!$(e.target).closest(".tl-approvals-dropdown").length) {
				me.$panel.hide();
			}
		});

		this.$list.on("click", ".tl-approval-open", function (e) {
			if ($(e.target).closest("button").length) return;
			const $row = $(this);
			me.$panel.hide();
			frappe.set_route("Form", $row.data("doctype"), $row.data("name"));
		});

		this.$list.on("click", ".tl-approval-approve", function (e) {
			e.preventDefault();
			e.stopPropagation();
			const $row = $(this).closest(".tl-approval-row");
			const doctype = $row.data("doctype");
			const name = $row.data("name");
			frappe.confirm(__("Approve this {0} request ({1})?", [doctype, name]), () => {
				me.decide($row, "approve_request", doctype, name);
			});
		});

		this.$list.on("click", ".tl-approval-reject", function (e) {
			e.preventDefault();
			e.stopPropagation();
			const $row = $(this).closest(".tl-approval-row");
			const doctype = $row.data("doctype");
			const name = $row.data("name");
			frappe.prompt(
				[{ fieldname: "remarks", fieldtype: "Small Text", label: __("Rejection Remarks") }],
				(values) => me.decide($row, "reject_request", doctype, name, values.remarks),
				__("Reject Request"),
				__("Reject")
			);
		});
	},

	decide: function ($row, method_name, doctype, name, remarks) {
		const me = this;
		frappe.call({
			method: `transport_logistics.transport_logistics.manager_approval.${method_name}`,
			args: { doctype, name, remarks },
			freeze: true,
			callback: function () {
				frappe.show_alert({
					message: method_name === "approve_request" ? __("Approved") : __("Rejected"),
					indicator: method_name === "approve_request" ? "green" : "orange",
				});
				// Disappear immediately -- don't wait for the next poll or
				// the realtime round-trip.
				$row.fadeOut(150, () => {
					$row.remove();
					me.requests = me.requests.filter(
						(r) => !(r.reference_doctype === doctype && r.reference_name === name)
					);
					me.render_list();
				});
			},
		});
	},

	refresh: function () {
		const me = this;
		frappe.call({
			method: "transport_logistics.transport_logistics.manager_approval.get_pending_approvals",
			callback: function (r) {
				me.requests = r.message || [];
				me.render_list();
			},
		});
	},

	render_list: function () {
		const count = this.requests.length;

		if (count) {
			this.$badge.text(count > 99 ? "99+" : count).show();
		} else {
			this.$badge.hide();
		}

		if (!count) {
			this.$list.html(`<div class="tl-approvals-empty text-muted">${__("Nothing pending")}</div>`);
			return;
		}

		const rows = this.requests
			.map((req) => {
				const doctype = frappe.utils.escape_html(req.reference_doctype || "");
				const name = frappe.utils.escape_html(req.reference_name || "");
				const requestType = frappe.utils.escape_html(req.request_type || "");
				const details = frappe.utils.escape_html(req.details || "");
				const truck = frappe.utils.escape_html(req.truck || "");
				const requestedBy = frappe.utils.escape_html(req.requested_by || "");

				return `
					<div class="tl-approval-row tl-approval-open" data-doctype="${doctype}" data-name="${name}">
						<div class="tl-approval-main">
							<div class="tl-approval-title">
								<span class="tl-approval-type">${requestType}</span>
								<span class="tl-approval-ref">${name}</span>
							</div>
							<div class="tl-approval-details">${details}</div>
							<div class="tl-approval-meta">
								${truck ? `${__("Truck")} ${truck} &middot; ` : ""}${__("by")} ${requestedBy}
							</div>
						</div>
						<div class="tl-approval-actions">
							<button class="btn btn-xs btn-primary tl-approval-approve">${__("Approve")}</button>
							<button class="btn btn-xs btn-default tl-approval-reject">${__("Reject")}</button>
						</div>
					</div>
				`;
			})
			.join("");

		this.$list.html(rows);
	},

	inject_styles: function () {
		if (document.getElementById("tl-approvals-style")) return;
		const style = document.createElement("style");
		style.id = "tl-approvals-style";
		style.textContent = `
			.tl-approvals-dropdown { position: relative; }
			.tl-approvals-toggle { position: relative; display: flex; align-items: center; padding: 0 10px; height: 100%; }
			.tl-approvals-badge {
				position: absolute; top: 2px; right: 2px; min-width: 16px; height: 16px;
				padding: 0 4px; border-radius: 9px; background: var(--red-500, #e24c4c);
				color: #fff; font-size: 10px; line-height: 16px; text-align: center; font-weight: 600;
			}
			.tl-approvals-panel {
				position: absolute; right: 0; top: 100%; margin-top: 4px; width: 360px; max-height: 420px;
				overflow-y: auto; background: var(--fg-color, #fff); border: 1px solid var(--border-color, #d1d8dd);
				border-radius: var(--border-radius-md, 8px); box-shadow: var(--shadow-lg, 0 4px 16px rgba(0,0,0,.15));
				z-index: 1050;
			}
			.tl-approvals-header {
				padding: 10px 14px; font-weight: 600; border-bottom: 1px solid var(--border-color, #d1d8dd);
			}
			.tl-approvals-empty { padding: 16px 14px; text-align: center; }
			.tl-approval-row {
				display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;
				padding: 10px 14px; border-bottom: 1px solid var(--border-color, #eef1f4); cursor: pointer;
			}
			.tl-approval-row:last-child { border-bottom: none; }
			.tl-approval-row:hover { background: var(--fg-hover-color, #f4f5f6); }
			.tl-approval-main { min-width: 0; }
			.tl-approval-title { font-weight: 600; font-size: 12px; }
			.tl-approval-ref { color: var(--text-muted, #8d99a6); font-weight: 400; margin-left: 6px; }
			.tl-approval-details { font-size: 12px; margin-top: 2px; }
			.tl-approval-meta { font-size: 11px; color: var(--text-muted, #8d99a6); margin-top: 2px; }
			.tl-approval-actions { display: flex; flex-direction: column; gap: 4px; flex-shrink: 0; }
			.tl-approval-actions .btn { white-space: nowrap; }
		`;
		document.head.appendChild(style);
	},
};

$(document).ready(function () {
	transport_logistics.approvals.init();
});
