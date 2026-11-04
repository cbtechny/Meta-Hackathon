"""Repeatable chat acceptance tests; Meta transport and NHTSA are mocked."""
import io
import json
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from counterpilot.app import app
from counterpilot.chat import ChatDetails
from counterpilot.conversation import SESSIONS
from counterpilot.providers import MetaProvider, ProviderError


class ConversationTests(unittest.TestCase):
    def setUp(self):
        SESSIONS.clear()
        self.client = TestClient(app)
        self.last = {}

    def send(self, text, patch_data=None, edits=None, status=200):
        payload = {"message": text, "session_id": self.last.get("session_id"), "revision": self.last.get("revision", 0)}
        if edits is not None:
            payload.update(message="", edits=edits)
        response = io.BytesIO(json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(patch_data or {})}}]}).encode())
        with patch('counterpilot.providers.urlopen', return_value=response):
            result = self.client.post('/api/chat', json=payload)
        self.assertEqual(result.status_code, status, result.text)
        if status == 200:
            self.last = result.json()
            self.assertLessEqual(len(self.last['lookup']['questions']), 1)
        return result.json()

    def vehicle(self, part='oil filter', engine=None):
        return self.send('2019 RAV4 '+part+(f' {engine}' if engine else ''), dict(year=2019, make='Toyota', model='RAV4', part=part, engine=engine))

    def test_formatted_vin_is_decoded_without_meta(self):
        decoded = {'model_year': '2019', 'make': 'Toyota', 'model': 'RAV4', 'engine': {}, 'api_error_code': '0'}
        with patch('counterpilot.app.decode_vin', return_value=decoded) as service, patch.object(MetaProvider, 'interpret_conversation', side_effect=AssertionError('Unexpected Meta call')):
            a = self.send('VIN is 1hgc m826-33a004352')
        service.assert_called_once_with('1HGCM82633A004352')
        self.assertEqual(a['question']['field'], 'vin_confirmation')
        self.assertEqual(a['lookup']['detail_progress']['confirmed'], 0)

    def test_invalid_vin_never_reaches_services_and_preserves_details(self):
        self.vehicle()
        with patch('counterpilot.app.decode_vin', side_effect=AssertionError('Unexpected NHTSA call')), patch.object(MetaProvider, 'interpret_conversation', side_effect=AssertionError('Unexpected Meta call')):
            a = self.send('1IGCM82633A004352')
        self.assertEqual(a['question']['field'], 'vin')
        self.assertEqual(a['details']['model'], 'RAV4')
        self.assertIn('does not use I, O or Q', a['reply'])

    def test_empty_vin_identity_is_not_offered_for_confirmation(self):
        with patch('counterpilot.app.decode_vin', return_value={'api_error_code': '0', 'engine': {}}):
            a = self.send('1HGCM82633A004352')
        self.assertNotEqual((a['question'] or {}).get('field'), 'vin_confirmation')
        self.assertIsNone(a['details']['model'])

    def test_ambiguous_filter_short_replies_and_coverage(self):
        a=self.send('Need a filter for my rav 4', dict(make='Toyota', model='rav 4', part='oil filter'))
        self.assertEqual(a['details']['part'], 'filter')
        self.assertEqual(a['question']['field'], 'part')
        a=self.send('Oil', dict(part='oil filter'))
        self.assertEqual(a['question']['field'], 'year')
        a=self.send('2017', dict(year=2017))
        self.assertEqual(a['details']['model'], 'RAV4')
        self.assertEqual(a['details']['part'], 'oil filter')
        self.assertEqual(a['lookup']['status'], 'outside_coverage')
        self.assertIsNone(a['question'])

    def test_complete_request_returns_only_retrieved_part(self):
        a=self.vehicle(engine='2.5 liter')
        self.assertEqual(a['details']['engine'], '2.5L')
        self.assertEqual(a['question']['field'], 'trim')
        self.assertTrue(a['question']['optional'])
        self.assertEqual([p['part_number'] for p in a['lookup']['candidates']], ['FL-00131'])

    def test_engine_correction_is_preserved_without_false_restriction(self):
        self.vehicle(engine='2.5')
        a=self.send('Actually mine is a 3.5', dict(engine='3.5'))
        self.assertEqual(a['details']['engine'], '3.5L')
        self.assertEqual(a['lookup']['status'], 'outside_coverage')
        self.assertFalse(a['lookup']['candidates'])
        self.assertIn('only has 2.5L records', a['reply'])
        a=self.send('Why?', {})
        self.assertEqual(a['details']['engine'], '3.5L')

    def test_unknown_engine_and_declined_vin_do_not_loop(self):
        self.vehicle()
        a=self.send("I don't know the engine", dict(engine=None))
        self.assertEqual(a['question']['field'], 'trim')
        self.assertIn('VIN would help', a['reply'])
        a=self.send("I don't have the VIN")
        self.assertTrue(a['state']['vin_declined'])
        self.assertNotIn('VIN would help', a['reply'])
        a=self.send("I don't know", {})
        self.assertNotEqual((a['question'] or {}).get('field'), 'engine')
        self.assertNotIn('VIN would help', a['reply'])

    def test_skip_switches_part_preserving_vehicle(self):
        self.vehicle()
        a=self.send('Skip that, I need wipers', dict(part='wipers'))
        self.assertEqual(a['details']['year'], 2019)
        self.assertEqual(a['details']['model'], 'RAV4')
        self.assertFalse(a['question'] and a['question']['field']=='engine')
        if a['question']:
            self.assertEqual(a['question']['field'], 'position')
            a=self.send('Front', dict(position='front'))
        self.assertTrue(a['lookup']['candidates'])

    def test_position_and_side_short_answers(self):
        self.vehicle(part='brake caliper', engine='2.5')
        self.assertEqual(self.last['question']['field'], 'position')
        self.send('Front', dict(position='front'))
        self.assertEqual(self.last['question']['field'], 'side')
        a=self.send('Left', dict(side='left'))
        self.assertTrue(a['lookup']['candidates'])

    def test_vin_confirmation_conflict_and_original_provenance(self):
        decoded={'model_year':'2019','make':'Toyota','model':'RAV4','engine':{'displacement_l':'2.5'},'api_error_code':'0'}
        with patch('counterpilot.app.decode_vin', return_value=decoded) as service:
            a=self.send('1HGCM82633A004352')
        service.assert_called_once_with('1HGCM82633A004352')
        self.assertEqual(a['question']['field'], 'vin_confirmation')
        self.send('Yes')
        a=self.send('Actually mine is a 3.5', dict(engine='3.5'))
        self.assertEqual(a['question']['field'], 'override_confirmation')
        self.assertEqual(a['details']['engine'], '2.5L')
        a=self.send('Yes')
        self.assertEqual(a['details']['engine'], '3.5L')
        self.assertEqual(a['state']['decoded']['engine'], '2.5L')
        self.assertEqual(a['state']['sources']['engine'], 'customer override')
        self.assertEqual(a['state']['overrides']['engine'], '3.5L')
        a=self.send('2021 Ford F-150', dict(year=2021,make='Ford',model='F-150'))
        self.assertEqual(a['question']['field'], 'override_confirmation')
        a=self.send('Yes')
        self.assertIsNone(a['state']['vin'])
        self.assertEqual(a['details']['model'],'F-150')

    def test_vehicle_change_invalidates_results_and_reset_clears_state(self):
        self.vehicle(engine='2.5')
        a=self.send('Change vehicle')
        self.assertIsNone(a['details']['year'])
        self.assertEqual(a['details']['part'], 'oil filter')
        self.assertFalse(a['lookup']['candidates'])
        a=self.send('Start over')
        self.assertTrue(all(v is None for v in a['details'].values()))
        self.assertEqual(a['reply'], 'What part do you need?')
        self.assertFalse(a['state']['vin_declined'])

    def test_missing_coverage_stops_questions(self):
        a=self.send('2017 RAV4 oil filter',dict(year=2017,make='Toyota',model='RAV4',part='oil filter'))
        self.assertEqual(a['lookup']['status'],'outside_coverage')
        self.assertIsNone(a['question'])
        self.assertFalse(a['lookup']['candidates'])

    def test_api_failure_preserves_authoritative_state_and_retry(self):
        self.vehicle()
        old=self.last.copy()
        with patch.object(MetaProvider,'interpret_conversation',side_effect=ProviderError('private')):
            r=self.client.post('/api/chat', json={'message':'2.5','session_id':old['session_id'],'revision':old['revision']})
        self.assertEqual(r.status_code,503)
        self.assertNotIn('private',r.text)
        state=SESSIONS[old['session_id']].state
        self.assertEqual(state.details.model,'RAV4')
        self.assertEqual(state.revision,old['revision'])
        self.assertTrue(self.send('2.5',dict(engine='2.5'))['lookup']['candidates'])

    def test_authoritative_state_and_stale_revision(self):
        self.vehicle(engine='2.5')
        a=self.send('thanks',dict(year=None, engine=None, part=None))
        self.assertEqual(a['details']['year'],2019)
        r=self.client.post('/api/chat',json={'message':'2.0','session_id':a['session_id'],'revision':1,'details':{'model':'Camry'}})
        self.assertEqual(r.status_code,409)
        self.assertEqual(SESSIONS[a['session_id']].state.details.model,'RAV4')

    def test_vin_failure_and_demo_id_never_substitute_vehicle(self):
        with patch('counterpilot.app.decode_vin',side_effect=AssertionError):
            self.send('use VIN DEMO-RAV4')
        with patch('counterpilot.app.decode_vin',side_effect=ValueError):
            a=self.send('1HGCM82633A004352')
        self.assertIsNone(a['details']['model'])
        self.assertIn('unavailable',a['reply'])

    def test_demo_profile_does_not_reapply_engine(self):
        self.send('Demo RAV4-01')
        a=self.send('Actually mine is a 3.5', dict(engine='3.5'))
        self.assertEqual(a['details']['engine'],'3.5L')
        self.assertEqual(a['state']['sources']['engine'],'customer')
        self.assertEqual(self.send('oil filter',dict(part='oil filter'))['details']['engine'],'3.5L')

    def test_symptom_is_not_diagnosis_or_engine_displacement(self):
        a=self.send('Clicking when turning',dict(part='CV axle'))
        self.assertIsNone(a['details']['part'])
        self.assertIn('several causes',a['reply'])
        a=self.send('four cylinder',dict(engine='2.5L'))
        self.assertIsNone(a['details']['engine'])
    def test_explicit_unknown_engine_clears_only_engine_and_keeps_source_decode(self):
        self.vehicle(engine='2.5')
        a=self.send("Actually I don't know the engine",dict(engine=None,year=None,part=None))
        self.assertIsNone(a['details']['engine'])
        self.assertEqual(a['details']['year'],2019)
        self.assertEqual(a['details']['part'],'oil filter')
        self.assertEqual(a['state']['attempts']['engine'],1)
        self.assertIn('VIN would help',a['reply'])

    def test_suzuki_demo_preserves_unknown_trim_and_uses_sample_records(self):
        self.send('oil filter',dict(part='oil filter'))
        a=self.send('Demo SX4-01')
        self.assertEqual(a['details']['year'],2007)
        self.assertEqual(a['details']['make'],'Suzuki')
        self.assertEqual(a['details']['model'],'SX4')
        self.assertEqual(a['details']['drivetrain'],'AWD')
        self.assertIsNone(a['details']['trim'])
        self.assertEqual([p['part_number'] for p in a['lookup']['candidates']],['FL-00251'])
        self.assertTrue(all(p['fictional'] and p['source']=='generated_demo' for p in a['lookup']['candidates']))

    def test_explicit_demo_selection_replaces_conflicting_vehicle_context(self):
        self.vehicle()
        self.send('It is hybrid', dict(hybrid=True))
        decoded={'model_year':'2019','make':'Toyota','model':'RAV4','engine':{'displacement_l':'2.5'},'api_error_code':'0'}
        with patch('counterpilot.app.decode_vin',return_value=decoded):
            self.send('1HGCM82633A004352')
        a=self.send('Demo RAV4-01')
        self.assertEqual(a['question']['field'], 'engine')
        self.assertIsNone(a['state']['vin'])
        self.assertFalse(a['details']['hybrid'])
        self.assertTrue(a['lookup']['candidates'])
        self.assertEqual(a['state']['sources']['model'],'demo profile')
        self.assertTrue(a['state']['pending']['optional'])

    def test_retry_after_lost_success_replays_without_second_model_call(self):
        self.vehicle()
        payload={'message':'2.5L','session_id':self.last['session_id'],'revision':self.last['revision'],'request_id':'a'*32}
        with patch.object(MetaProvider,'interpret_conversation',return_value=ChatDetails(engine='2.5L')) as provider:
            first=self.client.post('/api/chat',json=payload)
            second=self.client.post('/api/chat',json=payload)
        self.assertEqual(first.status_code,200)
        self.assertEqual(second.json(),first.json())
        provider.assert_called_once()


class ApplicationPolicyTests(unittest.TestCase):
    """Synthetic variants exercise branches absent from the five-profile demo."""
    def catalog(self, part='oil_filter', same_number=False, hybrid=False):
        import copy
        from counterpilot.domain import CATALOG
        catalog=copy.deepcopy(CATALOG)
        v=copy.deepcopy(next(v for v in catalog['vehicles'] if v['id']=='RAV4-01'))
        v.update(id='SYNTHETIC-VARIANT',vehicle_id='SYNTHETIC-VARIANT',source='synthetic_test_only')
        if hybrid:
            v['fuel_type']='hybrid'
        else:
            v['engine']='3.5L'
        catalog['vehicles'].append(v)
        p=copy.deepcopy(next(p for p in catalog['parts'] if p['vehicle_id']=='RAV4-01' and p['part_type']==part))
        p.update(id='SYNTHETIC-PART',part_id='SYNTHETIC-PART',vehicle_id=v['id'],source='synthetic_test_only')
        if not same_number:
            p['part_number']='SYNTHETIC-ALT'
        catalog['parts'].append(p)
        return catalog

    def test_engine_question_only_when_applications_differ_and_unknown_stops_loop(self):
        from counterpilot.chat import Conversation, lookup_reply
        details=ChatDetails(year=2019,make='Toyota',model='RAV4',part='oil filter')
        state=Conversation(details=details)
        catalog=self.catalog()
        a=lookup_reply(details,state,catalog)
        self.assertEqual(a['question']['field'],'engine')
        self.assertEqual(a['question']['options'],['2.5L','3.5L'])
        state.attempts['engine']=1
        a=lookup_reply(details,state,catalog)
        self.assertIsNone(a['question'])
        self.assertFalse(a['lookup']['candidates'])
        self.assertIn('VIN would help',a['reply'])
        details.engine='3.5L'
        a=lookup_reply(details,state,catalog)
        self.assertEqual(a['lookup']['candidates'][0]['part_number'],'SYNTHETIC-ALT')

    def test_shared_wiper_applications_do_not_require_engine(self):
        from counterpilot.chat import lookup_reply
        a=lookup_reply(ChatDetails(year=2019,make='Toyota',model='RAV4',part='wipers',position='front'),catalog=self.catalog('wiper_blade',True))
        self.assertIsNone(a['question'])
        self.assertEqual(a['lookup']['status'],'candidates')
        self.assertEqual(len(a['lookup']['applications']),2)
        self.assertFalse(a['lookup']['fitment_confirmed'])

    def test_hybrid_question_separates_relevant_applications(self):
        from counterpilot.chat import lookup_reply
        a=lookup_reply(ChatDetails(year=2019,make='Toyota',model='RAV4',part='oil filter'),catalog=self.catalog(hybrid=True))
        self.assertEqual(a['question']['field'],'hybrid')
        a=lookup_reply(ChatDetails(year=2019,make='Toyota',model='RAV4',part='oil filter',hybrid=True),catalog=self.catalog(hybrid=True))
        self.assertEqual(a['lookup']['candidates'][0]['part_number'],'SYNTHETIC-ALT')

    def test_missing_application_engine_metadata_reports_limitation(self):
        from counterpilot.chat import lookup_reply
        catalog=self.catalog()
        for v in catalog['vehicles']:
            v['engine']='unknown'
        a=lookup_reply(ChatDetails(year=2019,make='Toyota',model='RAV4',part='oil filter'),catalog=catalog)
        self.assertIsNone(a['question'])
        self.assertFalse(a['lookup']['candidates'])
        self.assertIn('lack enough',a['reply'])


if __name__=='__main__':
    unittest.main()
