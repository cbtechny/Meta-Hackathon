import json
import unittest
from urllib.parse import quote
from fastapi.testclient import TestClient
from counterpilot.app import app
from counterpilot.domain import CATALOG
from counterpilot.garage import COOKIE_NAME, read_garage


class GarageTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(app)
        self.part=next(p for p in CATALOG['parts'] if p['vehicle_id']=='SX4-01' and p['part_type']=='oil_filter')
        self.selection=['SX4-01',self.part['id']]

    def get(self,items):
        self.client.cookies.set(COOKIE_NAME,quote(json.dumps(items),safe=''))
        return self.client.get('/api/garage')

    def test_empty_garage_needs_no_login_and_has_no_cache(self):
        response=self.client.get('/api/garage')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['applications'],[])
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertNotIn('set-cookie',response.headers)

    def test_cookie_ids_resolve_current_catalog_source_and_configuration(self):
        item=self.get([self.selection]).json()['applications'][0]
        self.assertTrue(item['available'])
        self.assertEqual(item['vehicle']['model'],'SX4')
        self.assertEqual(item['vehicle']['drivetrain'],'AWD')
        self.assertEqual(item['part'],self.part)
        self.assertEqual(item['part']['part_number'],'FL-00251')
        self.assertEqual(item['part']['source'],'generated_demo')

    def test_duplicate_application_only_resolves_once(self):
        self.assertEqual(len(self.get([self.selection,self.selection]).json()['applications']),1)

    def test_unknown_ids_and_wrong_vehicle_never_supply_part_claims(self):
        for selection in [['SX4-01','MISSING'],['RAV4-01',self.part['id']]]:
            with self.subTest(selection=selection):
                item=self.get([selection]).json()['applications'][0]
                self.assertFalse(item['available'])
                self.assertIsNone(item['part'])
                self.assertIsNone(item['vehicle'])

    def test_malformed_oversized_and_injected_cookies_are_recoverable(self):
        for cookie in ['invalid',quote('{}'),quote('[null]'),quote('[[1,2]]'),quote('[[]]'),
                       quote(json.dumps([['x','y']]*21)), 'a'*3801, '['*1200+']'*1200,
                       quote(json.dumps([['SX4-01','<img src=x onerror=alert(1)>']]))]:
            with self.subTest(cookie_type=cookie[:15]):
                data=read_garage(cookie,CATALOG)
                self.assertTrue(data['invalid_cookie'])
                self.assertEqual(data['applications'],[])

    def test_empty_cookie_list_clears_bookmarks(self):
        self.get([self.selection])
        self.assertEqual(self.get([]).json()['applications'],[])

    def test_home_loads_garage_before_chat_with_same_origin_scripts(self):
        html=self.client.get('/').text
        self.assertLess(html.index('/static/garage.js'),html.index('/static/chat.js'))
        self.assertIn('id="garage-open"',html)
        self.assertIn('id="garage-dialog"',html)
        for path in ['/static/garage.js','/static/garage.css']:
            response=self.client.get(path)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers['cache-control'],'no-store')


if __name__=='__main__':
    unittest.main()
