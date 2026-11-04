import unittest
from fastapi.testclient import TestClient
from counterpilot.app import app
from counterpilot.domain import CATALOG


class ChatHomeTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_home_is_the_single_chat_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="chat-form"', response.text)
        self.assertIn('id="search-intro"', response.text)
        self.assertIn('Chat and find your parts.', response.text)
        self.assertNotIn('<nav', response.text)
        self.assertNotIn('id="search-form"', response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertIn("script-src 'self'", response.headers['content-security-policy'])

    def test_old_chat_link_redirects_and_legacy_lookup_assets_are_gone(self):
        response = self.client.get('/chat', follow_redirects=False)
        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers['location'], '/')
        for path in ('/static/index.html', '/static/app.js', '/static/style.css'):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_autocomplete_metadata_only_lists_registered_values(self):
        response = self.client.get('/api/catalog')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['part_aliases'], CATALOG['aliases'])
        self.assertEqual({v['id'] for v in data['vehicles']}, {v['id'] for v in CATALOG['vehicles']})
        for kind in data['part_types']:
            applications = [p for p in CATALOG['parts'] if p['part_type'] == kind['id']]
            self.assertTrue(applications)
            self.assertEqual(kind['positions'], sorted({p['position'] for p in applications if p['position']}))
            self.assertEqual(kind['sides'], sorted({p['side'] for p in applications if p['side']}))


if __name__ == '__main__':
    unittest.main()
