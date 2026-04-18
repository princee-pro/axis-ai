import gc
import os
import sys
import unittest
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain


class TestBrainGoals(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_brain_goals_{uuid.uuid4().hex}.db"
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

    def test_add_goal_command(self):
        response = self.brain.think("Add a goal: Learn Python")
        self.assertIn("Goal added", response)
        self.assertIn("Learn Python", response)
        self.assertIn("multi-step plan", response)

        goals = self.brain.goal_engine.list_goals()
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0]['objective'], "Learn Python")

        goal_context = self.brain.goal_engine.get_goal_context(goals[0]['id'])
        self.assertGreater(len(goal_context['steps']), 0)

    def test_list_goals_command(self):
        goal_a = self.brain.goal_engine.create_goal("Goal A", title="Goal A")
        goal_b = self.brain.goal_engine.create_goal("Goal B", title="Goal B")

        goals = self.brain.goal_engine.list_goals()
        goal_ids = {goal['id'] for goal in goals}
        goal_titles = {goal['title'] for goal in goals}

        self.assertIn(goal_a['id'], goal_ids)
        self.assertIn(goal_b['id'], goal_ids)
        self.assertIn("Goal A", goal_titles)
        self.assertIn("Goal B", goal_titles)
        self.assertTrue(all(isinstance(goal['id'], str) for goal in goals))

    def test_complete_goal_command(self):
        goal = self.brain.goal_engine.create_goal("Goal to Complete", title="Goal to Complete")
        self.brain.goal_engine.complete_goal(goal['id'])

        summary = self.brain.get_goal_summary(goal['id'])
        self.assertEqual(summary['status'], "completed")
        self.assertFalse(summary['execution_state']['is_blocked'])


if __name__ == '__main__':
    unittest.main()
