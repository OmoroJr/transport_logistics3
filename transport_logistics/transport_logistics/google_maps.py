# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Google Maps Distance Matrix integration — used by the Route form's
"Fetch Distance from Google Maps" button to fill in Reference Distance (Km)
from free-text Origin/Destination fields, instead of the user having to
look it up and type it in by hand.

Requires:
  1. A Google Cloud project with the "Distance Matrix API" enabled and
     billing configured (Google's API is not free beyond a small monthly
     credit).
  2. Transport Logistics Settings > Google Maps Integration:
       - Enable Google Maps Distance Lookup (checked)
       - Google Maps API Key (ideally restricted to the Distance Matrix
         API only, to limit blast radius/cost if it ever leaks)

This deliberately only calls the Distance Matrix API (driving distance
between two place strings) — it does not do autocomplete, geocoding, or
render an actual map, since Route only needs a single numeric distance
and none of those would change that.
"""

import frappe
from frappe.utils import flt


def _get_settings():
	settings = frappe.get_cached_doc("Transport Logistics Settings")
	if not settings.enable_google_maps:
		frappe.throw(
			"Google Maps Distance Lookup is not enabled. Turn it on in "
			"Transport Logistics Settings and set an API Key first."
		)
	if not settings.get_password("google_maps_api_key", raise_exception=False):
		frappe.throw("Google Maps API Key is not set in Transport Logistics Settings.")
	return settings


@frappe.whitelist()
def get_distance(origin, destination):
	"""Returns {"distance_km": float, "duration_text": str} for the driving
	distance between two free-text places, using Google's Distance Matrix
	API. Raises a user-facing error (via frappe.throw) on any failure —
	missing input, network error, or a non-OK status from Google (e.g. a
	place Google can't resolve, or an API key/billing problem) — so the
	button in route.js can just show whatever message comes back."""
	if not origin or not destination:
		frappe.throw("Both Origin and Destination are required to fetch distance.")

	settings = _get_settings()
	api_key = settings.get_password("google_maps_api_key")

	import requests

	try:
		response = requests.get(
			"https://maps.googleapis.com/maps/api/distancematrix/json",
			params={
				"origins": origin,
				"destinations": destination,
				"units": "metric",
				"key": api_key,
			},
			timeout=15,
		)
		response.raise_for_status()
	except requests.RequestException as e:
		frappe.throw(f"Could not reach Google Maps: {e}")

	data = response.json()

	if data.get("status") != "OK":
		frappe.throw(
			f"Google Maps returned an error: {data.get('status')} "
			f"{data.get('error_message') or ''}".strip()
		)

	rows = data.get("rows") or []
	elements = rows[0].get("elements") if rows else []
	element = elements[0] if elements else None

	if not element or element.get("status") != "OK":
		status = element.get("status") if element else "NO_RESULT"
		frappe.throw(
			f"Google Maps could not find a driving route between '{origin}' and "
			f"'{destination}' ({status}). Check the spelling/detail of both places."
		)

	distance_km = flt(element["distance"]["value"]) / 1000
	duration_text = element.get("duration", {}).get("text", "")

	return {"distance_km": distance_km, "duration_text": duration_text}
