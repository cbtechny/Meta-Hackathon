import io
import json
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from counterpilot.app import app
from counterpilot.chat import ChatDetails, ChatRequest, lookup_reply, merge_details
from counterpilot.providers import MetaProvider, ProviderError


class ChatTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def turn(self, update, **payload):
        headers = payload.pop("headers", {})
        with patch.object(MetaProvider, "interpret_conversation", return_value=ChatDetails(**update)):
            return self.client.post("/api/chat", headers=headers, json={"message": "customer words", **payload})

    def test_partial_answer_preserves_confirmed_details_and_asks_one_question(self):
        first = self.turn({"year": 2021, "make": "Ford", "model": "F-150", "part": "brake caliper"}).json()
        self.assertEqual(first["question"]["field"], "position")
        second = self.turn({"position": "front"}, details=first["details"]).json()
        self.assertEqual(second["details"]["year"], 2021)
        self.assertEqual(second["details"]["part"], "brake caliper")
        self.assertEqual(second["question"]["field"], "side")
        self.assertEqual(len(second["lookup"]["questions"]), 1)
        self.assertEqual(second["lookup"]["candidates"], [])

    def test_model_year_correction_clears_equipment_but_preserves_part(self):
        current = ChatDetails(year=2021, make="Ford", model="F-150", engine="3.5L EcoBoost",
                              part="brake rotor", position="rear", side="left")
        new = merge_details(current, ChatDetails(year=2020))
        self.assertEqual(new.model, "F-150")
        self.assertEqual(new.part, "brake rotor")
        self.assertIsNone(new.engine)
        self.assertIsNone(new.side)

    def test_make_correction_clears_old_model(self):
        new = merge_details(ChatDetails(make="Ford", model="F-150"), ChatDetails(make="Toyota"))
        self.assertIsNone(new.model)

    def test_explicit_clear_is_distinct_from_omission(self):
        current = ChatDetails(year=2019, make="Toyota", model="RAV4", part="oil filter")
        self.assertEqual(merge_details(current, ChatDetails()).year, 2019)
        self.assertIsNone(merge_details(current, ChatDetails(year=None)).year)

    def test_unsupported_example_retains_details_without_inventing_record(self):
        response = self.turn({"year": 2018, "make": "Toyota", "model": "Camry", "part": "brake pads", "position": "front"})
        data = response.json()
        self.assertEqual(data["details"]["model"], "Camry")
        self.assertEqual(data["details"]["part"], "brake pads")
        self.assertIsNone(data["details"]["engine"])
        self.assertEqual(data["lookup"]["status"], "outside_coverage")
        self.assertFalse(data["lookup"]["candidates"])
        self.assertIn("matching application loaded", data["reply"])

    def test_single_profile_preview_does_not_require_unknown_engine(self):
        data = self.turn({"year": 2019, "make": "Toyota", "model": "RAV4", "part": "oil filter"}).json()
        self.assertEqual(data["question"]["field"], "engine")
        self.assertTrue(data["question"]["optional"])
        self.assertIsNone(data["details"]["engine"])
        self.assertTrue(data["lookup"]["candidates"])
        self.assertFalse(data["lookup"]["fitment_confirmed"])
        self.assertIn("engine", data["lookup"]["unconfirmed_fields"])

    def test_engine_mismatch_cannot_show_catalog_candidate(self):
        result = lookup_reply(ChatDetails(year=2019, make="Toyota", model="RAV4", part="oil filter", engine="3.5L"))
        self.assertEqual(result["lookup"]["status"], "outside_coverage")
        self.assertFalse(result["lookup"]["candidates"])

    def test_matching_engine_returns_only_catalog_record(self):
        result = lookup_reply(ChatDetails(year=2019, make="Toyota", model="RAV4", part="oil filter", engine="2.5L"))
        self.assertEqual(result["lookup"]["candidates"][0]["part_number"], "FL-00131")
        self.assertIsNone(result["question"])

    def test_manual_correction_does_not_call_meta(self):
        with patch.object(MetaProvider, "interpret_conversation", side_effect=AssertionError):
            response = self.client.post("/api/chat", json={"details": {"year": 2018, "make": "Toyota", "model": "RAV4", "part": "oil filter"}, "edits": {"year": 2019}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["details"]["year"], 2019)
        self.assertEqual(response.json()["question"]["field"], "engine")
        self.assertTrue(response.json()["lookup"]["candidates"])

    def test_failure_never_echoes_exception_or_submitted_message(self):
        secret = "test-secret-do-not-return"
        with patch.object(MetaProvider, "interpret_conversation", side_effect=ProviderError(secret)):
            response = self.client.post("/api/chat", json={"message": secret})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(secret, response.text)

    def test_input_validation_is_bounded_and_does_not_echo_input(self):
        secret = "test-secret-do-not-return"
        for payload in ({"message": "x" * 2001}, {"message": "test", "history": [{"role": "system", "content": secret}]},
                        {"message": "test", "details": {"confidence": secret}}, {"message": "test", "details": {"year": secret}},
                        {"message": "test", "history": [{"role": "user", "content": "x" * 2000}] * 13},
                        {"message": ""}, {"message": "test", "edits": {"year": 2019}}):
            with self.subTest(payload_type=tuple(payload)):
                response = self.client.post("/api/chat", json=payload)
                self.assertEqual(response.status_code, 422)
                self.assertNotIn(secret, response.text)

    def test_raw_body_limit_and_cross_origin_requests(self):
        self.assertEqual(self.client.post("/api/chat", content="x" * 48001).status_code, 413)
        with patch.object(MetaProvider, "interpret_conversation", side_effect=AssertionError):
            self.assertEqual(self.client.post("/api/chat", headers={"Origin": "https://other.invalid"}, json={"message": "hello"}).status_code, 403)
        response = self.turn({"part": "oil filter"}, headers={"Origin": "http://testserver"})
        self.assertEqual(response.status_code, 200)

    def test_chat_security_headers_and_no_secret_routes(self):
        response = self.client.get("/chat")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("script-src 'self'", response.headers["content-security-policy"])
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        direct = self.client.get("/static/chat.html")
        self.assertEqual(direct.headers["cache-control"], "no-store")
        self.assertIn("script-src 'self'", direct.headers["content-security-policy"])
        for path in ("/.env", "/chat/.env", "/static/.env", "/static/%2e%2e/.env"):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_transport_preserves_roles_and_never_sends_key_in_body(self):
        response = io.BytesIO(json.dumps({"choices": [{"message": {"content": '{"position":"rear"}'}}]}).encode())
        request = ChatRequest(message="rear", history=[{"role": "assistant", "content": "Front or rear?"}],
                              details=ChatDetails(year=2021, make="Ford", model="F-150", part="brake rotor"))
        with patch.dict(os.environ, {"MODEL_API_KEY": "test-not-a-real-key"}):
            with patch("counterpilot.providers.urlopen", return_value=response) as transport:
                parsed = MetaProvider().interpret_conversation(request)
        sent = transport.call_args.args[0]
        self.assertEqual(parsed.position, "rear")
        self.assertEqual(parsed.model_fields_set, {"position"})
        self.assertNotIn(b"test-not-a-real-key", sent.data)
        messages = json.loads(sent.data)["messages"]
        self.assertEqual(json.loads(sent.data)["reasoning_effort"], "minimal")
        self.assertEqual(json.loads(sent.data)["max_tokens"], 2048)
        self.assertEqual([m["role"] for m in messages], ["system", "assistant", "user"])
        self.assertEqual(messages[-1]["content"], "rear")

    def test_untrusted_model_cannot_return_fitment_or_extra_fields(self):
        for content in ('{"part_number":"invented"}', '{"confidence":0.99}', '{"year":1800}', 'not json'):
            response = io.BytesIO(json.dumps({"choices": [{"message": {"content": content}}]}).encode())
            with patch.dict(os.environ, {"MODEL_API_KEY": "test-not-a-real-key"}), patch("counterpilot.providers.urlopen", return_value=response):
                with self.assertRaises(ProviderError):
                    MetaProvider().interpret_conversation(ChatRequest(message="hello"))

    def test_truncated_or_empty_model_response_is_recoverable(self):
        for content, finish in ((None, "length"), ('{"part":"oil filter"}', "length"), (None, "stop")):
            response = io.BytesIO(json.dumps({"choices": [{"finish_reason": finish, "message": {"content": content}}]}).encode())
            with patch.dict(os.environ, {"MODEL_API_KEY": "test-not-a-real-key"}), patch("counterpilot.providers.urlopen", return_value=response):
                with self.assertRaises(ProviderError):
                    MetaProvider().interpret_conversation(ChatRequest(message="hello"))

    def test_model_cannot_infer_engine_or_clear_confirmed_fields(self):
        content = '{"year":2019,"make":"Toyota","model":"RAV4","engine":"2.5L","part":null}'
        response = io.BytesIO(json.dumps({"choices": [{"message": {"content": content}}]}).encode())
        request = ChatRequest(message="2019 Toyota RAV4", details=ChatDetails(part="oil filter"))
        with patch.dict(os.environ, {"MODEL_API_KEY": "test-not-a-real-key"}), patch("counterpilot.providers.urlopen", return_value=response):
            update = MetaProvider().interpret_conversation(request)
        self.assertNotIn("engine", update.model_fields_set)
        self.assertNotIn("part", update.model_fields_set)
        self.assertEqual(merge_details(request.details, update).part, "oil filter")

    def test_echoed_engine_does_not_transfer_to_corrected_year(self):
        content = '{"year":2018,"make":"Toyota","model":"RAV4","engine":"2.5L","part":"oil filter"}'
        response = io.BytesIO(json.dumps({"choices": [{"message": {"content": content}}]}).encode())
        request = ChatRequest(message="Actually 2018", details=ChatDetails(year=2019, make="Toyota", model="RAV4", engine="2.5L", part="oil filter"))
        with patch.dict(os.environ, {"MODEL_API_KEY": "test-not-a-real-key"}), patch("counterpilot.providers.urlopen", return_value=response):
            update = MetaProvider().interpret_conversation(request)
        self.assertEqual(update.model_fields_set, {"year"})
        self.assertIsNone(merge_details(request.details, update).engine)

    def test_clear_one_field_does_not_erase_other_confirmed_details(self):
        content = '{"year":null,"make":null,"model":null,"engine":null,"part":null}'
        response = io.BytesIO(json.dumps({"choices": [{"message": {"content": content}}]}).encode())
        request = ChatRequest(message="Clear the engine", details=ChatDetails(year=2019, make="Toyota", model="RAV4", engine="2.5L", part="oil filter"))
        with patch.dict(os.environ, {"MODEL_API_KEY": "test-not-a-real-key"}), patch("counterpilot.providers.urlopen", return_value=response):
            update = MetaProvider().interpret_conversation(request)
        self.assertEqual(update.model_fields_set, {"engine"})
        merged = merge_details(request.details, update)
        self.assertIsNone(merged.engine)
        self.assertEqual(merged.year, 2019)
        self.assertEqual(merged.part, "oil filter")


if __name__ == "__main__":
    unittest.main()
