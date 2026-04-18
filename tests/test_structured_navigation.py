import gc
import os
import sys
import time
import unittest
import urllib.request
import uuid
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain
from jarvis_ai.mobile.server import JarvisServer

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional dependency guard
    sync_playwright = None


class StructuredNavigationBrainTests(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_structured_navigation_{uuid.uuid4().hex}.db"
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
            created_by="test",
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

    def test_backend_blocked_goal_action_includes_blocked_filter(self):
        self._create_blocked_goal("Blocked Navigation Goal", "Owner action is still required")

        result = self.brain.chat_with_metadata("conv-blocked-filter", "show my blocked goals")

        self.assertEqual(result["actions"][0]["target"], "goals")
        self.assertEqual(result["actions"][0]["filter"], "blocked")

    def test_backend_pending_approval_action_includes_pending_filter(self):
        _goal, action_id = self._create_goal_with_pending_action(
            "Pending Approval Goal",
            "Review the pending approval item",
        )

        result = self.brain.chat_with_metadata("conv-pending-filter", "what approvals are waiting")

        self.assertEqual(result["actions"][0]["target"], "approvals")
        self.assertEqual(result["actions"][0]["filter"], "pending")
        self.assertEqual(result["actions"][0]["approval_id"], action_id)

    def test_backend_disabled_permission_action_includes_disabled_filter(self):
        self.brain.permissions.set_permission_state("goals.manage", "disabled")

        result = self.brain.chat_with_metadata("conv-disabled-filter", "what permissions are disabled")

        self.assertEqual(result["actions"][0]["target"], "permissions")
        self.assertEqual(result["actions"][0]["filter"], "disabled")

    def test_backend_specific_goal_action_includes_highlight(self):
        goal = self._create_blocked_goal("Highlighted Goal", "Missing owner confirmation")

        result = self.brain.chat_with_metadata(
            "conv-goal-highlight",
            "why is this goal blocked",
            dashboard_context={
                "focus_goal": {
                    "goal_id": goal["id"],
                    "title": goal["title"],
                    "status": "blocked",
                }
            },
        )

        self.assertEqual(result["actions"][0]["target"], "goals")
        self.assertEqual(result["actions"][0]["highlight"], goal["id"])
        self.assertEqual(result["actions"][0]["filter"], "blocked")


class StructuredNavigationBrowserTests(unittest.TestCase):
    def setUp(self):
        if sync_playwright is None:
            self.skipTest("Playwright is not available in this environment.")

        self.db_path = f"test_structured_navigation_browser_{uuid.uuid4().hex}.db"
        self.secret = f"structured-secret-{uuid.uuid4().hex}"
        self.previous_secret = os.environ.get("JARVIS_SECRET_TOKEN")
        os.environ["JARVIS_SECRET_TOKEN"] = self.secret

        self.brain = Brain({
            "llm": {"provider": "mock"},
            "memory": {"db_path": self.db_path},
            "google": {"enabled": False},
            "security_token": self.secret,
            "capabilities": {"web_automation": {"enabled": True}},
        })
        self.blocked_goal_id, self.blocked_goal_title = self._seed_goal(
            "Blocked Goal for Hint Navigation",
            "Owner review is still missing for this recovery path.",
            status="blocked",
        )
        self._seed_goal(
            "Active Goal for Hint Navigation",
            "This active goal stays visible only on the all/active view.",
            status="active",
        )

        self.server = JarvisServer(self.brain, port=0, host="127.0.0.1", server_config={})
        self.server.start()
        self.base_url = f"http://127.0.0.1:{self.server.httpd.server_address[1]}"

        start = time.time()
        while time.time() - start < 5:
            try:
                with urllib.request.urlopen(f"{self.base_url}/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(0.05)

        self.playwright_manager = sync_playwright().start()
        self.browser = self.playwright_manager.chromium.launch(headless=True)
        self.context = self.browser.new_context(viewport={"width": 1440, "height": 900})
        self.page = self.context.new_page()
        self.page.set_default_timeout(10000)
        self.page.on("dialog", lambda dialog: dialog.accept())

    def tearDown(self):
        for attr_name in ("page", "context", "browser"):
            target = getattr(self, attr_name, None)
            if target:
                try:
                    target.close()
                except Exception:
                    pass
                setattr(self, attr_name, None)
        if getattr(self, "playwright_manager", None):
            try:
                self.playwright_manager.stop()
            except Exception:
                pass
            self.playwright_manager = None
        if getattr(self, "server", None):
            self.server.stop()
            self.server = None
        if getattr(self, "brain", None):
            self.brain.close()
            self.brain = None
        if self.previous_secret is None:
            os.environ.pop("JARVIS_SECRET_TOKEN", None)
        else:
            os.environ["JARVIS_SECRET_TOKEN"] = self.previous_secret
        gc.collect()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except PermissionError:
                pass

    def _seed_goal(self, title, objective, status="draft"):
        goal = self.brain.goal_engine.create_goal(objective, title=title, requires_approval=False)
        updates = {"status": status, "updated_at": datetime.now().isoformat()}
        if status == "blocked":
            updates["last_error"] = objective
        self.brain.memory_engine.update_goal_record(goal["id"], updates)
        self.brain.memory_engine.log_goal_event(
            goal["id"],
            f"goal_{status}",
            from_status="draft",
            to_status=status,
            reason=objective,
        )
        return goal["id"], goal["title"]

    def login_owner(self):
        self.page.goto(f"{self.base_url}/ui", wait_until="domcontentloaded", timeout=30000)
        self.page.wait_for_function(
            """() => {
                const app = document.querySelector('#app');
                const overlay = document.querySelector('#auth-overlay');
                const appVisible = app && !app.classList.contains('hidden');
                const overlayVisible = overlay && !overlay.classList.contains('hidden');
                return Boolean(appVisible || overlayVisible);
            }""",
            timeout=15000,
        )
        if not self.page.locator("#app").is_visible():
            self.page.locator("#auth-token").fill(self.secret)
            self.page.locator("#login-btn").click(force=True)
            self.page.wait_for_function(
                "() => document.querySelector('#app') && !document.querySelector('#app').classList.contains('hidden')",
                timeout=15000,
            )

    def seed_assistant_action(self, action):
        self.page.evaluate(
            """
            (seedAction) => {
                state.assistant.messages = [{
                    id: 'seed-assistant',
                    role: 'assistant',
                    type: 'assistant',
                    body: 'Seeded assistant message for structured navigation testing.',
                    timestamp: new Date().toISOString(),
                    actions: [seedAction]
                }];
                renderAssistantThread();
            }
            """,
            action,
        )

    def test_frontend_chip_click_with_filter_hint_activates_correct_filter(self):
        self.login_owner()
        self.seed_assistant_action({
            "label": "Review Blocked Goals",
            "target": "goals",
            "filter": "blocked",
        })

        self.page.locator(".message-chip").evaluate("(node) => node.click()")
        self.page.wait_for_function(
            """
            () => {
                const button = document.querySelector('[data-goal-filter="blocked"]');
                return button && button.classList.contains('is-active');
            }
            """,
            timeout=10000,
        )

        state_snapshot = self.page.evaluate(
            """
            () => ({
                activeFilter: document.querySelector('[data-goal-filter="blocked"]')?.classList.contains('is-active') || false,
                goalTitles: Array.from(document.querySelectorAll('#page-goals .goal-list [data-goal-id] .goal-card__title')).map((node) => node.textContent.trim())
            })
            """
        )

        self.assertTrue(state_snapshot["activeFilter"])
        self.assertEqual(state_snapshot["goalTitles"], [self.blocked_goal_title])

    def test_frontend_chip_click_with_highlight_hint_pulses_target_goal(self):
        self.login_owner()
        self.seed_assistant_action({
            "label": "View Blocked Goal",
            "target": "goals",
            "goal_id": self.blocked_goal_id,
            "filter": "blocked",
            "highlight": self.blocked_goal_id,
        })

        self.page.locator(".message-chip").evaluate("(node) => node.click()")
        self.page.wait_for_function(
            """
            (goalId) => {
                const card = document.querySelector(`[data-goal-id="${goalId}"]`);
                return Boolean(card && card.classList.contains('axis-highlight'));
            }
            """,
            arg=self.blocked_goal_id,
            timeout=10000,
        )

        state_snapshot = self.page.evaluate(
            """
            (goalId) => {
                const card = document.querySelector(`[data-goal-id="${goalId}"]`);
                const detailTitle = document.querySelector('#page-goals .detail-title');
                return {
                    highlighted: Boolean(card && card.classList.contains('axis-highlight')),
                    selectedGoalId: state.selectedGoalId,
                    detailTitle: detailTitle ? detailTitle.textContent.trim() : null
                };
            }
            """,
            self.blocked_goal_id,
        )

        self.assertTrue(state_snapshot["highlighted"])
        self.assertEqual(state_snapshot["selectedGoalId"], self.blocked_goal_id)
        self.assertEqual(state_snapshot["detailTitle"], self.blocked_goal_title)


if __name__ == "__main__":
    unittest.main()
