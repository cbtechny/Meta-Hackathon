"""Inline preview progress and optional questions use authoritative state only."""
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from counterpilot.app import app
from counterpilot.chat import ChatDetails, Conversation, detail_progress
from counterpilot.conversation import SESSIONS
from counterpilot.providers import MetaProvider, ProviderError


class InlineResultTests(unittest.TestCase):
    def setUp(self):
        SESSIONS.clear()
        self.client = TestClient(app)
        self.last = {}

    def turn(self, message="", update=None, edits=None, request_id=None):
        payload = {"message": message, "session_id": self.last.get("session_id"),
                   "revision": self.last.get("revision", 0), "request_id": request_id}
        if edits is not None:
            payload.update(message="", edits=edits)
        with patch.object(MetaProvider, "interpret_conversation", return_value=ChatDetails(**(update or {}))):
            response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        self.last = response.json()
        self.assertLessEqual(len(self.last["lookup"]["questions"]), 1)
        return self.last

    def vehicle(self):
        return self.turn(edits={"year": 2019, "make": "Toyota", "model": "RAV4", "part": "oil filter"})

    def test_preview_and_optional_question_coexist_with_three_of_six(self):
        result = self.vehicle()
        self.assertEqual(result["lookup"]["candidates"][0]["part_number"], "FL-00131")
        self.assertEqual(result["lookup"]["detail_progress"]["confirmed"], 3)
        self.assertEqual(result["lookup"]["detail_progress"]["total"], 6)
        self.assertFalse(result["lookup"]["fitment_confirmed"])
        self.assertEqual(result["question"]["field"], "engine")
        self.assertTrue(result["question"]["optional"])

    def test_progress_increases_and_six_does_not_claim_fitment(self):
        self.vehicle()
        for field, value, count in (("engine", "2.5L", 4), ("trim", "XLE", 5), ("drivetrain", "AWD", 6)):
            result = self.turn(edits={field: value})
            self.assertEqual(result["lookup"]["detail_progress"]["confirmed"], count)
            self.assertFalse(result["lookup"]["fitment_confirmed"])
        self.assertIsNone(result["question"])
        self.assertIn("not fitment probability", result["lookup"]["detail_progress"]["meaning"])

    def test_skip_survives_later_answers_until_vehicle_changes(self):
        self.vehicle()
        result = self.turn("I don't know the engine")
        self.assertEqual(result["question"]["field"], "trim")
        self.assertTrue(result["lookup"]["candidates"])
        result = self.turn("XLE", {"trim": "XLE"})
        self.assertEqual(result["question"]["field"], "drivetrain")
        result = self.turn("I don't know the drivetrain")
        self.assertIsNone(result["question"])
        self.assertEqual(result["lookup"]["detail_progress"]["confirmed"], 4)
        result = self.turn(edits={"year": 2021, "make": "Ford", "model": "F-150"})
        self.assertEqual(result["question"]["field"], "engine")

    def test_required_questions_take_priority_over_completeness(self):
        result = self.turn(edits={"year": 2019, "make": "Toyota", "model": "RAV4", "part": "brake caliper"})
        self.assertEqual(result["question"]["field"], "position")
        self.assertNotIn("optional", result["question"])
        self.assertFalse(result["lookup"]["candidates"])
        result = self.turn(edits={"position": "front"})
        self.assertEqual(result["question"]["field"], "side")
        result = self.turn(edits={"side": "left"})
        self.assertTrue(result["lookup"]["candidates"])
        self.assertEqual(result["question"]["field"], "engine")

    def test_demo_defaults_never_count_as_confirmed(self):
        self.turn("Demo RAV4-01")
        result = self.turn("oil filter", {"part": "oil filter"})
        self.assertEqual(result["lookup"]["detail_progress"]["confirmed"], 0)
        self.assertTrue(result["lookup"]["candidates"])
        result = self.turn("2.5L")  # Same value as the profile, now explicitly stated.
        self.assertEqual(result["lookup"]["detail_progress"]["confirmed"], 1)
        self.assertEqual(result["question"]["field"], "trim")

    def test_vin_values_only_count_after_acceptance_and_new_decode_unconfirms(self):
        decoded = {"model_year": "2019", "make": "Toyota", "model": "RAV4", "engine": {"displacement_l": "2.5"}, "trim": "XLE", "drivetrain": "AWD", "api_error_code": "0"}
        with patch("counterpilot.app.decode_vin", return_value=decoded):
            result = self.turn("1HGCM82633A004352")
        self.assertEqual(result["lookup"]["detail_progress"]["confirmed"], 0)
        result = self.turn("Yes")
        self.assertEqual(result["lookup"]["detail_progress"]["confirmed"], 6)
        self.assertEqual(result["state"]["sources"]["engine"], "VIN confirmed")
        with patch("counterpilot.app.decode_vin", return_value=decoded):
            result = self.turn("1HGCM82633A004352")
        self.assertFalse(result["state"]["confirmed"])
        self.assertEqual(result["lookup"]["detail_progress"]["confirmed"], 0)

    def test_inferred_equipment_cannot_raise_the_count(self):
        result = self.turn("2019 Toyota RAV4 oil filter", {"year": 2019, "make": "Toyota", "model": "RAV4", "part": "oil filter", "trim": "XLE", "drivetrain": "AWD"})
        self.assertIsNone(result["details"]["trim"])
        self.assertIsNone(result["details"]["drivetrain"])
        self.assertEqual(result["lookup"]["detail_progress"]["confirmed"], 3)

    def test_incompatible_correction_removes_current_candidates_and_equipment_count(self):
        self.vehicle()
        self.turn(edits={"engine": "2.5L", "trim": "XLE", "drivetrain": "AWD"})
        result = self.turn(edits={"year": 2018})
        self.assertFalse(result["lookup"]["candidates"])
        self.assertEqual(result["lookup"]["status"], "outside_coverage")
        self.assertEqual(result["lookup"]["detail_progress"]["confirmed"], 3)
        self.assertIsNone(result["question"])

    def test_source_and_unknown_values_control_count(self):
        state = Conversation(details=ChatDetails(year=2019, make="Toyota", model="RAV4", engine="Unknown", trim="XLE", drivetrain="AWD"),
                             sources={"year": "customer", "make": "catalog", "model": "demo profile", "engine": "customer", "trim": "VIN decoded", "drivetrain": "VIN confirmed"})
        self.assertEqual(detail_progress(state)["confirmed_fields"], ["year", "drivetrain"])

    def test_failure_and_replay_do_not_inflate_progress_or_advance_session(self):
        self.vehicle()
        before = self.last
        payload = {"message": "2.5L", "session_id": before["session_id"], "revision": before["revision"], "request_id": "b" * 32}
        with patch.object(MetaProvider, "interpret_conversation", side_effect=ProviderError("private")):
            response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(SESSIONS[before["session_id"]].state.revision, before["revision"])
        with patch.object(MetaProvider, "interpret_conversation", return_value=ChatDetails(engine="2.5L")) as provider:
            first = self.client.post("/api/chat", json=payload)
            replay = self.client.post("/api/chat", json=payload)
        provider.assert_called_once()
        self.assertEqual(first.json(), replay.json())
        self.assertEqual(first.json()["lookup"]["detail_progress"]["confirmed"], 4)


if __name__ == "__main__":
    unittest.main()
