import gc
import os
import sys
import unittest
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain


class TestExecutionRealismControls(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_execution_realism_{uuid.uuid4().hex}.db"
        self.brain = Brain({
            "llm": {"provider": "mock"},
            "memory": {"db_path": self.db_path},
            "google": {"enabled": False},
            "capabilities": {"web_automation": {"enabled": True}},
        })

    def tearDown(self):
        if getattr(self, "brain", None):
            self.brain.notifications.stop()
            self.brain = None
        gc.collect()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except PermissionError:
                pass

    def _create_planned_goal(self, objective="Prepare a project summary", title="Project Summary"):
        goal = self.brain.goal_engine.create_goal(objective, title=title, requires_approval=True)
        plan = self.brain.goal_engine.plan_goal(goal["id"], brain=None)
        self.assertNotIn("error", plan)
        return goal

    def test_goal_pause_edit_resume_and_stop_flow(self):
        goal = self._create_planned_goal()

        pause = self.brain.goal_engine.pause_goal(goal["id"])
        self.assertTrue(pause["paused"])

        paused_summary = self.brain.get_goal_summary(goal["id"])
        self.assertTrue(paused_summary["execution_state"]["is_paused"])
        self.assertTrue(paused_summary["controls"]["can_resume"])

        edit = self.brain.goal_engine.edit_goal(goal["id"], {
            "title": "Project Summary Revised",
            "objective": "Prepare a revised project summary",
        })
        self.assertEqual(edit["goal"]["title"], "Project Summary Revised")

        resume = self.brain.goal_engine.resume_goal(goal["id"], self.brain)
        self.assertTrue(resume["resumed"])
        self.assertIn("Awaiting approval", resume["message"])

        resumed_summary = self.brain.get_goal_summary(goal["id"])
        self.assertEqual(resumed_summary["status"], "awaiting_approval")
        self.assertEqual(len(resumed_summary["waiting_approvals"]), 1)

        stop = self.brain.goal_engine.stop_goal(goal["id"])
        self.assertTrue(stop["stopped"])

        stopped_summary = self.brain.get_goal_summary(goal["id"])
        self.assertEqual(stopped_summary["status"], "stopped")
        self.assertTrue(stopped_summary["execution_state"]["is_terminal"])

    def test_advance_goal_is_blocked_when_execution_permission_is_disabled(self):
        goal = self._create_planned_goal(title="Execution Gate")
        self.brain.permissions.set_permission_state("goals.execute", "disabled")

        ok, message = self.brain.goal_engine.advance_goal(goal["id"], self.brain)

        self.assertFalse(ok)
        self.assertIn("Goal execution", message)
        summary = self.brain.get_goal_summary(goal["id"])
        self.assertEqual(summary["status"], "blocked")
        self.assertIn("Goal execution", summary["blocked_reason"])
        self.assertEqual(self.brain.memory_engine.count_permission_requests(status="pending"), 1)


if __name__ == "__main__":
    unittest.main()
