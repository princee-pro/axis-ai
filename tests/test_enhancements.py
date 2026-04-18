import gc
import os
import sys
import unittest
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain
from jarvis_ai.memory.long_term import LongTermMemory


class TestEnhancements(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_enhancements_{uuid.uuid4().hex}.db"
        self.memory_path = f"test_enhancements_memory_{uuid.uuid4().hex}.json"
        self.brain = Brain({
            'llm': {'provider': 'mock'},
            'memory': {'db_path': self.db_path},
            'google': {'enabled': False},
            'security_token': 'test-secret',
            'capabilities': {'web_automation': {'enabled': True}},
        })
        self.brain.long_term_memory = LongTermMemory(self.memory_path)

    def tearDown(self):
        if getattr(self, 'brain', None):
            self.brain.close()
            self.brain = None
        gc.collect()
        for path in (self.memory_path, self.db_path):
            if os.path.exists(path):
                os.remove(path)

    def test_learning_command(self):
        response = self.brain.think("Learn that the project name is Jarvis 2.0")
        self.assertIn("I have learned that 'the project name' is 'Jarvis 2.0'", response)
        self.assertEqual(self.brain.long_term_memory.load("the project name"), "Jarvis 2.0")

    def test_goal_priority(self):
        self.brain.goal_engine.create_goal("Normal Task", title="Normal Task", priority="normal")
        self.brain.goal_engine.create_goal("Critical Task", title="Critical Task", priority="high")

        goals = self.brain.goal_engine.list_goals()
        goals_by_title = {goal['title']: goal for goal in goals}

        self.assertEqual(goals_by_title['Normal Task']['objective'], 'Normal Task')
        self.assertEqual(goals_by_title['Normal Task']['priority'], 'normal')
        self.assertEqual(goals_by_title['Critical Task']['objective'], 'Critical Task')
        self.assertEqual(goals_by_title['Critical Task']['priority'], 'high')

    def test_progress_tracking(self):
        goal = self.brain.goal_engine.create_goal("Research AI", title="Research AI", priority="high")
        self.brain.goal_engine.plan_goal(goal['id'], brain=self.brain)

        first_resume = self.brain.goal_engine.resume_goal(goal['id'], brain=self.brain)
        action_id = first_resume['next_step']['action_ref']
        self.brain.memory_engine.update_action_status(action_id, 'approved')
        ok, message = self.brain.execute_pending_action(action_id)
        self.assertTrue(ok)
        self.assertIn('Web plan executed', message)

        second_resume = self.brain.goal_engine.resume_goal(goal['id'], brain=self.brain)
        summary = self.brain.get_goal_summary(goal['id'])

        self.assertTrue(second_resume['resumed'])
        self.assertEqual(summary['progress'], '2/3')
        self.assertEqual(summary['completed_steps'], 2)
        self.assertEqual(summary['status'], 'active')


if __name__ == '__main__':
    unittest.main()
