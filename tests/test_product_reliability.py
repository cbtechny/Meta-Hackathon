import unittest
import io
import json
import os
from unittest.mock import patch
from fastapi.testclient import TestClient
from counterpilot.app import app
from counterpilot.chat import ChatDetails, ChatRequest, stated_engine_displacement
from counterpilot.providers import MetaProvider
from counterpilot.conversation import SESSIONS


class ProductReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(app)
        SESSIONS.clear()

    def test_initial_request_replays_after_lost_response_without_second_meta_call(self):
        payload={'message':'Oil filter','request_id':'c'*32}
        with patch.object(MetaProvider,'interpret_conversation',return_value=ChatDetails(part='oil filter')) as provider:
            first=self.client.post('/api/chat',json=payload)
            retry=self.client.post('/api/chat',json=payload)
        self.assertEqual(first.status_code,200)
        self.assertEqual(first.json(),retry.json())
        provider.assert_called_once()
        self.assertEqual(len(SESSIONS),1)

    def test_reusing_request_id_for_different_content_cannot_replay_old_success(self):
        payload={'message':'Oil filter','request_id':'d'*32}
        with patch.object(MetaProvider,'interpret_conversation',return_value=ChatDetails(part='oil filter')) as provider:
            first=self.client.post('/api/chat',json=payload)
            mismatch=self.client.post('/api/chat',json={**payload,'message':'Brake pads'})
        self.assertEqual(first.status_code,200)
        self.assertEqual(mismatch.status_code,409)
        provider.assert_called_once()

    def test_numeric_grounding_accepts_units_normalization_and_sentence_punctuation(self):
        for text,engine in [('Actually mine is a 3.5.','3.5L'),('2007 SX4, 2.0 AWD.','2L'),('2.50 liters.','2.5L')]:
            with self.subTest(text=text):
                self.assertTrue(stated_engine_displacement(text,engine))
                response=io.BytesIO(json.dumps({'choices':[{'message':{'content':json.dumps({'engine':engine})}}]}).encode())
                with patch.dict(os.environ,{'MODEL_API_KEY':'test-not-real'}),patch('counterpilot.providers.urlopen',return_value=response):
                    update=MetaProvider().interpret_conversation(ChatRequest(message=text))
                self.assertEqual(update.engine,engine)

    def test_numeric_grounding_does_not_use_cylinders_or_model_digits(self):
        for text,engine in [('four-cylinder','2.0L'),('SX4','4L'),('3.55L','3.5L'),('2.5L','5L')]:
            self.assertFalse(stated_engine_displacement(text,engine))

    def test_two_liter_spellings_return_the_same_catalog_candidates(self):
        candidates = None
        for engine in ['2', '2.0', '2L', '2.0 L', '2.00l', '2 liters', '2.0 litres']:
            with self.subTest(engine=engine):
                response = self.client.post('/api/chat', json={'edits': {
                    'year': 2007, 'make': 'Suzuki', 'model': 'SX4',
                    'engine': engine, 'part': 'oil filter'}})
                self.assertEqual(response.status_code, 200)
                result = response.json()
                self.assertEqual(result['details']['engine'], '2L')
                self.assertTrue(result['lookup']['candidates'])
                if candidates is None:
                    candidates = result['lookup']['candidates']
                self.assertEqual(result['lookup']['candidates'], candidates)

    def test_engine_normalization_preserves_qualifiers_and_other_sizes(self):
        for engine in ['2.0T', '2.0L EcoBoost', '2.0L diesel', '2.5L']:
            self.assertEqual(ChatDetails(engine=engine).engine, engine)

    def test_health_does_not_call_providers_or_return_secrets(self):
        with patch.object(MetaProvider,'interpret_conversation',side_effect=AssertionError):
            response=self.client.get('/healthz')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json(),{'status':'ok','catalog_loaded':True})
        self.assertEqual(response.headers['cache-control'],'no-store')

    def test_polish_assets_load_with_same_origin_policy(self):
        html=self.client.get('/').text
        for marker in ['id="resume-chat"','id="edit-failed"','id="vehicles-dialog"','id="garage-undo"','Skip to your parts request']:
            self.assertIn(marker,html)
        for name in ['product.js','polish.css','mark.svg']:
            response=self.client.get('/static/'+name)
            self.assertEqual(response.status_code,200)
            self.assertIn("script-src 'self'",response.headers['content-security-policy'])


if __name__=='__main__':
    unittest.main()
