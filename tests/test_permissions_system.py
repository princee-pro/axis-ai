import gc
import os
import sys
import unittest
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain


class TestPermissionsSystem(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_permissions_system_{uuid.uuid4().hex}.db"
        self.config = {
            "llm": {"provider": "mock"},
            "memory": {"db_path": self.db_path},
            "google": {"enabled": False},
            "capabilities": {"web_automation": {"enabled": True}},
        }
        self.brain = Brain(self.config)
        self.extra_brains = []

    def tearDown(self):
        brains = [self.brain] + self.extra_brains
        for brain in brains:
            if brain:
                brain.notifications.stop()
        self.brain = None
        self.extra_brains = []
        gc.collect()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except PermissionError:
                pass

    def test_permission_state_persists_across_brain_restart(self):
        self.brain.permissions.set_permission_state("goals.execute", "disabled")

        restarted = Brain(self.config)
        self.extra_brains.append(restarted)
        permission = restarted.permissions.get_permission(
            "goals.execute",
            runtime=restarted.get_permission_runtime(),
        )

        self.assertEqual(permission["current_state"], "disabled")
        self.assertEqual(permission["effective_status"], "disabled")
        self.assertFalse(restarted.permissions.is_allowed("goals.execute", runtime=restarted.get_permission_runtime()))

    def test_permission_block_creates_single_pending_request(self):
        self.brain.permissions.set_permission_state("goals.manage", "disabled")

        block_one = self.brain.permissions.build_permission_block(
            "goals.manage",
            "Goal creation is blocked for this request.",
            goal_id="goal-123",
            goal_title="Permissions Goal",
            action_label="Create a goal",
            source="unit_test",
        )
        block_two = self.brain.permissions.build_permission_block(
            "goals.manage",
            "Goal creation is blocked for this request.",
            goal_id="goal-123",
            goal_title="Permissions Goal",
            action_label="Create a goal",
            source="unit_test",
        )

        self.assertEqual(self.brain.memory_engine.count_permission_requests(status="pending"), 1)
        self.assertEqual(
            block_one["permission_request"]["id"],
            block_two["permission_request"]["id"],
        )

    def test_capabilities_guide_exposes_realism_summary_and_workflows(self):
        guide = self.brain.get_capabilities_guide()
        keys = {item["key"] for item in guide["capabilities"]}

        self.assertIn("permissions", keys)
        self.assertIn("execution_realism", keys)
        self.assertIn("chrome_control", keys)
        self.assertIn("goal_lifecycle", {item["key"] for item in guide["workflows"]})
        self.assertEqual(sum(guide["summary"].values()), len(guide["capabilities"]))


if __name__ == "__main__":
    unittest.main()
