import gc
import io
import json
import os
import sys
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain


class TestAPIIntegration(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_api_integration_{uuid.uuid4().hex}.db"
        self.brain = Brain({
            'llm': {'provider': 'mock'},
            'memory': {'db_path': self.db_path},
            'google': {'enabled': False},
            'security_token': 'test-secret',
        })

    def tearDown(self):
        if getattr(self, 'brain', None):
            self.brain.close()
            self.brain = None
        gc.collect()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_api_initialization(self):
        self.assertIsNotNone(self.brain.api)

    def test_weather_api_mock(self):
        result = self.brain.api.get_weather('Kigali', goal_id=None)
        self.assertIn('city', result)
        self.assertIn('temperature', result)
        self.assertIn('condition', result)
        self.assertTrue(result['mock'])

    def test_news_api_mock(self):
        result = self.brain.api.get_news('technology', goal_id=None)
        self.assertIn('category', result)
        self.assertIn('articles', result)
        self.assertGreater(len(result['articles']), 0)
        self.assertTrue(result['mock'])

    def test_stock_api_mock(self):
        result = self.brain.api.get_stock_price('AAPL', goal_id=None)
        self.assertIn('symbol', result)
        self.assertIn('price', result)
        self.assertIn('change', result)
        self.assertTrue(result['mock'])

    def test_api_caching(self):
        result_one = self.brain.api.get_weather('Kigali')
        result_two = self.brain.api.get_weather('Kigali')
        self.assertEqual(result_one, result_two)

    def test_make_request_handles_http_errors(self):
        error = urllib.error.HTTPError(
            'https://example.com',
            503,
            'Service Unavailable',
            {},
            io.BytesIO(b''),
        )
        with patch('urllib.request.urlopen', side_effect=error):
            result = self.brain.api.make_request('https://example.com/data')
        error.close()
        self.assertIn('error', result)
        self.assertIn('HTTP error 503', result['error'])


if __name__ == '__main__':
    unittest.main()
