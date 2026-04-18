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


class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_integration_{uuid.uuid4().hex}.db"
        self.secret = f"test-secret-{uuid.uuid4().hex}"
        self.brain = Brain({
            'llm': {'provider': 'mock'},
            'memory': {'db_path': self.db_path},
            'google': {'enabled': False},
            'security_token': self.secret,
            'capabilities': {'web_automation': {'enabled': True}},
        })
        self.server = None

    def tearDown(self):
        if self.server is not None:
            self.server.stop()
            self.server = None
        if getattr(self, 'brain', None):
            self.brain.close()
            self.brain = None
        gc.collect()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _start_server(self):
        if self.server is None:
            self.server = JarvisServer(self.brain, port=0, host='127.0.0.1', server_config={})
            self.server.start()
            self.base_url = f"http://127.0.0.1:{self.server.httpd.server_address[1]}"

    def _request_json(self, path, method='GET', payload=None, headers=None):
        body = None if payload is None else json.dumps(payload).encode('utf-8')
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={
                'Content-Type': 'application/json',
                'X-Jarvis-Token': self.secret,
                **(headers or {}),
            },
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode('utf-8'))

    def test_full_goal_autonomous_execution(self):
        goal = self.brain.goal_engine.create_goal('Prepare a project summary', title='AI Trends Brief', priority='high')
        plan = self.brain.goal_engine.plan_goal(goal['id'], brain=self.brain)
        self.assertEqual(plan['planner_type'], 'llm')
        self.assertEqual(plan['steps_count'], 3)

        goal_context = self.brain.goal_engine.get_goal_context(goal['id'])
        self.assertEqual(len(goal_context['steps']), 3)
        self.assertEqual(goal_context['steps'][0]['capability_type'], 'web_plan')

        first_resume = self.brain.goal_engine.resume_goal(goal['id'], brain=self.brain)
        self.assertEqual(first_resume['status'], 'awaiting_approval')
        self.assertIn('Approve pending action', first_resume['recommended_next_action'])

        action_id = first_resume['next_step']['action_ref']
        self.assertTrue(self.brain.memory_engine.update_action_status(action_id, 'approved'))
        ok, message = self.brain.execute_pending_action(action_id)
        self.assertTrue(ok)
        self.assertIn('Web plan executed', message)

        second_resume = self.brain.goal_engine.resume_goal(goal['id'], brain=self.brain)
        summary = self.brain.get_goal_summary(goal['id'])

        self.assertTrue(second_resume['resumed'])
        self.assertEqual(second_resume['completed_steps'], 2)
        self.assertEqual(second_resume['next_step']['title'], 'Manual review')
        self.assertEqual(summary['progress'], '2/3')
        self.assertEqual(summary['status'], 'active')

    def test_mobile_integration(self):
        self._start_server()

        status, payload = self._request_json(
            '/chat',
            method='POST',
            payload={'message': 'create a goal to review the release notes'},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload['reply'], payload['response'])
        self.assertIn('created a new draft goal', payload['response'])
        self.assertEqual(payload['actions'][0]['label'], 'Open Goal')

        status, whoami = self._request_json('/whoami')
        self.assertEqual(status, 200)
        self.assertTrue(whoami['is_owner'])
        self.assertEqual(whoami['auth_context']['type'], 'owner')


if __name__ == '__main__':
    unittest.main()
