"""Canonical CSV schema, taxonomy and validation. Standard library only."""
from __future__ import annotations

import csv
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

DATA_DIR = Path(__file__).with_name("data")
VEHICLE_COLUMNS = ["vehicle_id", "year", "make", "model", "engine", "trim", "drivetrain",
                   "fuel_type", "front_brakes", "rear_brakes", "steering_type", "featured",
                   "description", "data_status", "source", "fitment_notes"]
PART_COLUMNS = ["part_id", "vehicle_id", "part_number", "brand", "category", "part_type",
                "name", "position", "side", "fitment_notes", "data_status", "source"]
VERIFIED_COLUMNS = PART_COLUMNS + ["source_reference", "verification_date"]
PRICE_COLUMNS = ["price_amount", "currency", "price_unit"]
ALIAS_COLUMNS = ["alias", "part_type"]

# Taxonomy, not application data: all vehicle/part applications live in CSV.
# part_type -> (category, fictional number prefix, display name)
PART_TYPES = {
    "oil_filter": ("filters", "FL", "Oil filter"),
    "air_filter": ("filters", "FL", "Engine air filter"),
    "cabin_filter": ("filters", "FL", "Cabin air filter"),
    "spark_plug": ("ignition", "SP", "Spark plug"),
    "ignition_coil": ("ignition", "IC", "Ignition coil"),
    "brake_pad": ("brakes", "BR", "Brake pads"),
    "brake_shoe": ("brakes", "BR", "Brake shoes"),
    "brake_rotor": ("brakes", "RT", "Brake rotor"),
    "brake_caliper": ("brakes", "CL", "Brake caliper"),
    "starter": ("starting_charging", "ST", "Starter motor"),
    "alternator": ("starting_charging", "AL", "Alternator"),
    "shock_absorber": ("suspension", "SU", "Shock absorber"),
    "strut_assembly": ("suspension", "SU", "Strut assembly"),
    "control_arm": ("suspension", "SU", "Control arm"),
    "tie_rod_end": ("steering", "SR", "Outer tie rod end"),
    "radiator": ("cooling", "CO", "Radiator"),
    "thermostat": ("cooling", "CO", "Thermostat"),
    "water_pump": ("cooling", "CO", "Water pump"),
    "fuel_pump": ("fuel_delivery", "FP", "Fuel pump"),
    "cv_axle": ("drivetrain", "AX", "CV axle"),
    "wheel_hub": ("hubs_bearings", "HB", "Wheel hub / bearing assembly"),
    "serpentine_belt": ("belts", "BT", "Serpentine belt"),
    "belt_tensioner": ("belts", "BT", "Belt tensioner"),
    "wiper_blade": ("wipers", "WP", "Wiper blade pair"),
}

# Fictional presentation prices, never manufacturer or supplier quotations.
DEMO_PRICES = {
    "oil_filter": "12.95", "air_filter": "24.95", "cabin_filter": "22.95",
    "spark_plug": "9.95", "ignition_coil": "49.95", "brake_pad": "54.95",
    "brake_shoe": "44.95", "brake_rotor": "69.95", "brake_caliper": "89.95",
    "starter": "149.95", "alternator": "189.95", "shock_absorber": "64.95",
    "strut_assembly": "159.95", "control_arm": "94.95", "tie_rod_end": "34.95",
    "radiator": "179.95", "thermostat": "19.95", "water_pump": "79.95",
    "fuel_pump": "129.95", "cv_axle": "109.95", "wheel_hub": "89.95",
    "serpentine_belt": "29.95", "belt_tensioner": "59.95", "wiper_blade": "32.95",
}


def demo_price(part_type):
    return dict(price_amount=DEMO_PRICES[part_type], currency="USD",
                price_unit="axle set" if part_type in {"brake_pad", "brake_shoe"} else "pair" if part_type == "wiper_blade" else "each")


def price_metadata(part):
    amount = part.get("price_amount", "")
    if not amount:
        return None
    return {"amount": format(Decimal(amount), ".2f"), "currency": part["currency"],
            "unit": part["price_unit"], "is_sample": part["data_status"] == "sample"}


def image_metadata(part_type):
    if part_type not in PART_TYPES:
        return None
    return {"url": f"/static/parts/{part_type}.jpg", "alt": f"Generic {PART_TYPES[part_type][2].lower()} on a neutral background",
            "is_generic": True}


def read_csv(path: Path, columns: list[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        allowed = [columns, columns + PRICE_COLUMNS] if columns in (PART_COLUMNS, VERIFIED_COLUMNS) else [columns]
        if reader.fieldnames not in allowed:
            raise ValueError(f"{path.name}: headers must be {', '.join(columns)}")
        rows = []
        for number, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{path.name}: row {number} has the wrong number of cells")
            rows.append({field: value.strip() for field, value in row.items()})
        return rows


def validate_rows(vehicles, parts, aliases, verified=()) -> list[str]:
    errors = []
    vehicle_ids, part_ids, sample_numbers, alias_names = set(), set(), set(), set()
    for index, vehicle in enumerate(vehicles, 2):
        label = f"vehicles.csv row {index}"
        if any(not vehicle.get(field) for field in VEHICLE_COLUMNS):
            errors.append(f"{label}: required vehicle field is blank")
        if vehicle.get("vehicle_id") in vehicle_ids:
            errors.append(f"{label}: duplicate vehicle_id")
        vehicle_ids.add(vehicle.get("vehicle_id"))
        year = vehicle.get("year", "")
        if not re.fullmatch(r"\d{4}", year) or not 1980 <= int(year) <= 2100:
            errors.append(f"{label}: year must be a four-digit value from 1980 to 2100")
        if vehicle.get("fuel_type") not in {"gasoline", "diesel", "hybrid", "electric", "unknown"}:
            errors.append(f"{label}: invalid fuel_type")
        for field in ("front_brakes", "rear_brakes"):
            if vehicle.get(field) not in {"disc", "drum", "unknown"}:
                errors.append(f"{label}: invalid {field}")
        if vehicle.get("steering_type") not in {"electric", "hydraulic", "unknown"}:
            errors.append(f"{label}: invalid steering_type")
        if vehicle.get("featured") not in {"true", "false"}:
            errors.append(f"{label}: featured must be true or false")
    if not vehicles:
        errors.append("vehicles.csv: at least one vehicle is required")
    if sum(v.get("featured") == "true" for v in vehicles) > 1:
        errors.append("vehicles.csv: only one vehicle can be featured")
    vehicle_map = {v["vehicle_id"]: v for v in vehicles}
    for source_rows, filename, status in ((parts, "parts.csv", "sample"), (verified, "parts_verified.csv", "verified")):
        for index, part in enumerate(source_rows, 2):
            label = f"{filename} row {index}"
            required = [field for field in PART_COLUMNS if field not in {"position", "side"}]
            if any(not part.get(field) for field in required):
                errors.append(f"{label}: required part field is blank")
            if part.get("part_id") in part_ids:
                errors.append(f"{label}: duplicate part_id")
            part_ids.add(part.get("part_id"))
            if part.get("vehicle_id") not in vehicle_ids:
                errors.append(f"{label}: unknown vehicle_id")
            taxonomy = PART_TYPES.get(part.get("part_type"))
            if not taxonomy or part.get("category") != taxonomy[0]:
                errors.append(f"{label}: invalid part_type/category mapping")
            if part.get("position") not in {"", "front", "rear"} or part.get("side") not in {"", "left", "right"}:
                errors.append(f"{label}: invalid position or side")
            if part.get("data_status") != status:
                errors.append(f"{label}: data_status must be {status}")
            pricing = [part.get(field, "") for field in PRICE_COLUMNS]
            if any(pricing):
                try:
                    amount = Decimal(pricing[0])
                    valid = amount.is_finite() and 0 < amount <= Decimal("999999.99") and amount == amount.quantize(Decimal("0.01"))
                except (InvalidOperation, ValueError):
                    valid = False
                if not valid or pricing[1] != "USD" or pricing[2] not in {"each", "axle set", "pair"}:
                    errors.append(f"{label}: price requires a positive USD amount with at most two decimals and a supported unit")
            if status == "sample":
                if part.get("brand") != "CounterPilot Demo" or part.get("source") != "generated_demo":
                    errors.append(f"{label}: invalid sample brand/source")
                if "simulated fitment" not in part.get("fitment_notes", "").casefold():
                    errors.append(f"{label}: sample must disclose simulated fitment")
                number = part.get("part_number", "")
                if not taxonomy or not re.fullmatch(re.escape(taxonomy[1]) + r"-\d{5}", number):
                    errors.append(f"{label}: invalid fictional part number")
                if number in sample_numbers:
                    errors.append(f"{label}: duplicate fictional part number")
                sample_numbers.add(number)
                if part.get("part_id") != "DEMO-" + number:
                    errors.append(f"{label}: part_id must be DEMO-<part_number>")
                vehicle = vehicle_map.get(part.get("vehicle_id"), {})
                if vehicle.get("fuel_type") in {"diesel", "electric"} and part.get("part_type") in {"spark_plug", "ignition_coil"}:
                    errors.append(f"{label}: ignition application conflicts with fuel_type")
                if vehicle.get("fuel_type") == "electric" and part.get("part_type") in {"oil_filter", "air_filter", "starter", "alternator", "fuel_pump", "serpentine_belt", "belt_tensioner"}:
                    errors.append(f"{label}: conventional engine application conflicts with electric fuel_type")
                brakes = vehicle.get(part.get("position", "") + "_brakes")
                if brakes == "drum" and part.get("part_type") in {"brake_rotor", "brake_pad", "brake_caliper"}:
                    errors.append(f"{label}: disc-brake application conflicts with drum configuration")
            else:
                if (part.get("brand", "").casefold() == "counterpilot demo"
                        or part.get("source") == "generated_demo" or part.get("part_id", "").startswith("DEMO-")):
                    errors.append(f"{label}: generated demo identities cannot be marked verified")
                if not part.get("source_reference"):
                    errors.append(f"{label}: source_reference is required for verified records")
                try:
                    stamp = part.get("verification_date", "")
                    if date.fromisoformat(stamp).isoformat() != stamp:
                        raise ValueError
                except ValueError:
                    errors.append(f"{label}: verification_date must be YYYY-MM-DD")
    targets = {part.get("part_type") for part in [*parts, *verified]}
    for index, alias in enumerate(aliases, 2):
        name = alias.get("alias", "").casefold()
        if not name or name in alias_names:
            errors.append(f"part_aliases.csv row {index}: blank or duplicate alias")
        alias_names.add(name)
        if alias.get("part_type") not in targets:
            errors.append(f"part_aliases.csv row {index}: alias target has no application")
    return errors


def read_sources(directory: Path = DATA_DIR):
    vehicles = read_csv(directory / "vehicles.csv", VEHICLE_COLUMNS)
    parts = read_csv(directory / "parts.csv", PART_COLUMNS)
    aliases = read_csv(directory / "part_aliases.csv", ALIAS_COLUMNS)
    verified_path = directory / "parts_verified.csv"
    verified = read_csv(verified_path, VERIFIED_COLUMNS) if verified_path.exists() else []
    errors = validate_rows(vehicles, parts, aliases, verified)
    if errors:
        raise ValueError("Catalog validation failed:\n" + "\n".join(errors))
    return vehicles, parts, aliases, verified
