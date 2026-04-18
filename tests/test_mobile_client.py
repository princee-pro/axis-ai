import gc
import json
import os
import sys
import unittest
import urllib.request
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain
from jarvis_ai.mobile.server import JarvisServer


class TestMobileClient(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_mobile_client_{uuid.uuid4().hex}.db"
        self.secret = f"mobile-secret-{uuid.uuid4().hex}"
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

    def _request_json(self, path, method='GET', payload=None):
        body = None if payload is None else json.dumps(payload).encode('utf-8')
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={
                'Content-Type': 'application/json',
                'X-Jarvis-Token': self.secret,
            },
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode('utf-8'))

    def test_add_goal_via_client(self):
        status, response = self._request_json('/goals', method='POST', payload={
            'title': 'Test mobile integration',
            'objective': 'Test mobile integration',
            'priority': 'high',
        })
        self.assertEqual(status, 200)
        self.assertIn('goal', response)
        self.assertEqual(response['goal']['title'], 'Test mobile integration')
        self.assertEqual(response['goal']['priority'], 'high')
        self.assertEqual(response['goal']['status'], 'draft')

        status, goals_payload = self._request_json('/goals')
        self.assertEqual(status, 200)
        self.assertEqual(len(goals_payload['goals']), 1)
        self.assertEqual(goals_payload['goals'][0]['title'], 'Test mobile integration')

    def test_remote_goal_execution(self):
        _, created = self._request_json('/goals', method='POST', payload={
            'title': 'Test autonomous execution',
            'objective': 'Test autonomous execution',
            'priority': 'high',
        })
        goal_id = created['goal']['id']

        status, plan = self._request_json(f'/goals/{goal_id}/plan', method='POST', payload={})
        self.assertEqual(status, 200)
        self.assertEqual(plan['steps_count'], 3)

        status, resumed = self._request_json(f'/goals/{goal_id}/resume', method='POST', payload={})
        self.assertEqual(status, 200)
        self.assertEqual(resumed['status'], 'awaiting_approval')
        self.assertIn('Approve pending action', resumed['recommended_next_action'])

        status, summary = self._request_json(f'/goals/{goal_id}/summary')
        self.assertEqual(status, 200)
        self.assertEqual(summary['status'], 'awaiting_approval')
        self.assertEqual(len(summary['waiting_approvals']), 1)

    def test_status_endpoint_logs(self):
        self._request_json('/goals', method='POST', payload={
            'title': 'Status goal',
            'objective': 'Status goal',
            'priority': 'normal',
        })

        status, payload = self._request_json('/status')
        self.assertEqual(status, 200)
        self.assertIn('active_goals', payload)
        self.assertEqual(len(payload['active_goals']), 1)
        self.assertIn('autonomous_loop_active', payload)


if __name__ == '__main__':
    unittest.main()
