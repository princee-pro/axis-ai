import gc
import os
import sys
import unittest
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain


class TestAutonomy(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_autonomy_{uuid.uuid4().hex}.db"
        self.secret = f"test-secret-{uuid.uuid4().hex}"

    def tearDown(self):
        brain = getattr(self, 'brain', None)
        if brain is not None:
            brain.close()
            self.brain = None
        gc.collect()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _build_brain(self, *, web_enabled):
        self.brain = Brain({
            'llm': {'provider': 'mock'},
            'memory': {'db_path': self.db_path},
            'google': {'enabled': False},
            'security_token': self.secret,
            'capabilities': {'web_automation': {'enabled': web_enabled}},
        })
        return self.brain

    def test_resume_goal_enters_approval_queue(self):
        brain = self._build_brain(web_enabled=True)
        goal = brain.goal_engine.create_goal('Research AI', title='Research AI', priority='high')
        brain.goal_engine.plan_goal(goal['id'], brain=brain)

        response = brain.goal_engine.resume_goal(goal['id'], brain=brain)
        summary = brain.get_goal_summary(goal['id'])

        self.assertTrue(response['resumed'])
        self.assertEqual(response['status'], 'awaiting_approval')
        self.assertIn('Approve pending action', response['recommended_next_action'])
        self.assertEqual(summary['status'], 'awaiting_approval')
        self.assertEqual(summary['step_status_counts']['awaiting_approval'], 1)

    def test_resume_goal_blocks_when_required_capability_is_unavailable(self):
        brain = self._build_brain(web_enabled=False)
        goal = brain.goal_engine.create_goal('Research AI', title='Research AI', priority='high')
        brain.goal_engine.plan_goal(goal['id'], brain=brain)

        response = brain.goal_engine.resume_goal(goal['id'], brain=brain)
        summary = brain.get_goal_summary(goal['id'])

        self.assertFalse(response['resumed'])
        self.assertEqual(response['status'], 'blocked')
        self.assertIn('Web automation is currently unavailable', response['message'])
        self.assertEqual(summary['status'], 'blocked')
        self.assertEqual(summary['step_status_counts']['blocked'], 1)


if __name__ == '__main__':
    unittest.main()
