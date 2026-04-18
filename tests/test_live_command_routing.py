import gc
import os
import sys
import unittest
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain


class TestLiveCommandRouting(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_live_command_routing_{uuid.uuid4().hex}.db"
        self.brain = Brain({
            "llm": {"provider": "mock"},
            "memory": {"db_path": self.db_path},
            "google": {"enabled": False},
            "capabilities": {"web_automation": {"enabled": True}},
        })

    def tearDown(self):
        if getattr(self, "brain", None):
            self.brain.close()
            self.brain = None
        gc.collect()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except PermissionError:
                pass

    def _create_goal_with_pending_action(self, title, objective, action_id=None):
        action_id = action_id or str(uuid.uuid4())[:8]
        goal = self.brain.goal_engine.create_goal(objective, title=title, requires_approval=True)
        plan_id = str(uuid.uuid4())[:12]
        step_id = str(uuid.uuid4())[:8]

        self.brain.memory_engine.create_plan_record({
            "id": plan_id,
            "goal_id": goal["id"],
            "status": "active",
            "risk_summary": None,
            "created_by": "test",
            "created_at": goal["created_at"],
            "planner_type": "test",
            "planner_provider": "unit",
            "planner_warnings": None,
            "raw_plan_hash": None,
        })
        self.brain.memory_engine.create_plan_step_record({
            "id": step_id,
            "goal_id": goal["id"],
            "plan_id": plan_id,
            "step_index": 0,
            "title": "Review approval",
            "description": objective,
            "capability_type": "web.plan.execute",
            "status": "awaiting_approval",
            "requires_approval": True,
            "action_ref": action_id,
            "result_ref": None,
            "error": None,
        })
        self.brain.memory_engine.create_pending_action(
            action_id,
            "web.plan.execute",
            {"objective": objective, "steps": []},
            created_by="test"
        )
        self.brain.memory_engine.update_goal_record(goal["id"], {"status": "awaiting_approval"})
        self.brain.memory_engine.log_goal_event(
            goal["id"],
            "awaiting_approval",
            from_status="draft",
            to_status="awaiting_approval",
            reason="Waiting for owner review",
            plan_id=plan_id,
            step_id=step_id,
            action_ref=action_id,
        )
        return goal, action_id

    def _create_blocked_goal(self, title, reason):
        goal = self.brain.goal_engine.create_goal(reason, title=title, requires_approval=True)
        self.brain.memory_engine.update_goal_record(goal["id"], {"status": "blocked", "last_error": reason})
        self.brain.memory_engine.log_goal_event(
            goal["id"],
            "goal_blocked",
            from_status="draft",
            to_status="blocked",
            reason=reason,
        )
        return goal

    def test_pending_approvals_summary_command(self):
        goal, _action_id = self._create_goal_with_pending_action(
            "Review Landing Page",
            "Review the landing page approval request"
        )

        result = self.brain.chat_with_metadata("conv-approvals", "summarize my pending approvals")

        self.assertEqual(result["routing"]["intent"], "pending_approvals_summary")
        self.assertIn("actionable approval item", result["reply"])
        self.assertIn(goal["title"], result["reply"])
        self.assertEqual(result["routing"]["context"]["approvals_count"], 1)
        self.assertEqual(result["actions"][0]["target"], "approvals")
        self.assertEqual(result["actions"][0]["approval_id"], _action_id)

    def test_pending_approvals_summary_reports_total_count_beyond_preview(self):
        for index in range(9):
            self._create_goal_with_pending_action(
                f"Approval Goal {index}",
                f"Review pending approval {index}"
            )

        result = self.brain.chat_with_metadata("conv-approvals-many", "summarize my pending approvals")

        self.assertEqual(result["routing"]["intent"], "pending_approvals_summary")
        self.assertIn("9 actionable approval item(s)", result["reply"])
        self.assertEqual(result["routing"]["context"]["approvals_count"], 9)

    def test_blocked_goals_summary_command(self):
        goal = self._create_blocked_goal("Broken Checkout", "Owner review is required before retrying checkout flow")

        result = self.brain.chat_with_metadata("conv-blocked", "show my blocked goals")

        self.assertEqual(result["routing"]["intent"], "blocked_goals_summary")
        self.assertIn(goal["title"], result["reply"])
        self.assertIn("Owner review is required", result["reply"])
        self.assertEqual(result["routing"]["context"]["blocked_count"], 1)
        self.assertEqual(result["actions"][0]["target"], "goals")
        self.assertEqual(result["actions"][0]["goal_id"], goal["id"])

    def test_blocked_goals_summary_reports_total_count_beyond_preview(self):
        for index in range(9):
            self._create_blocked_goal(
                f"Blocked Goal {index}",
                f"Blocked reason {index}"
            )

        result = self.brain.chat_with_metadata("conv-blocked-many", "show my blocked goals")

        self.assertEqual(result["routing"]["intent"], "blocked_goals_summary")
        self.assertIn("9 blocked item(s)", result["reply"])
        self.assertEqual(result["routing"]["context"]["blocked_count"], 9)

    def test_create_goal_from_command(self):
        result = self.brain.chat_with_metadata("conv-create", "create a goal to review pending approvals")
        goals = self.brain.goal_engine.list_goals()

        self.assertEqual(result["routing"]["intent"], "create_goal")
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0]["status"], "draft")
        self.assertIn("created a new draft goal", result["reply"].lower())
        self.assertIn(result["routing"]["context"]["goal_id"], [goal["id"] for goal in goals])
        self.assertEqual(result["actions"][0]["target"], "goals")
        self.assertEqual(result["actions"][0]["goal_id"], result["routing"]["context"]["goal_id"])

    def test_recommended_next_action_command(self):
        goal, _action_id = self._create_goal_with_pending_action(
            "Review Pricing Approval",
            "Review the pricing approval request"
        )

        result = self.brain.chat_with_metadata("conv-next", "what should I do next")

        self.assertEqual(result["routing"]["intent"], "recommended_next_actions")
        self.assertIn("Based on the live system state", result["reply"])
        self.assertIn(goal["title"], result["reply"])
        self.assertTrue(result["routing"]["context"]["recommendations"])

    def test_create_goal_command_is_blocked_when_goal_management_disabled(self):
        self.brain.permissions.set_permission_state("goals.manage", "disabled")

        result = self.brain.chat_with_metadata("conv-create-blocked", "create a goal to review permissions")

        self.assertEqual(result["routing"]["intent"], "permission_blocked_goal_creation")
        self.assertIn("Permissions & Access", result["reply"])
        self.assertEqual(self.brain.memory_engine.count_permission_requests(status="pending"), 1)
        self.assertEqual(result["routing"]["context"]["permission_key"], "goals.manage")
        self.assertIsNotNone(result["routing"]["context"]["permission_request"])

    def test_pending_approvals_command_is_blocked_when_permission_disabled(self):
        self.brain.permissions.set_permission_state("approvals.manage", "disabled")

        result = self.brain.chat_with_metadata("conv-approvals-blocked", "what is waiting for approval")

        self.assertEqual(result["routing"]["intent"], "permission_blocked_approvals")
        self.assertIn("Permissions & Access", result["reply"])
        self.assertEqual(result["routing"]["context"]["permission_key"], "approvals.manage")
        self.assertEqual(self.brain.memory_engine.count_permission_requests(status="pending"), 1)

    def test_disabled_permissions_command_reports_live_permission_state(self):
        self.brain.permissions.set_permission_state("goals.manage", "disabled")

        result = self.brain.chat_with_metadata("conv-disabled", "what permissions are disabled")

        self.assertEqual(result["routing"]["intent"], "disabled_permissions_summary")
        self.assertIn("Goal management", result["reply"])
        self.assertTrue(any(item["key"] == "goals.manage" for item in result["routing"]["context"]["disabled_permissions"]))
        self.assertEqual(result["actions"][0]["target"], "permissions")

    def test_access_overview_command_reports_real_access_snapshot(self):
        result = self.brain.chat_with_metadata("conv-access", "what can Axis currently access")

        self.assertEqual(result["routing"]["intent"], "access_overview")
        self.assertIn("active permission(s)", result["reply"])
        self.assertGreater(len(result["routing"]["context"]["active_permissions"]), 0)

    def test_profile_plan_command_reports_active_workspace_plan(self):
        result = self.brain.chat_with_metadata("conv-plan", "what plan am i on")

        self.assertEqual(result["routing"]["intent"], "profile_plan_summary")
        self.assertIn("Axis is currently running as", result["reply"])
        self.assertEqual(result["routing"]["context"]["active_plan"]["id"], "foundation_free")
        self.assertEqual(result["routing"]["context"]["active_profile"]["profile_type"], "developer")

    def test_axis_hub_command_reports_skill_registry_snapshot(self):
        result = self.brain.chat_with_metadata("conv-axis-hub", "show axis hub")

        self.assertEqual(result["routing"]["intent"], "axis_hub_summary")
        self.assertIn("Axis Hub currently tracks", result["reply"])
        self.assertGreater(len(result["routing"]["context"]["skills"]), 0)

    def test_page_walkthrough_uses_dashboard_context(self):
        goal = self._create_blocked_goal("Checkout Recovery", "Owner input is still missing for the retry path")

        result = self.brain.chat_with_metadata(
            "conv-page",
            "walk me through this page",
            dashboard_context={
                "page_id": "goals",
                "page_title": "Goals",
                "page_purpose": "Use Goals to manage durable work items and understand exact execution state.",
                "page_sections": ["Goal queue", "Focused goal detail", "Goal timeline"],
                "system_state": {
                    "active_goals_count": 0,
                    "pending_approvals_count": 0,
                    "blocked_items_count": 1,
                    "disabled_permissions_count": 2,
                },
                "focus_goal": {
                    "goal_id": goal["id"],
                    "title": goal["title"],
                    "status": "blocked",
                    "blocked_reason": "Owner input is still missing for the retry path",
                },
            },
        )

        self.assertEqual(result["routing"]["intent"], "page_walkthrough")
        self.assertIn("You're on Goals.", result["reply"])
        self.assertIn("Goal queue", result["reply"])
        self.assertIn(goal["title"], result["reply"])
        self.assertEqual(result["routing"]["context"]["page_id"], "goals")

    def test_current_capabilities_uses_dashboard_page_context(self):
        result = self.brain.chat_with_metadata(
            "conv-capabilities",
            "what can Axis do right now",
            dashboard_context={
                "page_id": "permissions",
                "page_title": "Permissions & Access",
            },
        )

        self.assertEqual(result["routing"]["intent"], "current_capabilities")
        self.assertIn("Axis currently has", result["reply"])
        self.assertIn("On Permissions & Access I can explain", result["reply"])
        self.assertEqual(result["routing"]["context"]["page_id"], "permissions")
        self.assertEqual(result["actions"][0]["target"], "capabilities")

    def test_goal_block_reason_prefers_dashboard_focus_goal(self):
        focused_goal = self._create_blocked_goal("Focused Goal", "Passport information is still missing")
        other_goal = self._create_blocked_goal("Other Goal", "Waiting on another dependency")

        result = self.brain.chat_with_metadata(
            "conv-goal-blocked-focused",
            "why is this goal blocked",
            dashboard_context={
                "focus_goal": {
                    "goal_id": focused_goal["id"],
                    "title": focused_goal["title"],
                    "status": "blocked",
                }
            },
        )

        self.assertEqual(result["routing"]["intent"], "goal_block_reason")
        self.assertIn(focused_goal["title"], result["reply"])
        self.assertIn("Passport information is still missing", result["reply"])
        self.assertNotIn(other_goal["title"], result["reply"])

    def test_goal_block_reason_command_mentions_related_permission_dependency(self):
        self.brain.permissions.set_permission_state("browser.web_automation", "disabled")
        goal = self.brain.goal_engine.create_goal(
            "Open a website and inspect the pricing page",
            title="Website Audit",
            requires_approval=False,
        )
        self.brain.goal_engine.plan_goal(goal["id"], brain=None)

        ok, message = self.brain.goal_engine.advance_goal(goal["id"], self.brain)
        self.assertFalse(ok)
        self.assertIn("Web automation", message)

        result = self.brain.chat_with_metadata("conv-goal-blocked", "why is this goal blocked")

        self.assertEqual(result["routing"]["intent"], "goal_block_reason")
        self.assertIn("Website Audit", result["reply"])
        self.assertIn("Web automation", result["reply"])
        self.assertTrue(
            any(item["key"] == "browser.web_automation" for item in result["routing"]["context"]["related_permissions"])
        )

    def test_grounded_fallback_when_no_data_exists(self):
        result = self.brain.chat_with_metadata("conv-fallback", "tell me something useful")

        self.assertEqual(result["routing"]["intent"], "grounded_fallback")
        self.assertIn("0 active goal(s)", result["reply"])
        self.assertIn("0 actionable approval item(s)", result["reply"])
        self.assertIn("create a goal", result["reply"].lower())


if __name__ == "__main__":
    unittest.main()
