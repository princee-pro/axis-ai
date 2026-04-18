import gc
import json
import os
import sys
import unittest
import urllib.error
import urllib.request
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain
from jarvis_ai.mobile.server import JarvisServer


class TestMobileIntegration(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_mobile_integration_{uuid.uuid4().hex}.db"
        self.secret = f"mobile-integration-secret-{uuid.uuid4().hex}"
        self.brain = Brain({
            'llm': {'provider': 'mock'},
            'memory': {'db_path': self.db_path},
            'google': {'enabled': False},
            'security_token': self.secret,
            'capabilities': {'web_automation': {'enabled': True}},
        })
        self.server = JarvisServer(self.brain, port=0, host='127.0.0.1', server_config={})
        self.server.start()
        self.base_url = f"http://127.0.0.1:{self.server.httpd.server_address[1]}"

    def tearDown(self):
        if getattr(self, 'server', None):
            self.server.stop()
            self.server = None
        if getattr(self, 'brain', None):
            self.brain.close()
            self.brain = None
        gc.collect()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _request_json(self, path, method='GET', payload=None, token=None):
        body = None if payload is None else json.dumps(payload).encode('utf-8')
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={
                'Content-Type': 'application/json',
                'X-Jarvis-Token': token or self.secret,
            },
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode('utf-8'))

    def test_client_server_brain_flow(self):
        status, payload = self._request_json(
            '/chat',
            method='POST',
            payload={'message': 'create a goal to review the release notes'},
        )
        self.assertEqual(status, 200)
        self.assertIn('created a new draft goal', payload['response'])
        self.assertEqual(payload['reply'], payload['response'])

    def test_mobile_goal_execution(self):
        _, created = self._request_json('/goals', method='POST', payload={
            'title': 'Verify mobile integration',
            'objective': 'Verify mobile integration',
            'priority': 'high',
        })
        goal_id = created['goal']['id']

        _, plan = self._request_json(f'/goals/{goal_id}/plan', method='POST', payload={})
        self.assertEqual(plan['planner_type'], 'llm')

        _, resumed = self._request_json(f'/goals/{goal_id}/resume', method='POST', payload={})
        self.assertEqual(resumed['status'], 'awaiting_approval')

        _, summary = self._request_json(f'/goals/{goal_id}/summary')
        self.assertEqual(summary['status'], 'awaiting_approval')
        self.assertTrue(summary['recommended_next_action'].startswith('Approve'))

    def test_unauthorized_access(self):
        request = urllib.request.Request(
            f"{self.base_url}/chat",
            data=json.dumps({'message': 'Hello'}).encode('utf-8'),
            method='POST',
            headers={
                'Content-Type': 'application/json',
                'X-Jarvis-Token': 'wrong-token',
            },
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 403)
        caught.exception.close()


if __name__ == '__main__':
    unittest.main()
