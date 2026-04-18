import gc
import os
import sys
import time
import unittest
from unittest.mock import patch
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain


class TestAutonomousLoop(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_autonomous_loop_{uuid.uuid4().hex}.db"
        self.brain = Brain({
            'llm': {'provider': 'mock'},
            'memory': {'db_path': self.db_path},
            'google': {'enabled': False},
            'security_token': 'test-secret',
        })

    def tearDown(self):
        if getattr(self, 'brain', None):
            self.brain.autonomy.stop_autonomous_loop()
            time.sleep(0.05)
            self.brain.close()
            self.brain = None
        gc.collect()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_autonomous_loop_starts_and_stops(self):
        result = self.brain.autonomy.start_autonomous_loop(mode='mock', interval=0.1)
        self.assertEqual(result, 'Started.')
        self.assertTrue(self.brain.autonomy.autonomous_loop_active)

        result = self.brain.autonomy.stop_autonomous_loop()
        self.assertEqual(result, 'Stopped.')
        self.assertFalse(self.brain.autonomy.autonomous_loop_active)

    def test_autonomous_loop_is_idempotent_while_running(self):
        self.brain.autonomy.start_autonomous_loop(mode='mock', interval=0.1)
        result = self.brain.autonomy.start_autonomous_loop(mode='mock', interval=0.1)
        self.assertEqual(result, 'Already running.')

    def test_autonomous_loop_dispatches_selected_goal(self):
        selected_goal = {'id': 'goal-123', 'status': 'pending'}
        with patch.object(self.brain.goal_engine, 'list_goals', return_value=[selected_goal]), \
             patch.object(self.brain.scheduler, 'select_next_goal', side_effect=[selected_goal, None, None]), \
             patch.object(self.brain.autonomy, 'run_goal') as run_goal:
            self.brain.autonomy.start_autonomous_loop(mode='mock', interval=0.05)

            deadline = time.time() + 2
            while not run_goal.called and time.time() < deadline:
                time.sleep(0.05)

            self.brain.autonomy.stop_autonomous_loop()

        self.assertTrue(run_goal.called)
        run_goal.assert_any_call('goal-123', mode='mock')


if __name__ == '__main__':
    unittest.main()
