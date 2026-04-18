import gc
import os
import time
import unittest
import uuid

from jarvis_ai.core.scheduler import GoalScheduler
from jarvis_ai.memory.memory_engine import MemoryEngine


class TestLearningLayer(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_learning_{uuid.uuid4().hex}.db"
        self.memory = MemoryEngine(self.db_path)
        self.scheduler = GoalScheduler(db_path=self.db_path)

    def tearDown(self):
        if getattr(self, 'scheduler', None) and getattr(self.scheduler, 'memory_engine', None):
            self.scheduler.memory_engine.close()
            self.scheduler = None
        if getattr(self, 'memory', None):
            self.memory.close()
            self.memory = None
        gc.collect()
        time.sleep(0.05)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_record_and_analytics(self):
        self.memory.record_execution({'id': 'goal-1', 'description': 'T1', 'tags': ['tag1']}, success=True)
        self.memory.record_execution({'id': 'goal-2', 'description': 'T1', 'tags': ['tag1']}, success=False)

        analytics = self.memory.get_analytics()
        self.assertEqual(analytics['overall_success_rate'], 50.0)
        self.assertEqual(len(analytics['tag_stats']), 1)
        self.assertEqual(analytics['tag_stats'][0]['success_rate'], 50.0)

    def test_failure_penalty_caps_at_six(self):
        goal = {'id': 'goal-risky', 'retry_count': 10}
        self.assertEqual(self.scheduler.calculate_failure_penalty(goal), 6)

    def test_pattern_detection(self):
        description = 'Daily Sync'
        for index in range(3):
            self.memory.record_execution({'id': f'goal-{index}', 'description': description}, success=True)

        analytics = self.memory.get_analytics()
        patterns = [pattern['description'] for pattern in analytics['repeated_patterns']]
        self.assertIn(description, patterns)


if __name__ == '__main__':
    unittest.main()
