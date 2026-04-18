import gc
import os
import unittest
import uuid

from jarvis_ai.agents.planner import PlannerAgent
from jarvis_ai.core.goal_engine import GoalEngine
from jarvis_ai.memory.memory_engine import MemoryEngine


class TestGoalSystem(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_goal_engine_{uuid.uuid4().hex}.db"
        self.memory = MemoryEngine(self.db_path)
        self.engine = GoalEngine(self.memory)
        self.planner = PlannerAgent(brain=None)

    def tearDown(self):
        if getattr(self, 'memory', None):
            self.memory.close()
            self.memory = None
        gc.collect()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_add_goal(self):
        goal = self.engine.create_goal('Test Goal', title='Test Goal', priority='normal')
        self.assertIsInstance(goal['id'], str)
        self.assertEqual(goal['objective'], 'Test Goal')
        self.assertEqual(goal['status'], 'draft')

    def test_complete_goal(self):
        goal = self.engine.create_goal('Test Goal', title='Test Goal')
        self.engine.complete_goal(goal['id'])

        updated = self.engine.get_goal_context(goal['id'])
        self.assertEqual(updated['status'], 'completed')

    def test_builtin_planning_creates_goal_steps(self):
        goal = self.engine.create_goal('Inspect website pricing', title='Inspect website pricing')
        result = self.engine.plan_goal(goal['id'])
        self.assertEqual(result['planner_type'], 'fallback')
        self.assertEqual(result['steps_count'], 1)

        context = self.engine.get_goal_context(goal['id'])
        self.assertEqual(context['status'], 'planned')
        self.assertEqual(context['steps'][0]['capability_type'], 'web_plan')

    def test_planner_steps(self):
        steps = self.planner.create_plan('Summarize file report.txt')
        self.assertIn('write file report.txt', steps[1].lower())

        steps_default = self.planner.create_plan('Something random')
        self.assertGreater(len(steps_default), 0)


if __name__ == '__main__':
    unittest.main()
