// Copyright (c) 2026, Wycliffs and contributors
// For license information, please see license.txt

const TCD_CHARTJS_URL = "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.5.0/chart.umd.min.js";
const TCD_FONTAWESOME_CSS_URL = "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css";

const KPI_ICONS = {
	distance: "fa-solid fa-road",
	fuel: "fa-solid fa-gas-pump",
	maintenance: "fa-solid fa-screwdriver-wrench",
	tyre: "fa-solid fa-dharmachakra",
	other: "fa-solid fa-file-invoice-dollar",
	depreciation: "fa-solid fa-building",
	total: "fa-solid fa-coins",
};

// Maps each KPI card to the backend "component" key used by
// get_cost_component_details, and to the doctype a "View List" button
// in the drill-down dialog should open (null = no direct list, e.g. a
// computed figure like Depreciation with no single source doctype).
const KPI_COMPONENTS = {
	distance: { component: "distance", list_doctype: "Truck Trip" },
	fuel: { component: "fuel", list_doctype: "Truck Fuel Log" },
	maintenance: { component: "maintenance", list_doctype: "Truck Maintenance Log" },
	tyre: { component: "tyre", list_doctype: "Tyre Movement Log" },
	other: { component: "other", list_doctype: "Truck Expense" },
	depreciation: { component: "depreciation", list_doctype: null },
	total: { component: "total", list_doctype: null },
};

frappe.pages["truck-cost-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Truck Cost Dashboard",
		single_column: true,
	});

	inject_styles();

	const truck_field = page.add_field({
		fieldtype: "Link",
		options: "Truck",
		fieldname: "truck",
		label: __("Truck (blank = All Trucks)"),
		change: render,
	});

	const from_date_field = page.add_field({
		fieldtype: "Date",
		fieldname: "from_date",
		label: __("From Date"),
		default: frappe.datetime.month_start(),
		change: render,
	});

	const to_date_field = page.add_field({
		fieldtype: "Date",
		fieldname: "to_date",
		label: __("To Date"),
		default: frappe.datetime.get_today(),
		change: render,
	});

	const $body = $('<div class="tcd-wrapper"></div>').appendTo(page.body);

	if (frappe.route_options && frappe.route_options.truck) {
		truck_field.set_value(frappe.route_options.truck);
		delete frappe.route_options.truck;
	}

	let chartjs_ready = false;
	let doughnut_instance = null;
	let current_args = null;

	load_chartjs(() => {
		chartjs_ready = true;
	});
	load_fontawesome();

	function fmt_money(v) {
		return format_currency(v || 0, frappe.defaults.get_default("currency"), 0);
	}

	function fmt_num(v, precision = 0) {
		return format_number(v || 0, null, precision);
	}

	function render() {
		const args = {
			truck: truck_field.get_value() || null,
			from_date: from_date_field.get_value(),
			to_date: to_date_field.get_value(),
		};
		if (!args.from_date || !args.to_date) return;

		frappe.call({
			method: "transport_logistics.transport_logistics.dashboard_api.get_truck_cost_dashboard",
			args,
			freeze: true,
			freeze_message: __("Crunching the numbers..."),
			callback(r) {
				if (r.message) draw(r.message, args.truck);
			},
		});
	}

	function draw(data, truck) {
		if (doughnut_instance) {
			doughnut_instance.destroy();
			doughnut_instance = null;
		}
		$body.empty();
		current_args = {
			truck: truck_field.get_value() || null,
			from_date: from_date_field.get_value(),
			to_date: to_date_field.get_value(),
		};

		const scope_label = truck ? truck : __("All Trucks ({0})", [data.truck_count]);
		$(`<div class="tcd-scope">${__("Showing")}: <b>${frappe.utils.escape_html(scope_label)}</b></div>`).appendTo($body);

		render_kpi_row(data);
		render_panel_row(data);
	}

	function icon_html(key) {
		// Font Awesome <i> tag. If the CSS failed to load (e.g. a flaky
		// connection), this just renders as an empty inline element —
		// harmless, the layout doesn't break.
		return `<i class="${KPI_ICONS[key]}"></i>`;
	}

	function render_kpi_row(data) {
		const kpis = [
			{ key: "distance", label: __("TOTAL DISTANCE"), value: `${fmt_num(data.distance_km)} km`, icon: "distance" },
			{ key: "fuel", label: __("FUEL COST"), value: fmt_money(data.fuel_cost), icon: "fuel" },
			{ key: "maintenance", label: __("MAINTENANCE COST"), value: fmt_money(data.maintenance_cost), icon: "maintenance" },
			{ key: "tyre", label: __("TYRE COST"), value: fmt_money(data.tyre_cost), icon: "tyre" },
			{ key: "other", label: __("OTHER EXPENSES"), value: fmt_money(data.other_expense_cost), icon: "other" },
			{ key: "depreciation", label: __("DEPRECIATION"), value: fmt_money(data.depreciation_cost), icon: "depreciation" },
			{ key: "total", label: __("TOTAL COST"), value: fmt_money(data.total_cost), icon: "total", highlight: true },
		];

		const $row = $('<div class="tcd-kpi-row"></div>').appendTo($body);
		kpis.forEach((k) => {
			const $card = $(`
				<div class="tcd-kpi-card tcd-kpi-clickable" title="${__("Click to see the components behind this figure")}">
					<div class="tcd-kpi-icon ${k.highlight ? "tcd-highlight" : ""}">${icon_html(k.icon)}</div>
					<div class="tcd-kpi-text">
						<div class="tcd-kpi-label">${k.label}</div>
						<div class="tcd-kpi-value ${k.highlight ? "tcd-highlight" : ""}">${k.value}</div>
					</div>
				</div>
			`).appendTo($row);
			$card.on("click", () => show_component_dialog(k.key, k.label));
		});
	}

	function show_component_dialog(key, label) {
		const cfg = KPI_COMPONENTS[key];
		if (!cfg || !current_args) return;

		frappe.call({
			method: "transport_logistics.transport_logistics.dashboard_api.get_cost_component_details",
			args: {
				component: cfg.component,
				truck: current_args.truck,
				from_date: current_args.from_date,
				to_date: current_args.to_date,
			},
			freeze: true,
			freeze_message: __("Loading details..."),
			callback(r) {
				render_component_dialog(label, cfg, r.message || { columns: [], rows: [] });
			},
		});
	}

	function render_component_dialog(label, cfg, result) {
		let body_html;
		if (!result.rows || !result.rows.length) {
			body_html = `<div class="tcd-empty">${__("No underlying records found for this period")}</div>`;
		} else {
			const header = result.columns.map((c) => `<th>${frappe.utils.escape_html(c)}</th>`).join("");
			const rows = result.rows
				.map(
					(row) =>
						`<tr>${row.map((cell) => `<td>${frappe.utils.escape_html(String(cell))}</td>`).join("")}</tr>`
				)
				.join("");
			body_html = `
				<div class="tcd-detail-table-wrap">
					<table class="table table-bordered tcd-detail-table">
						<thead><tr>${header}</tr></thead>
						<tbody>${rows}</tbody>
					</table>
				</div>
				<div class="tcd-detail-count">${__("{0} record(s)", [result.rows.length])}</div>
			`;
		}

		const dialog = new frappe.ui.Dialog({
			title: `${label} — ${__("Components")}`,
			size: "extra-large",
			fields: [{ fieldtype: "HTML", fieldname: "detail_html", options: body_html }],
		});

		if (cfg.list_doctype) {
			dialog.set_primary_action(__("Open Full List"), () => {
				dialog.hide();
				const route_filters = {};
				if (current_args.truck) route_filters.truck = current_args.truck;
				frappe.route_options = route_filters;
				frappe.set_route("List", cfg.list_doctype);
			});
		}

		dialog.show();
	}

	function render_panel_row(data) {
		const $row = $('<div class="tcd-panel-row"></div>').appendTo($body);
		render_breakdown_panel($row, data);
		render_performance_panel($row, data);
		render_trend_panel($row, data);
	}

	function render_breakdown_panel($row, data) {
		const $panel = $(`<div class="tcd-panel tcd-breakdown"><h4>${__("Cost Breakdown")}</h4></div>`).appendTo($row);

		if (!data.breakdown.length) {
			$panel.append(`<div class="tcd-empty">${__("No costs recorded in this period")}</div>`);
			return;
		}

		const $donutWrap = $('<div class="tcd-donut-wrap"></div>').appendTo($panel);

		if (chartjs_ready && window.Chart) {
			render_chartjs_doughnut($donutWrap, data);
		} else {
			// Graceful fallback: pure-CSS donut, no external library needed.
			// Used if Chart.js hasn't finished loading yet or failed to load.
			render_css_donut($donutWrap, data);
		}

		const $legend = $('<div class="tcd-legend"></div>').appendTo($panel);
		data.breakdown.forEach((b) => {
			$(`
				<div class="tcd-legend-row">
					<span class="tcd-legend-dot" style="background:${b.color}"></span>
					<span class="tcd-legend-label">${frappe.utils.escape_html(b.label)}</span>
					<span class="tcd-legend-pct">${b.percent.toFixed(1)}%</span>
				</div>
			`).appendTo($legend);
		});
	}

	function render_chartjs_doughnut($wrap, data) {
		const $canvasHolder = $('<div class="tcd-donut-canvas-wrap"></div>').appendTo($wrap);
		const canvas = document.createElement("canvas");
		canvas.width = 170;
		canvas.height = 170;
		$canvasHolder[0].appendChild ? $canvasHolder[0].appendChild(canvas) : $canvasHolder.append(canvas);

		const centerTextPlugin = {
			id: "tcdCenterText",
			afterDraw(chart) {
				const { ctx, chartArea } = chart;
				if (!chartArea) return;
				const cx = (chartArea.left + chartArea.right) / 2;
				const cy = (chartArea.top + chartArea.bottom) / 2;
				ctx.save();
				ctx.textAlign = "center";
				ctx.textBaseline = "middle";
				ctx.fillStyle = "#888";
				ctx.font = "10px sans-serif";
				ctx.fillText(__("TOTAL COST"), cx, cy - 10);
				ctx.fillStyle = "#222";
				ctx.font = "bold 13px sans-serif";
				ctx.fillText(fmt_money(data.total_cost), cx, cy + 8);
				ctx.restore();
			},
		};

		doughnut_instance = new window.Chart(canvas.getContext("2d"), {
			type: "doughnut",
			data: {
				labels: data.breakdown.map((b) => b.label),
				datasets: [
					{
						data: data.breakdown.map((b) => b.value),
						backgroundColor: data.breakdown.map((b) => b.color),
						borderWidth: 2,
						borderColor: "#fff",
					},
				],
			},
			options: {
				cutout: "62%",
				plugins: {
					legend: { display: false },
					tooltip: {
						callbacks: {
							label(ctx) {
								const b = data.breakdown[ctx.dataIndex];
								return ` ${b.label}: ${fmt_money(b.value)} (${b.percent.toFixed(1)}%)`;
							},
						},
					},
				},
			},
			plugins: [centerTextPlugin],
		});
	}

	function render_css_donut($wrap, data) {
		let cumulative = 0;
		const stops = data.breakdown
			.map((b) => {
				const start = cumulative;
				cumulative += b.percent;
				return `${b.color} ${start}% ${cumulative}%`;
			})
			.join(", ");

		$(`
			<div class="tcd-donut" style="background: conic-gradient(${stops});">
				<div class="tcd-donut-center">
					<div class="tcd-donut-center-label">${__("TOTAL COST")}</div>
					<div class="tcd-donut-center-value">${fmt_money(data.total_cost)}</div>
				</div>
			</div>
		`).appendTo($wrap);
	}

	function render_performance_panel($row, data) {
		const $panel = $(`<div class="tcd-panel tcd-performance"><h4>${__("Performance Summary")}</h4></div>`).appendTo($row);

		const profit_class = data.profit_loss >= 0 ? "tcd-green" : "tcd-red";
		const rows = [
			[__("Fuel Efficiency"), `${data.avg_efficiency.toFixed(2)} km/L`, ""],
			[__("Cost per KM"), fmt_money(data.cost_per_km), ""],
			[__("Revenue"), fmt_money(data.revenue), "tcd-green"],
			[__("Profit / Loss"), fmt_money(data.profit_loss), profit_class],
			[__("Profit per KM"), fmt_money(data.profit_per_km), profit_class],
		];

		rows.forEach(([label, value, cls]) => {
			$(`
				<div class="tcd-perf-row">
					<span>${label}</span>
					<b class="${cls}">${value}</b>
				</div>
			`).appendTo($panel);
		});
	}

	function render_trend_panel($row, data) {
		const $panel = $(`<div class="tcd-panel tcd-trend"><h4>${__("Cost Trend")} (${frappe.defaults.get_default("currency") || ""})</h4></div>`).appendTo($row);
		const $chartHolder = $('<div class="tcd-trend-chart"></div>').appendTo($panel);

		if (!data.trend.some((t) => t.total_cost || t.revenue)) {
			$chartHolder.html(`<div class="tcd-empty">${__("No historical data yet")}</div>`);
			return;
		}

		// Trend line intentionally still uses frappe.Chart (bundled with
		// Frappe, no CDN needed) — only the donut and icons were requested
		// to move to CDN-based libraries.
		new frappe.Chart($chartHolder[0], {
			data: {
				labels: data.trend.map((t) => t.month),
				datasets: [
					{ name: __("Total Cost"), values: data.trend.map((t) => Math.round(t.total_cost)) },
					{ name: __("Revenue"), values: data.trend.map((t) => Math.round(t.revenue)) },
				],
			},
			type: "line",
			height: 230,
			colors: ["#2E86C1", "#27AE60"],
			lineOptions: { hideDots: 0, regionFill: 0 },
			axisOptions: { xAxisMode: "tick" },
		});
	}

	function load_chartjs(callback) {
		if (window.Chart) {
			callback();
			return;
		}
		if (document.getElementById("tcd-chartjs-script")) {
			// Already being loaded by an earlier page visit in this session
			document.getElementById("tcd-chartjs-script").addEventListener("load", callback);
			return;
		}
		const script = document.createElement("script");
		script.id = "tcd-chartjs-script";
		script.src = TCD_CHARTJS_URL;
		script.onload = callback;
		script.onerror = () => {
			console.warn("Truck Cost Dashboard: Chart.js failed to load from CDN — falling back to CSS donut.");
		};
		document.head.appendChild(script);
	}

	function load_fontawesome() {
		if (document.getElementById("tcd-fontawesome-css")) return;
		const link = document.createElement("link");
		link.id = "tcd-fontawesome-css";
		link.rel = "stylesheet";
		link.href = TCD_FONTAWESOME_CSS_URL;
		document.head.appendChild(link);
	}

	function inject_styles() {
		if (document.getElementById("tcd-styles")) return;
		const style = document.createElement("style");
		style.id = "tcd-styles";
		style.innerHTML = `
			.tcd-wrapper { padding: 10px 5px 30px; }
			.tcd-scope { margin-bottom: 12px; color: var(--text-muted); }
			.tcd-kpi-row {
				display: grid;
				grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
				gap: 12px;
				margin-bottom: 20px;
			}
			.tcd-kpi-card {
				background: var(--card-bg, #fff);
				border: 1px solid var(--border-color, #e0e0e0);
				border-radius: 10px;
				padding: 14px;
				display: flex;
				align-items: center;
				gap: 12px;
			}
			.tcd-kpi-clickable { cursor: pointer; transition: box-shadow 0.15s, transform 0.15s; }
			.tcd-kpi-clickable:hover { box-shadow: 0 2px 10px rgba(0,0,0,0.1); transform: translateY(-2px); }
			.tcd-kpi-icon { font-size: 20px; color: #5DADE2; width: 24px; text-align: center; }
			.tcd-kpi-icon.tcd-highlight { color: #C0392B; }
			.tcd-kpi-label { font-size: 11px; color: var(--text-muted); letter-spacing: 0.5px; text-transform: uppercase; }
			.tcd-kpi-value { font-size: 18px; font-weight: 600; margin-top: 2px; }
			.tcd-kpi-value.tcd-highlight { color: #C0392B; }
			.tcd-panel-row {
				display: grid;
				grid-template-columns: 1fr 1fr 1.3fr;
				gap: 16px;
			}
			.tcd-panel {
				background: var(--card-bg, #fff);
				border: 1px solid var(--border-color, #e0e0e0);
				border-radius: 10px;
				padding: 16px;
			}
			.tcd-panel h4 { margin: 0 0 14px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); }
			.tcd-donut-wrap { display: flex; justify-content: center; margin-bottom: 16px; }
			.tcd-donut-canvas-wrap { width: 170px; height: 170px; }
			.tcd-donut {
				width: 150px; height: 150px; border-radius: 50%;
				display: flex; align-items: center; justify-content: center;
			}
			.tcd-donut-center {
				width: 96px; height: 96px; border-radius: 50%;
				background: var(--card-bg, #fff);
				display: flex; flex-direction: column; align-items: center; justify-content: center;
				text-align: center;
			}
			.tcd-donut-center-label { font-size: 9px; color: var(--text-muted); text-transform: uppercase; }
			.tcd-donut-center-value { font-size: 13px; font-weight: 700; }
			.tcd-legend-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13px; }
			.tcd-legend-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
			.tcd-legend-label { flex: 1; }
			.tcd-legend-pct { font-weight: 600; }
			.tcd-perf-row {
				display: flex; justify-content: space-between; align-items: center;
				padding: 9px 0; border-bottom: 1px solid var(--border-color, #f0f0f0);
				font-size: 13px;
			}
			.tcd-perf-row:last-child { border-bottom: none; }
			.tcd-green { color: #27AE60; }
			.tcd-red { color: #C0392B; }
			.tcd-empty { color: var(--text-muted); text-align: center; padding: 30px 0; font-size: 13px; }
			.tcd-detail-table-wrap { max-height: 420px; overflow-y: auto; }
			.tcd-detail-table { width: 100%; font-size: 12px; }
			.tcd-detail-table th { position: sticky; top: 0; background: var(--card-bg, #fff); white-space: nowrap; }
			.tcd-detail-table td { white-space: nowrap; }
			.tcd-detail-count { margin-top: 10px; font-size: 12px; color: var(--text-muted); }
			@media (max-width: 900px) {
				.tcd-panel-row { grid-template-columns: 1fr; }
			}
		`;
		document.head.appendChild(style);
	}

	render();
};
