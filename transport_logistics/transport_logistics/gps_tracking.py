# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Live GPS tracking integration.

Currently supports Traccar (traccar.org) — a free, self-hosted or cloud GPS
platform that speaks the protocol used by most cheap GPS/GSM tracker
hardware (the kind typically fitted to trucks in Kenya/East Africa). If you
use a different platform, add a small function here that maps its API
response into the same (device_id, lat, lon, speed_kmh, odometer_km) shape
consumed by sync_truck_locations() below, and branch on
settings.gps_provider.

What this does, on a schedule (see hooks.py `scheduler_events`) or on
demand (Sync Now button on the Truck list/form):

  1. Logs into the configured Traccar server.
  2. Fetches devices + their latest positions.
  3. Matches each Truck (where `enable_gps_tracking` is checked) to a
     device by `gps_device_id` == Traccar's device `uniqueId`.
  4. Updates the Truck's last_latitude/last_longitude/gps_location/
     last_gps_update/last_gps_speed_kmh.
  5. If the device reports a total distance (odometer) attribute, converts
     it to Km and updates Truck.current_odometer — but only forward, and
     only if the jump since the last known value is within the configured
     sanity limit (protects against device resets/glitches silently
     corrupting fuel-efficiency and utilization reports).

Configure the server URL/credentials in Transport Logistics Settings, then
tick "Track this Truck via GPS" + set the Device ID on each Truck you want
synced.
"""

import frappe
from frappe.utils import flt, now_datetime


def _get_settings():
	settings = frappe.get_cached_doc("Transport Logistics Settings")
	if not settings.enable_gps_tracking:
		return None
	if not settings.gps_server_url or not settings.gps_username or not settings.gps_password:
		frappe.log_error(
			"GPS Tracking is enabled but Server URL / Username / Password is not fully "
			"configured in Transport Logistics Settings.",
			"GPS Tracking Sync",
		)
		return None
	return settings


def _fetch_traccar_data(settings):
	"""Returns a dict keyed by device uniqueId -> {latitude, longitude,
	speed_kmh, odometer_km}, using Traccar's REST API with HTTP Basic Auth
	(no separate session/login step needed)."""
	import requests

	base_url = settings.gps_server_url.rstrip("/")
	auth = (settings.gps_username, settings.get_password("gps_password"))

	devices_resp = requests.get(f"{base_url}/api/devices", auth=auth, timeout=30)
	devices_resp.raise_for_status()
	devices = devices_resp.json()

	positions_resp = requests.get(f"{base_url}/api/positions", auth=auth, timeout=30)
	positions_resp.raise_for_status()
	positions = positions_resp.json()

	# Map internal Traccar device id -> uniqueId (what customers actually set on the Truck)
	device_id_to_unique_id = {d.get("id"): d.get("uniqueId") for d in devices}

	data_by_unique_id = {}
	for pos in positions:
		unique_id = device_id_to_unique_id.get(pos.get("deviceId"))
		if not unique_id:
			continue

		attributes = pos.get("attributes") or {}
		# Traccar reports totalDistance in metres, when the device/protocol supports it.
		total_distance_m = attributes.get("totalDistance")
		odometer_km = flt(total_distance_m) / 1000 if total_distance_m else None

		# speed is reported in knots by Traccar's core API
		speed_knots = pos.get("speed")
		speed_kmh = flt(speed_knots) * 1.852 if speed_knots else 0

		data_by_unique_id[unique_id] = {
			"latitude": pos.get("latitude"),
			"longitude": pos.get("longitude"),
			"speed_kmh": speed_kmh,
			"odometer_km": odometer_km,
			"device_time": pos.get("deviceTime"),
		}

	return data_by_unique_id


def sync_truck_locations():
	"""Scheduled (and manually triggerable) job: pulls live positions for
	every GPS-enabled Truck and updates location + odometer."""
	settings = _get_settings()
	if not settings:
		return

	trucks = frappe.get_all(
		"Truck",
		filters={"enable_gps_tracking": 1, "gps_device_id": ["is", "set"]},
		fields=["name", "gps_device_id", "current_odometer"],
	)
	if not trucks:
		return

	try:
		if settings.gps_provider == "Traccar":
			live_data = _fetch_traccar_data(settings)
		else:
			frappe.log_error(f"Unsupported GPS provider: {settings.gps_provider}", "GPS Tracking Sync")
			return
	except Exception:
		frappe.log_error(frappe.get_traceback(), "GPS Tracking Sync - Fetch Failed")
		return

	jump_limit = flt(settings.gps_odometer_jump_limit_km) or 1000

	for truck in trucks:
		point = live_data.get(truck.gps_device_id)
		if not point or point.get("latitude") is None:
			continue

		update = {
			"last_latitude": point["latitude"],
			"last_longitude": point["longitude"],
			"last_gps_speed_kmh": point.get("speed_kmh") or 0,
			"last_gps_update": now_datetime(),
			"gps_location": frappe.as_json(
				{
					"type": "FeatureCollection",
					"features": [
						{
							"type": "Feature",
							"geometry": {
								"type": "Point",
								"coordinates": [point["longitude"], point["latitude"]],
							},
							"properties": {},
						}
					],
				}
			),
		}

		odometer_km = point.get("odometer_km")
		if odometer_km:
			current = flt(truck.current_odometer)
			if odometer_km >= current:
				if odometer_km - current <= jump_limit:
					update["current_odometer"] = odometer_km
				else:
					frappe.log_error(
						f"Truck {truck.name}: GPS odometer ({odometer_km} Km) jumped "
						f"{odometer_km - current:.1f} Km past the last recorded value "
						f"({current} Km) in a single sync, which exceeds the configured "
						f"limit of {jump_limit} Km. Ignored — check the device (possible "
						f"reset/glitch) or update Reject Odometer Jump Above in Transport "
						f"Logistics Settings if this is a genuine long trip.",
						"GPS Tracking Sync - Odometer Jump Rejected",
					)
			# if odometer_km < current: device glitch reporting a lower value — ignore silently

		frappe.db.set_value("Truck", truck.name, update, update_modified=False)

	frappe.db.commit()


@frappe.whitelist()
def sync_now(truck=None):
	"""Manual trigger — either syncs every GPS-enabled truck, or (if a
	specific truck name is passed) reports what happened for that one truck
	so the button in the UI can show a useful message."""
	settings = _get_settings()
	if not settings:
		frappe.throw(
			"GPS Tracking is not enabled/configured. Set it up in Transport Logistics Settings first."
		)

	before = None
	if truck:
		before = frappe.db.get_value(
			"Truck", truck, ["last_gps_update", "current_odometer"], as_dict=True
		)

	sync_truck_locations()

	if truck:
		after = frappe.db.get_value(
			"Truck", truck, ["last_latitude", "last_longitude", "last_gps_update", "current_odometer"],
			as_dict=True,
		)
		if not after.last_gps_update or after.last_gps_update == (before and before.last_gps_update):
			frappe.msgprint(
				"No new position was received for this truck. Check that its GPS Device ID "
				"matches the Unique ID on the tracking platform, and that the device is online."
			)
		return after

	return {"status": "synced"}
