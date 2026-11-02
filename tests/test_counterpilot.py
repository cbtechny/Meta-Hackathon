import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from counterpilot.app import app
from counterpilot.domain import CATALOG, Criteria, load_catalog, search
from counterpilot.providers import MockProvider, MetaProvider, ProviderError
from counterpilot_vin_lookup import decode_vin, VinLookupError


class LookupTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def query(self, text="", **criteria):
        return self.client.post("/api/search", json={"text": text, "criteria": criteria}).json()

    def test_filter_request(self):
        result = self.query("Oil filter for a 2019 Toyota RAV4")
        self.assertEqual(result["status"], "candidates")
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["candidates"][0]["category"], "oil_filter")

    def test_all_vehicle_families_and_categories(self):
        for v in CATALOG["vehicles"]:
            for category in ["oil_filter", "air_filter", "cabin_filter", "brake_rotor"]:
                with self.subTest(vehicle=v["id"], category=category):
                    result = search(Criteria(year=v["year"], make=v["make"], model=v["model"],
                                             category=category, position="front"))
                    self.assertEqual(result["status"], "candidates")
                    self.assertTrue(all(p["vehicle_id"] == v["id"] for p in result["candidates"]))

    def test_brake_split_and_position(self):
        text = "Rotors for a 2021 Ford F-150"
        result = self.query(text)
        self.assertEqual(result["questions"][0]["field"], "position")
        self.assertFalse(result["candidates"])
        result = self.query(text, position="rear")
        self.assertEqual(result["questions"][0]["field"], "brake_package")
        self.assertFalse(result["candidates"])
        standard = self.query(text, position="rear", brake_package="standard")
        heavy = self.query(text, position="rear", brake_package="heavy-duty")
        self.assertNotEqual(standard["candidates"][0]["id"], heavy["candidates"][0]["id"])
        front = self.query(text, position="front")
        self.assertEqual(front["status"], "candidates")

    def test_missing_vehicle(self):
        result = self.query("oil filter")
        self.assertEqual(result["status"], "needs_clarification")
        self.assertEqual({q["field"] for q in result["questions"]}, {"year", "make", "model"})

    def test_unknown_vehicle_and_category(self):
        self.assertEqual(self.query("alternator for a 2021 F-150")["status"], "outside_coverage")
        self.assertEqual(self.query("oil filter for a 2018 RAV4")["status"], "outside_coverage")

    def test_manual_does_not_call_provider(self):
        with patch("counterpilot.app.get_provider", side_effect=AssertionError):
            result = self.client.post("/api/search", json={"provider": "manual",
                "criteria": {"year": 2023, "make": "Honda", "model": "CR-V", "category": "cabin_filter"}})
        self.assertEqual(result.json()["status"], "candidates")

    def test_explicit_criteria_override(self):
        result = self.query("Oil filter for a 2019 RAV4", category="cabin_filter")
        self.assertEqual(result["candidates"][0]["category"], "cabin_filter")

    def test_interchange_is_not_fitment(self):
        data = copy.deepcopy(CATALOG)
        source = data["parts"][0]
        target = data["vehicles"][1]
        source["interchanges"].append({"number": "anything", "vehicle_id": target["id"]})
        data["parts"] = [source]
        result = search(Criteria(year=target["year"], make=target["make"], model=target["model"],
                                 category="oil_filter"), data)
        self.assertEqual(result["status"], "outside_coverage")

    def test_reject_invalid_input(self):
        for payload in [{"provider": "unknown"}, {"criteria": {"year": 1900}},
                        {"criteria": {"brake_package": "guess"}}, {"criteria": {"fits": True}},
                        {"text": "x" * 2001}]:
            self.assertEqual(self.client.post("/api/search", json=payload).status_code, 422)

    def test_provider_failure_and_recovery(self):
        with patch("counterpilot.app.get_provider") as provider:
            provider.return_value.interpret.side_effect = ProviderError("Use offline mode.")
            self.assertEqual(self.client.post("/api/search", json={"text": "test", "provider": "meta"}).status_code, 503)
        self.assertEqual(self.query("oil filter for a 2019 RAV4")["status"], "candidates")

    def test_catalog_validation(self):
        self.assertEqual(len(CATALOG["parts"]), 30)
        data = copy.deepcopy(CATALOG)
        data["parts"][0]["vehicle_id"] = "missing"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                load_catalog(path)

    def test_catalog_is_fictional_with_evidence(self):
        for p in CATALOG["parts"]:
            self.assertTrue(p["fictional"])
            self.assertTrue(p["part_number"].startswith("DEMO-"))
            self.assertTrue(p["evidence"])

    def test_static_routes(self):
        for path in ["/", "/static/app.js", "/static/style.css", "/api/catalog"]:
            self.assertEqual(self.client.get(path).status_code, 200)


class ProviderTests(unittest.TestCase):
    def test_aliases(self):
        for text, expected in [("2021 f150 oil filter", "F-150"), ("2019 rav-4 air filter", "RAV4"),
                               ("2023 crv cabin air filter", "CR-V"), ("2021 Chevy Silverado oil filter", "Silverado 1500"),
                               ("2021 VW Tiguan front brake discs", "Tiguan")]:
            self.assertEqual(MockProvider().interpret(text).model, expected)

    def test_cabin_is_not_engine_air(self):
        self.assertEqual(MockProvider().interpret("2023 CR-V cabin air filter").category, "cabin_filter")

    def test_multiple_years_and_models_not_guessed(self):
        result = MockProvider().interpret("oil filter for 2019 RAV4 or 2023 CR-V")
        self.assertIsNone(result.year)
        self.assertIsNone(result.model)

    def test_meta_requires_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ProviderError):
                MetaProvider().interpret("oil filter")

    def test_meta_validates_untrusted_output(self):
        with patch.dict(os.environ, {"MODEL_API_KEY": "test-not-a-real-key"}):
            for content in ['{"fits":true}', '{"year":1800}', 'not json']:
                response = io.BytesIO(json.dumps({"choices": [{"message": {"content": content}}]}).encode())
                with patch("counterpilot.providers.urlopen", return_value=response):
                    with self.assertRaises(ProviderError):
                        MetaProvider().interpret("oil filter")

    def test_meta_valid_mock_response(self):
        response = io.BytesIO(json.dumps({"choices": [{"message": {"content":
            '{"year":2019,"make":"Toyota","model":"RAV4","category":"oil_filter"}'}}]}).encode())
        with patch.dict(os.environ, {"MODEL_API_KEY": "test-not-a-real-key"}):
            with patch("counterpilot.providers.urlopen", return_value=response):
                self.assertEqual(MetaProvider().interpret("oil filter").year, 2019)


class VinTests(unittest.TestCase):
    def test_invalid_vin(self):
        for vin in ["", "invalid", "I" * 17]:
            with self.assertRaises(VinLookupError):
                decode_vin(vin)

    def test_decode_mapping(self):
        response = io.BytesIO(json.dumps({"Results": [{"ModelYear": "2019", "Make": "TOYOTA",
            "Model": "RAV4", "DisplacementL": "2.5", "DriveType": "AWD"}]}).encode())
        with patch("counterpilot_vin_lookup.urlopen", return_value=response):
            result = decode_vin("1hgcm82633a004352")
        self.assertEqual(result["engine"]["displacement_l"], "2.5")
        self.assertIn("identity", result["fitment_note"])

    def test_api_requires_confirmation(self):
        with patch("counterpilot.app.decode_vin", return_value={"make": "Toyota"}):
            result = TestClient(app).post("/api/vin", json={"vin": "1HGCM82633A004352"}).json()
        self.assertTrue(result["requires_confirmation"])

    def test_vin_failure_manual_still_works(self):
        with patch("counterpilot.app.decode_vin", side_effect=VinLookupError("private detail")):
            result = TestClient(app).post("/api/vin", json={"vin": "1HGCM82633A004352"})
        self.assertEqual(result.status_code, 502)
        self.assertNotIn("private", result.text)



class RegressionTests(unittest.TestCase):
    def test_empty_request_asks_for_details(self):
        result = TestClient(app).post("/api/search", json={}).json()
        self.assertEqual(result["status"], "needs_clarification")
        self.assertEqual(len(result["questions"]), 4)

    def test_conflicting_make_and_model(self):
        result = MockProvider().interpret("2019 Ford RAV4 oil filter")
        self.assertIsNone(result.make)
        self.assertIsNone(result.model)

    def test_malformed_vin_payload_becomes_recoverable_error(self):
        with patch("counterpilot.app.decode_vin", side_effect=AttributeError("bad upstream response")):
            response = TestClient(app).post("/api/vin", json={"vin": "1HGCM82633A004352"})
        self.assertEqual(response.status_code, 502)


if __name__ == "__main__":
    unittest.main()
