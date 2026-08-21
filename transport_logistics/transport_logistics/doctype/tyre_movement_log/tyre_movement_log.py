# Copyright (c) 2026, Wycliffs and contributors
# For license information, please see license.txt

"""
Tyre positions aren't a fixed list — fleets are mixed: some trucks have 1
front axle + 1 rear axle, others have 1 front + 3 rear (or more), and
trailers in this fleet are normally 3-axle (see Truck.front_axle_count /
Truck.rear_axle_count / Trailer.axle_count). So instead of a hardcoded
"Front Left / Rear Right Outer / ..." Select list, a position here is built
from (vehicle type, axle type, axle number, side) and validated against
that specific vehicle's configured axle counts, or flagged as the Spare.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt, nowdate

from transport_logistics.transport_logistics.manager_approval import (
	block_submit_if_not_approved,
	flag_pending_approval,
)


class TyreMovementLog(Document):
	def validate(self):
		validate_movement(self)
		enforce_tyre_change_approval(self)


def _tyre_change_requires_approval(doc):
	return doc.movement_type in ("Fitted", "Removed")


def enforce_tyre_change_approval(doc, method=None):
	"""Fitting or removing a tyre (i.e. a tyre change) requires System
	Manager sign-off before this log can be submitted. Rotations,
	retreading, and scrapping are left unrestricted."""
	flag_pending_approval(doc, _tyre_change_requires_approval)
	block_submit_if_not_approved(doc, "a tyre change (fit/removal)")


def build_position_label(vehicle_type, is_spare, axle_type, axle_number, side):
	if cint(is_spare):
		return "Spare"
	if vehicle_type == "Truck":
		return f"{axle_type} Axle {cint(axle_number)} - {side}"
	if vehicle_type == "Trailer":
		return f"Trailer Axle {cint(axle_number)} - {side}"
	return ""


def _get_max_axles(doc):
	"""Returns (max_axles, description) for the axle group this movement is
	targeting, based on the specific truck's/trailer's configured axle
	counts — not a fleet-wide assumption."""
	if doc.vehicle_type == "Truck":
		if not doc.truck:
			frappe.throw("Truck is required for a Truck vehicle type.")
		front, rear = frappe.db.get_value(
			"Truck", doc.truck, ["front_axle_count", "rear_axle_count"]
		)
		if doc.axle_type == "Front":
			return cint(front) or 1, f"Truck {doc.truck} has {cint(front) or 1} front axle(s)"
		elif doc.axle_type == "Rear":
			return cint(rear) or 1, f"Truck {doc.truck} has {cint(rear) or 1} rear axle(s)"
		else:
			frappe.throw("Axle Type (Front/Rear) is required for a truck tyre position.")
	elif doc.vehicle_type == "Trailer":
		if not doc.trailer:
			frappe.throw("Trailer is required for a Trailer vehicle type.")
		axle_count = frappe.db.get_value("Trailer", doc.trailer, "axle_count")
		return cint(axle_count) or 3, f"Trailer {doc.trailer} has {cint(axle_count) or 3} axle(s)"
	else:
		frappe.throw("Vehicle Type must be Truck or Trailer.")


def validate_movement(doc, method=None):
	if doc.movement_type not in ("Fitted", "Rotated"):
		doc.position = "Spare" if cint(doc.is_spare) else (doc.position or "")
		return

	if not doc.vehicle_type:
		frappe.throw("Vehicle Type (Truck/Trailer) is mandatory for Fitted / Rotated movements")
	if doc.vehicle_type == "Truck" and not doc.truck:
		frappe.throw("Truck is mandatory when Vehicle Type is Truck")
	if doc.vehicle_type == "Trailer" and not doc.trailer:
		frappe.throw("Trailer is mandatory when Vehicle Type is Trailer")

	if not cint(doc.is_spare):
		if not doc.axle_number or not doc.side:
			frappe.throw("Axle Number and Side are mandatory (or tick 'This is the Spare')")

		max_axles, description = _get_max_axles(doc)
		if cint(doc.axle_number) < 1 or cint(doc.axle_number) > max_axles:
			frappe.throw(
				f"Axle Number {doc.axle_number} is out of range — {description}, so valid "
				f"axle numbers are 1 to {max_axles}."
			)

	doc.position = build_position_label(
		doc.vehicle_type, doc.is_spare, doc.axle_type, doc.axle_number, doc.side
	)

	vehicle = doc.truck if doc.vehicle_type == "Truck" else doc.trailer
	vehicle_field = "truck" if doc.vehicle_type == "Truck" else "trailer"

	if doc.movement_type == "Fitted":
		tyre_status = frappe.db.get_value("Tyre", doc.tyre, "status")
		if tyre_status == "Fitted":
			frappe.throw(
				f"Tyre {doc.tyre} is already fitted to a vehicle. Record a Removed movement for "
				"it first before fitting it elsewhere — a tyre can't be in two places at once."
			)

		existing = frappe.db.exists(
			"Tyre Movement Log",
			{
				vehicle_field: vehicle,
				"position": doc.position,
				"movement_type": "Fitted",
				"docstatus": 1,
				"name": ["!=", doc.name or ""],
			},
		)
		# only block if that position hasn't since been vacated
		if existing:
			last_on_position = frappe.db.sql(
				f"""
				select movement_type from `tabTyre Movement Log`
				where {vehicle_field}=%s and position=%s and docstatus=1 and name != %s
				order by date desc, creation desc limit 1
				""",
				(vehicle, doc.position, doc.name or ""),
			)
			if last_on_position and last_on_position[0][0] == "Fitted":
				frappe.throw(
					f"Position {doc.position} on {doc.vehicle_type} {vehicle} already has a "
					"tyre fitted. Record a Removed movement first."
				)


def apply_movement(doc, method=None):
	tyre = frappe.get_doc("Tyre", doc.tyre)

	if doc.movement_type == "Fitted":
		tyre.status = "Fitted"
		tyre.current_vehicle_type = doc.vehicle_type
		tyre.current_truck = doc.truck if doc.vehicle_type == "Truck" else None
		tyre.current_trailer = doc.trailer if doc.vehicle_type == "Trailer" else None
		tyre.current_axle_type = doc.axle_type if not cint(doc.is_spare) else None
		tyre.current_axle_number = doc.axle_number if not cint(doc.is_spare) else None
		tyre.current_side = doc.side if not cint(doc.is_spare) else None
		tyre.current_position = doc.position
		tyre.fitted_at_odometer = doc.odometer_reading or 0

	elif doc.movement_type == "Removed":
		_accumulate_km(tyre, doc)
		_clear_current_fitment(tyre)

	elif doc.movement_type == "Rotated":
		_accumulate_km(tyre, doc)
		tyre.current_axle_type = doc.axle_type if not cint(doc.is_spare) else None
		tyre.current_axle_number = doc.axle_number if not cint(doc.is_spare) else None
		tyre.current_side = doc.side if not cint(doc.is_spare) else None
		tyre.current_position = doc.position
		tyre.fitted_at_odometer = doc.odometer_reading or 0

	elif doc.movement_type == "Retreaded":
		_accumulate_km(tyre, doc)
		tyre.status = "In Stock"
		_clear_current_fitment(tyre)
		tyre.retread_count = (tyre.retread_count or 0) + 1
		tyre.flagged_for_replacement = 0

	elif doc.movement_type == "Scrapped":
		_accumulate_km(tyre, doc)
		tyre.status = "Scrapped"
		_clear_current_fitment(tyre, clear_position=False)
		tyre.flagged_for_replacement = 0

	tyre.save(ignore_permissions=True)


def _clear_current_fitment(tyre, clear_position=True):
	tyre.status = "In Stock" if tyre.status != "Scrapped" else tyre.status
	tyre.current_vehicle_type = None
	tyre.current_truck = None
	tyre.current_trailer = None
	tyre.current_axle_type = None
	tyre.current_axle_number = None
	tyre.current_side = None
	if clear_position:
		tyre.current_position = None
	tyre.fitted_at_odometer = 0


def reverse_movement(doc, method=None):
	# On cancellation, simply flag for manual review since re-deriving
	# state from movement history is safer than reversing deltas blindly.
	frappe.msgprint(
		f"Tyre Movement Log {doc.name} cancelled. Please verify Tyre {doc.tyre} "
		"current status/position manually.",
		alert=True,
	)


def _accumulate_km(tyre, doc):
	if doc.odometer_reading and tyre.fitted_at_odometer:
		km_run = doc.odometer_reading - tyre.fitted_at_odometer
		if km_run > 0:
			tyre.total_km_run = (tyre.total_km_run or 0) + km_run


@frappe.whitelist()
def create_fitment(
	tyre,
	vehicle_type,
	axle_type=None,
	axle_number=None,
	side=None,
	is_spare=0,
	truck=None,
	trailer=None,
	odometer_reading=None,
	date=None,
):
	"""Convenience wrapper behind the 'Fit to Truck/Trailer' button on the
	Tyre, Truck, and Trailer forms — associating a tyre with a vehicle
	always goes through a real, submitted Tyre Movement Log record (never
	a silent edit to Tyre.current_*), so the axle-count validation and
	audit trail in validate_movement()/apply_movement() above still apply."""
	doc = frappe.get_doc(
		{
			"doctype": "Tyre Movement Log",
			"tyre": tyre,
			"vehicle_type": vehicle_type,
			"truck": truck,
			"trailer": trailer,
			"is_spare": cint(is_spare),
			"axle_type": axle_type,
			"axle_number": cint(axle_number) if axle_number else None,
			"side": side,
			"movement_type": "Fitted",
			"date": date or nowdate(),
			"odometer_reading": flt(odometer_reading) if odometer_reading else None,
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


@frappe.whitelist()
def create_removal(tyre, odometer_reading=None, date=None, remarks=None):
	"""Convenience wrapper behind the 'Remove from Truck/Trailer' button —
	same idea as create_fitment() above, for movement_type=Removed. Reads
	the tyre's current fitment fields itself so the caller doesn't have to."""
	tyre_data = frappe.db.get_value(
		"Tyre",
		tyre,
		[
			"current_vehicle_type",
			"current_truck",
			"current_trailer",
			"current_axle_type",
			"current_axle_number",
			"current_side",
			"current_position",
		],
		as_dict=True,
	)
	if not tyre_data or not (tyre_data.current_truck or tyre_data.current_trailer):
		frappe.throw(f"Tyre {tyre} is not currently fitted to any vehicle.")

	is_spare = 1 if tyre_data.current_position == "Spare" else 0

	doc = frappe.get_doc(
		{
			"doctype": "Tyre Movement Log",
			"tyre": tyre,
			"vehicle_type": tyre_data.current_vehicle_type,
			"truck": tyre_data.current_truck,
			"trailer": tyre_data.current_trailer,
			"is_spare": is_spare,
			"axle_type": tyre_data.current_axle_type,
			"axle_number": tyre_data.current_axle_number,
			"side": tyre_data.current_side,
			"movement_type": "Removed",
			"date": date or nowdate(),
			"odometer_reading": flt(odometer_reading) if odometer_reading else None,
			"remarks": remarks,
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


@frappe.whitelist()
def get_axle_config(vehicle_type, vehicle):
	"""Used by the client scripts to build the Axle Number options for
	whichever specific truck/trailer was selected, instead of guessing at
	a fleet-wide default."""
	if vehicle_type == "Truck":
		front, rear = frappe.db.get_value("Truck", vehicle, ["front_axle_count", "rear_axle_count"])
		return {"front_axle_count": cint(front) or 1, "rear_axle_count": cint(rear) or 1}
	elif vehicle_type == "Trailer":
		axle_count = frappe.db.get_value("Trailer", vehicle, "axle_count")
		return {"axle_count": cint(axle_count) or 3}
	frappe.throw("Vehicle Type must be Truck or Trailer.")
