"""Generate missing canonical demo CSVs and validate them, without network access.

Existing CSVs are editable sources: never overwritten. To generate a pristine
copy, point --output-dir at an empty directory. No application/.env imports.
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from counterpilot.catalog_io import (ALIAS_COLUMNS, DATA_DIR, PART_COLUMNS, PART_TYPES,
                                    VEHICLE_COLUMNS, VERIFIED_COLUMNS, PRICE_COLUMNS, demo_price, read_csv, validate_rows)

# Original five profiles retain their order/part numbers; append new fictional profiles.
PROFILES = [
    ("F150-01", "2021", "Ford", "F-150", "3.5L EcoBoost", "XLT", "4WD"),
    ("RAV4-01", "2019", "Toyota", "RAV4", "2.5L", "XLE", "AWD"),
    ("CRV-01", "2023", "Honda", "CR-V", "1.5T", "EX", "AWD"),
    ("SIL1500-01", "2021", "Chevrolet", "Silverado 1500", "5.3L", "LT", "4WD"),
    ("TIGUAN-01", "2021", "Volkswagen", "Tiguan", "2.0T", "SE", "FWD"),
    ("SX4-01", "2007", "Suzuki", "SX4", "2.0L", "unknown", "AWD"),
]
ALIASES = {
    "oil_filter": ["oil filter", "oil filters", "engine oil filter"],
    "air_filter": ["air filter", "air filters", "engine air filter", "engine air filters", "air cleaner"],
    "cabin_filter": ["cabin filter", "cabin air filter", "cabin filters", "pollen filter", "AC filter"],
    "spark_plug": ["spark plug", "spark plugs", "plugs"],
    "ignition_coil": ["ignition coil", "ignition coils", "coil pack", "coil packs"],
    "brake_pad": ["brake pads", "brake pad", "pads", "disc brake pads"],
    "brake_shoe": ["brake shoes", "brake shoe", "drum brake shoes"],
    "brake_rotor": ["rotor", "rotors", "brake rotor", "brake rotors", "brake disc", "brake discs", "brake disk", "brake disks"],
    "brake_caliper": ["caliper", "calipers", "brake caliper", "brake calipers"],
    "starter": ["starter", "starter motor"], "alternator": ["alternator", "alternators"],
    "shock_absorber": ["shock", "shocks", "shock absorber", "shock absorbers"],
    "strut_assembly": ["strut", "struts", "strut assembly", "strut assemblies"],
    "control_arm": ["control arm", "control arms", "lower control arm", "wishbone"],
    "tie_rod_end": ["tie rod", "tie rods", "tie rod end", "outer tie rod", "outer tie rod end"],
    "radiator": ["radiator"], "thermostat": ["thermostat"], "water_pump": ["water pump", "coolant pump"],
    "fuel_pump": ["fuel pump", "fuel pump module"],
    "cv_axle": ["CV axle", "CV axles", "CV shaft", "half shaft", "halfshaft", "drive axle"],
    "wheel_hub": ["wheel hub", "wheel bearing", "hub bearing", "hub assembly", "wheel hub bearing"],
    "serpentine_belt": ["serpentine belt", "drive belt", "accessory belt", "fan belt"],
    "belt_tensioner": ["belt tensioner", "serpentine belt tensioner", "tensioner"],
    "wiper_blade": ["wiper", "wipers", "wiper blade", "wiper blades", "windshield wipers"],
}


def default_vehicles():
    rows = []
    for vehicle_id, year, make, model, engine, trim, drivetrain in PROFILES:
        rows.append(dict(zip(VEHICLE_COLUMNS, [
            vehicle_id, year, make, model, engine, trim, drivetrain, "gasoline", "unknown", "unknown", "unknown",
            "true" if vehicle_id == "RAV4-01" else "false", f"{engine} · {'trim unknown' if trim == 'unknown' else trim} · {drivetrain}",
            "sample", "generated_demo", ("User-requested fictional demo scenario. Trim is unknown. " if vehicle_id == "SX4-01" else "Reused fictional scenario. ") + "Gasoline is an unverified demo assumption; actual brake and steering equipment is unknown.",
        ])))
    return rows


def applications(vehicle):
    electric = vehicle["fuel_type"] == "electric"
    entries = [("cabin_filter", "", "")] if electric else [("oil_filter", "", ""), ("air_filter", "", ""), ("cabin_filter", "", "")]
    if vehicle["fuel_type"] == "gasoline":
        entries += [("spark_plug", "", ""), ("ignition_coil", "", "")]
    for position in ("front", "rear"):
        if vehicle[position + "_brakes"] == "drum":
            entries.append(("brake_shoe", position, ""))
        else:
            entries += [("brake_pad", position, ""), ("brake_rotor", position, "")]
    if vehicle["front_brakes"] != "drum":
        entries += [("brake_caliper", "front", side) for side in ("left", "right")]
    if vehicle["fuel_type"] not in {"hybrid", "electric"}:
        entries += [("starter", "", ""), ("alternator", "", "")]
    # Style is explicitly a sample assumption, not equipment authority.
    front_damper = "shock_absorber" if vehicle["model"] in {"F-150", "Silverado 1500"} else "strut_assembly"
    entries += [(front_damper, "front", ""), ("shock_absorber", "rear", "")]
    for part_type in ("control_arm", "tie_rod_end"):
        entries += [(part_type, "front", side) for side in ("left", "right")]
    cooling_fuel = ("radiator", "water_pump") if electric else ("radiator", "thermostat", "water_pump", "fuel_pump")
    entries += [(part_type, "", "") for part_type in cooling_fuel]
    for part_type in ("cv_axle", "wheel_hub"):
        entries += [(part_type, "front", side) for side in ("left", "right")]
    if not electric:
        entries += [("serpentine_belt", "", ""), ("belt_tensioner", "", "")]
    entries += [("wiper_blade", "front", "")]
    # No hydraulic steering pump is assumed for an unknown/electric system.
    return entries


def build_parts(vehicles, *, start_number=101):
    rows = []
    for vehicle in vehicles:
        for part_type, position, side in applications(vehicle):
            category, prefix, name = PART_TYPES[part_type]
            number = f"{prefix}-{start_number + len(rows):05d}"
            note = (f"Simulated fitment for {vehicle['year']} {vehicle['make']} {vehicle['model']} ({vehicle['description']}). "
                    "Unverified demo assumption: application, equipment, mounting and assembly style. Not manufacturer fitment evidence.")
            if part_type in {"brake_pad", "brake_rotor", "brake_caliper"} and vehicle[position + "_brakes"] == "unknown":
                note += f" {position.capitalize()} disc brakes are an unverified demo assumption."
            if part_type in {"starter", "alternator"}:
                note += " Conventional starting/charging equipment is an unverified demo assumption."
            rows.append(dict(zip(PART_COLUMNS, ["DEMO-" + number, vehicle["vehicle_id"], number, "CounterPilot Demo",
                         category, part_type, " ".join(filter(None, [position.capitalize(), side.capitalize(), name])),
                         position, side, note, "sample", "generated_demo"])))
            rows[-1].update(demo_price(part_type))
    return rows


def csv_bytes(columns, rows):
    if columns in (PART_COLUMNS, VERIFIED_COLUMNS) and any(any(field in row for field in PRICE_COLUMNS) for row in rows):
        columns = columns + PRICE_COLUMNS
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def generate(directory: Path):
    # Read and validate every existing file before creating anything. No overwrite
    # flag: manual edits and the verified source always survive regeneration.
    vehicle_file = directory / "vehicles.csv"
    vehicles = read_csv(vehicle_file, VEHICLE_COLUMNS) if vehicle_file.exists() else default_vehicles()
    parts_file = directory / "parts.csv"
    parts = read_csv(parts_file, PART_COLUMNS) if parts_file.exists() else build_parts(vehicles)
    active_types = {row["part_type"] for row in parts}
    alias_rows = [{"alias": alias.casefold(), "part_type": kind} for kind, names in ALIASES.items()
                  if kind in active_types for alias in names]
    alias_file = directory / "part_aliases.csv"
    aliases = read_csv(alias_file, ALIAS_COLUMNS) if alias_file.exists() else sorted(alias_rows, key=lambda row: row["alias"])
    verified_file = directory / "parts_verified.csv"
    verified = read_csv(verified_file, VERIFIED_COLUMNS) if verified_file.exists() else []
    errors = validate_rows(vehicles, parts, aliases, verified)
    print(f"Vehicles: {len(vehicles)} | Sample applications: {len(parts)} | Verified applications: {len(verified)} | Aliases: {len(aliases)}")
    if errors:
        for error in errors:
            print("ERROR: " + error)
        raise ValueError(f"{len(errors)} validation error(s); no files written")
    directory.mkdir(parents=True, exist_ok=True)
    for name, columns, rows in (("vehicles.csv", VEHICLE_COLUMNS, vehicles), ("parts.csv", PART_COLUMNS, parts),
                               ("part_aliases.csv", ALIAS_COLUMNS, aliases), ("parts_verified.csv", VERIFIED_COLUMNS, verified)):
        path = directory / name
        if path.exists():
            print(f"Preserved: {path}")
        else:
            with path.open("xb") as stream:
                stream.write(csv_bytes(columns, rows))
            print(f"Created: {path}")
    print("Validation errors: 0")
    print("Excel: not generated; CSV is the canonical editable source.")
    return vehicles, parts, aliases, verified


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR, help="Default: counterpilot/data; use an empty directory for pristine samples")
    args = parser.parse_args()
    try:
        generate(args.output_dir.resolve())
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
