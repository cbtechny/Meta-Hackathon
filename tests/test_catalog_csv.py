import contextlib
import csv
import io
import shutil
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from counterpilot.catalog_io import (ALIAS_COLUMNS, DATA_DIR, PART_COLUMNS, VEHICLE_COLUMNS,
                                    VERIFIED_COLUMNS, read_csv, read_sources, validate_rows)
from counterpilot.domain import Criteria, extract_part_type, load_catalog, search
from counterpilot.providers import MockProvider
from counterpilot.chat import ChatDetails, lookup_reply
from scripts.generate_demo_catalog import build_parts, csv_bytes, default_vehicles, generate


class CsvCatalogTests(unittest.TestCase):
    def generate_quietly(self, directory):
        with contextlib.redirect_stdout(io.StringIO()), patch.object(socket, "socket", side_effect=AssertionError("Network forbidden")):
            return generate(directory)

    def test_repeatable_generation_and_profile_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.generate_quietly(root / "a")
            self.generate_quietly(root / "b")
            before = {p.name: p.read_bytes() for p in (root / "a").glob("*.csv")}
            self.assertEqual(before, {p.name: p.read_bytes() for p in (root / "b").glob("*.csv")})
            self.generate_quietly(root / "a")
            self.assertEqual(before, {p.name: p.read_bytes() for p in (root / "a").glob("*.csv")})
        vehicles, parts, aliases, verified = read_sources()
        self.assertEqual([v["vehicle_id"] for v in vehicles], ["F150-01", "RAV4-01", "CRV-01", "SIL1500-01", "TIGUAN-01", "SX4-01"])
        self.assertEqual(len(parts), 180)
        self.assertEqual(len({p["part_number"] for p in parts}), 180)
        self.assertTrue(all(sum(p["vehicle_id"] == v["vehicle_id"] for p in parts) == 30 for v in vehicles))

    def test_editable_and_verified_files_survive_repeated_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.generate_quietly(root)
            parts = read_csv(root / "parts.csv", PART_COLUMNS)
            parts[0]["fitment_notes"] += " Manual note retained."
            (root / "parts.csv").write_bytes(csv_bytes(PART_COLUMNS, parts))
            verified = self.verified_row(parts[0])
            (root / "parts_verified.csv").write_bytes(csv_bytes(VERIFIED_COLUMNS, [verified]))
            before = {p.name: p.read_bytes() for p in root.glob("*.csv")}
            self.generate_quietly(root)
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.glob("*.csv")})

    @staticmethod
    def verified_row(sample):
        return {**sample, "part_id": "TEST-REAL-001", "part_number": "000123", "brand": "Test fixture only",
                "data_status": "verified", "source": "test_fixture", "source_reference": "Unit test fixture, not real fitment evidence",
                "verification_date": "2026-11-03", "fitment_notes": "Test fixture; never delivered as real catalog data."}

    def test_verified_overrides_only_matching_vehicle_type_position_and_side(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.generate_quietly(root)
            samples = read_csv(root / "parts.csv", PART_COLUMNS)
            chosen = next(p for p in samples if p["vehicle_id"] == "RAV4-01" and p["part_type"] == "brake_caliper" and p["side"] == "left")
            (root / "parts_verified.csv").write_bytes(csv_bytes(VERIFIED_COLUMNS, [self.verified_row(chosen)]))
            catalog = load_catalog(root)
            self.assertEqual(len(catalog["parts"]), 180)
            result = search(Criteria(year=2019, make="Toyota", model="RAV4", category="brake_caliper", position="front", side="left"), catalog)
            self.assertEqual([p["part_number"] for p in result["candidates"]], ["000123"])
            record = result["candidates"][0]
            self.assertFalse(record["fictional"])
            self.assertEqual(record["display_label"], "Verified source record")
            self.assertEqual(record["verification_date"], "2026-11-03")
            right = search(Criteria(year=2019, make="Toyota", model="RAV4", category="brake_caliper", position="front", side="right"), catalog)
            self.assertEqual(right["candidates"][0]["data_status"], "sample")
            self.assertTrue(any(p["vehicle_id"] == "F150-01" and p["part_type"] == "brake_caliper" and p["side"] == "left" for p in catalog["parts"]))

    def test_identifiers_and_part_numbers_stay_strings(self):
        vehicles, parts, aliases, _ = read_sources()
        self.assertTrue(all(isinstance(p[field], str) for p in parts for field in ("part_id", "vehicle_id", "part_number")))
        self.assertTrue(all(p["brand"] == "CounterPilot Demo" and p["source"] == "generated_demo" and p["data_status"] == "sample" for p in parts))
        self.assertTrue(all("simulated fitment" in p["fitment_notes"].lower() for p in parts))

    def test_equipment_rules_for_diesel_and_drum_profiles(self):
        vehicle = {**default_vehicles()[0], "fuel_type": "diesel", "rear_brakes": "drum", "steering_type": "electric"}
        parts = build_parts([vehicle])
        self.assertFalse(any(p["part_type"] in {"spark_plug", "ignition_coil", "steering_pump"} for p in parts))
        self.assertFalse(any(p["position"] == "rear" and p["part_type"] in {"brake_rotor", "brake_pad", "brake_caliper"} for p in parts))
        self.assertTrue(any(p["position"] == "rear" and p["part_type"] == "brake_shoe" for p in parts))
        electric = build_parts([{**vehicle, "fuel_type": "electric"}])
        self.assertFalse(any(p["part_type"] in {"oil_filter", "air_filter", "fuel_pump", "starter", "alternator", "serpentine_belt", "belt_tensioner"} for p in electric))

    def test_all_new_part_types_use_shared_aliases_in_offline_lookup(self):
        for phrase, kind in (("front pads", "brake_pad"), ("starter motor", "starter"), ("coil pack", "ignition_coil"),
                             ("engine air filter", "air_filter"), ("cabin air filter", "cabin_filter"),
                             ("serpentine belt tensioner", "belt_tensioner"), ("CV shaft", "cv_axle"),
                             ("pollen filter", "cabin_filter"), ("outer tie rod", "tie_rod_end")):
            self.assertEqual(extract_part_type(phrase), kind)
            self.assertEqual(MockProvider().interpret(phrase + " for a 2019 Toyota RAV4").category, kind)

    def test_symptoms_and_multiple_part_requests_need_clarification(self):
        for text in ("2019 Toyota RAV4 engine won't start", "2019 Toyota RAV4 battery light is on", "2021 Ford F-150 squealing brakes",
                     "pads and rotors for a 2019 RAV4"):
            criteria = MockProvider().interpret(text)
            self.assertIsNone(criteria.category)
            result = search(criteria)
            self.assertEqual(result["status"], "needs_clarification")
            self.assertFalse(result["candidates"])

    def test_expanded_chat_lookup_retrieves_only_catalog_numbers(self):
        result = lookup_reply(ChatDetails(year=2019, make="Toyota", model="RAV4", engine="2.5L", part="front pads", position="front"))
        self.assertEqual(result["lookup"]["status"], "candidates")
        self.assertEqual(result["lookup"]["candidates"][0]["part_type"], "brake_pad")
        self.assertEqual(result["lookup"]["candidates"][0]["display_label"], "Demo part — simulated fitment")

    def test_every_generated_application_is_searchable_with_customer_wording(self):
        catalog = load_catalog()
        vehicles = {vehicle["id"]: vehicle for vehicle in catalog["vehicles"]}
        for part in catalog["parts"]:
            vehicle = vehicles[part["vehicle_id"]]
            text = f"{part['name']} for a {vehicle['year']} {vehicle['make']} {vehicle['model']}"
            with self.subTest(part_id=part["id"]):
                result = search(MockProvider().interpret(text))
                self.assertEqual([record["id"] for record in result["candidates"]], [part["id"]])

    def test_validation_reports_duplicate_ids_invalid_refs_fields_and_alias_targets(self):
        vehicles, parts, aliases, _ = read_sources()
        bad = [{**parts[0], "vehicle_id": "missing", "brand": "", "part_number": "bad"}, {**parts[1], "part_id": parts[0]["part_id"]}]
        errors = validate_rows(vehicles, bad, [{"alias": "made up", "part_type": "not-a-type"}])
        for fragment in ("unknown vehicle_id", "duplicate part_id", "required part field", "invalid fictional part number", "alias target"):
            self.assertTrue(any(fragment in error for error in errors), fragment)

    def test_invalid_verified_evidence_is_rejected_without_overwriting_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.generate_quietly(root)
            sample = read_csv(root / "parts.csv", PART_COLUMNS)[0]
            record = {**self.verified_row(sample), "source_reference": "", "verification_date": "not-a-date"}
            (root / "parts_verified.csv").write_bytes(csv_bytes(VERIFIED_COLUMNS, [record]))
            before = {p.name: p.read_bytes() for p in root.glob("*.csv")}
            with self.assertRaises(ValueError):
                self.generate_quietly(root)
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.glob("*.csv")})
            with self.assertRaisesRegex(ValueError, "source_reference"):
                load_catalog(root)

    def test_alias_csv_edits_are_consumed_by_existing_catalog_layer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(DATA_DIR, root / "data")
            aliases = read_csv(root / "data/part_aliases.csv", ALIAS_COLUMNS)
            aliases.append({"alias": "counter shorthand", "part_type": "oil_filter"})
            (root / "data/part_aliases.csv").write_bytes(csv_bytes(ALIAS_COLUMNS, aliases))
            self.assertEqual(extract_part_type("counter shorthand", load_catalog(root / "data")), "oil_filter")

    def test_sample_cannot_be_reclassified_as_verified_by_status_alone(self):
        vehicles, samples, aliases, _ = read_sources()
        promoted = {**samples[0], "part_id": "REAL-FAKE", "data_status": "verified",
                    "source_reference": "Test", "verification_date": "2026-11-03"}
        errors = validate_rows(vehicles, samples, aliases, [promoted])
        self.assertTrue(any("generated demo identities" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
