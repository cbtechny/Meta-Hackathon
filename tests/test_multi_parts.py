"""Multiple requested items share vehicle facts, never item-specific constraints."""
import io
import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from counterpilot.app import app
from counterpilot.chat import ChatDetails, ChatRequest, ConversationUpdate
from counterpilot.conversation import SESSIONS
from counterpilot.providers import MetaProvider, ProviderError


class MultiplePartsTests(unittest.TestCase):
    def setUp(self):
        SESSIONS.clear()
        self.client = TestClient(app)
        self.last = {}

    def turn(self, message, **update):
        payload = {'message': message, 'session_id': self.last.get('session_id'),
                   'revision': self.last.get('revision', 0)}
        with patch.object(MetaProvider, 'interpret_conversation', return_value=ConversationUpdate(**update)):
            response = self.client.post('/api/chat', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.last = response.json()
        return self.last

    def vehicle(self, parts):
        return self.turn('For my 2019 Toyota RAV4, ' + ', '.join(p['part'] for p in parts),
                         year=2019, make='Toyota', model='RAV4', parts=parts)

    def test_three_items_clarify_independently_while_available_cards_stay_visible(self):
        result = self.vehicle([{'part': 'brakes'}, {'part': 'air filter'}, {'part': 'belt'}])
        self.assertEqual(len(result['parts']), 3)
        self.assertEqual(result['question']['item_index'], 0)
        self.assertEqual(result['lookup']['candidates'][0]['part_type'], 'air_filter')
        result = self.turn('Brake pads', part='brake pads')
        self.assertEqual(result['question']['field'], 'position')
        result = self.turn('Front', position='front')
        self.assertEqual(result['question']['item_index'], 2)
        self.assertIn('Which belt', result['question']['label'])
        result = self.turn('Serpentine belt', part='serpentine belt')
        self.assertEqual(len(result['parts']), 3)
        self.assertEqual({p['part_type'] for p in result['lookup']['candidates']},
                         {'brake_pad', 'air_filter', 'serpentine_belt'})
        self.assertEqual(result['parts'][0]['position'], 'front')
        self.assertIsNone(result['parts'][1]['position'])
        self.assertIsNone(result['parts'][2]['position'])

    def test_positions_and_sides_stay_with_their_own_items(self):
        result = self.vehicle([{'part': 'brake pads', 'position': 'front'},
                               {'part': 'brake rotors', 'position': 'rear'},
                               {'part': 'tie rod end', 'position': 'front', 'side': 'left'}])
        for item in result['lookup']['items']:
            self.assertTrue(item['lookup']['candidates'])
            for part in item['lookup']['candidates']:
                self.assertEqual(part['position'], item['position'])
                if item['side']:
                    self.assertEqual(part['side'], item['side'])

    def test_unknown_parts_are_retained_beside_available_records(self):
        result = self.vehicle([{'part': 'oil filter'}, {'part': 'transmission'}, {'part': 'timing belt'}])
        self.assertEqual(len(result['lookup']['items']), 3)
        self.assertTrue(result['lookup']['items'][0]['lookup']['candidates'])
        for item in result['lookup']['items'][1:]:
            self.assertEqual(item['lookup']['status'], 'outside_coverage')
            self.assertEqual(item['lookup']['candidates'], [])

    def test_append_deduplicates_aliases_without_losing_existing_items(self):
        self.turn('Oil filter for a 2019 RAV4', year=2019, make='Toyota', model='RAV4', part='oil filter')
        result = self.turn('Also add a cabin filter', parts=[{'part': 'cabin filter'}], parts_action='append')
        self.assertEqual(len(result['parts']), 2)
        result = self.turn('Add cabin air filter too', parts=[{'part': 'cabin air filter'}], parts_action='append')
        self.assertEqual(len(result['parts']), 2)
        result = self.turn('Instead I need a starter and alternator', parts=[{'part': 'starter'}, {'part': 'alternator'}])
        self.assertEqual([p['part'] for p in result['parts']], ['starter', 'alternator'])

    def test_same_part_front_and_rear_are_separate_items(self):
        result = self.vehicle([{'part': 'pads', 'position': 'front'}, {'part': 'brake pads', 'position': 'rear'}])
        self.assertEqual(len(result['parts']), 2)
        self.assertEqual({p['position'] for p in result['lookup']['candidates']}, {'front', 'rear'})

    def test_editing_one_item_and_vehicle_corrections_preserve_the_list(self):
        result = self.vehicle([{'part': 'oil filter'}, {'part': 'air filter'}, {'part': 'serpentine belt'}])
        self.turn('Edit item 3')
        result = self.turn('Timing belt instead', part='timing belt')
        self.assertEqual([p['part'] for p in result['parts']], ['oil filter', 'air filter', 'timing belt'])
        result = self.turn('Actually a 2.5L engine', engine='2.5L')
        self.assertEqual(len(result['parts']), 3)
        self.assertTrue(all(item['details']['engine'] == '2.5L' for item in result['lookup']['items']))
        result = self.turn('Start over')
        self.assertEqual(result['parts'], [])

    def test_explicit_correction_targets_named_item(self):
        self.vehicle([{'part': 'oil filter'}, {'part': 'air filter'}])
        result = self.turn('Change the air filter to a cabin filter', part='cabin filter', item_index=1)
        self.assertEqual([p['part'] for p in result['parts']], ['oil filter', 'cabin filter'])

    def test_explanation_uses_the_record_item_instead_of_active_clarification(self):
        result = self.vehicle([{'part': 'brakes'}, {'part': 'air filter'}])
        part = result['lookup']['candidates'][0]
        with patch.object(MetaProvider, '_extract', side_effect=ProviderError('unavailable')):
            response = self.client.post('/api/explain', json={'session_id': result['session_id'],
                'revision': result['revision'], 'part_id': part['id']})
        self.assertEqual(response.status_code, 200)
        facts = response.json()['focus'] + response.json()['other_details']
        self.assertEqual(next(f['value'] for f in facts if f['field'] == 'part'), 'air filter')

    def test_provider_accepts_multiple_supported_and_unknown_parts(self):
        content = {'parts': [{'part': 'brakes'}, {'part': 'air filter'}, {'part': 'belt'}, {'part': 'muffler'}]}
        raw = io.BytesIO(json.dumps({'choices': [{'message': {'content': json.dumps(content)}}]}).encode())
        with patch('counterpilot.providers.urlopen', return_value=raw):
            update = MetaProvider().interpret_conversation(ChatRequest(message='Brakes, an air filter, a belt and a muffler'))
        self.assertEqual([p.part for p in update.parts], ['brakes', 'air filter', 'belt', 'muffler'])

    def test_skipping_one_item_does_not_restart_its_question_on_every_turn(self):
        self.vehicle([{'part': 'brakes'}, {'part': 'air filter'}, {'part': 'belt'}])
        result = self.turn("I don't know which brakes")
        self.assertEqual(result['question']['item_index'], 2)
        result = self.turn('Serpentine belt', part='serpentine belt')
        self.assertIsNone(result['question'])
        self.assertEqual(len(result['lookup']['candidates']), 2)
        self.assertEqual(result['lookup']['items'][0]['lookup']['status'], 'unconfirmed')

    def test_expired_session_continuation_keeps_all_items_and_the_active_item(self):
        before = self.vehicle([{'part': 'oil filter'}, {'part': 'belt'}, {'part': 'air filter'}])
        SESSIONS.clear()
        with patch.object(MetaProvider, 'interpret_conversation', return_value=ConversationUpdate(part='serpentine belt')):
            response = self.client.post('/api/chat', json={'message': 'Serpentine belt',
                'details': before['details'], 'parts': before['parts'], 'active_part': before['active_part']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p['part'] for p in response.json()['parts']], ['oil filter', 'serpentine belt', 'air filter'])

    def test_failed_provider_turn_cannot_destroy_or_partially_change_the_list(self):
        before = self.vehicle([{'part': 'brakes'}, {'part': 'air filter'}, {'part': 'belt'}])
        with patch.object(MetaProvider, 'interpret_conversation', side_effect=ProviderError('unavailable')):
            response = self.client.post('/api/chat', json={'message': 'Brake pads',
                'session_id': before['session_id'], 'revision': before['revision']})
        self.assertEqual(response.status_code, 503)
        self.assertEqual([p.model_dump() for p in SESSIONS[before['session_id']].state.parts], before['parts'])
        self.assertEqual(SESSIONS[before['session_id']].state.revision, before['revision'])

    def test_part_list_survives_vin_conflict_confirmation(self):
        self.vehicle([{'part': 'oil filter'}, {'part': 'air filter'}])
        decoded = {'model_year': '2019', 'make': 'Toyota', 'model': 'RAV4', 'engine': {'displacement_l': '2.5'}, 'api_error_code': '0'}
        with patch('counterpilot.app.decode_vin', return_value=decoded):
            self.turn('VIN 1HGCM82633A004352')
        self.turn('Yes')
        result = self.turn('Actually a 3.5L, and I need front pads and rear rotors', engine='3.5L',
                           parts=[{'part': 'brake pads', 'position': 'front'}, {'part': 'brake rotors', 'position': 'rear'}])
        self.assertEqual(result['question']['field'], 'override_confirmation')
        result = self.turn('Yes')
        self.assertEqual([p['part'] for p in result['parts']], ['brake pads', 'brake rotors'])
        self.assertEqual([p['position'] for p in result['parts']], ['front', 'rear'])
        self.assertEqual(result['details']['engine'], '3.5L')


if __name__ == '__main__':
    unittest.main()
