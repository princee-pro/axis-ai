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


class TestScrollOwnership(unittest.TestCase):
    def setUp(self):
        if sync_playwright is None:
            self.skipTest("Playwright is not available in this environment.")

        self.db_path = f"test_scroll_ownership_{uuid.uuid4().hex}.db"
        self.secret = f"scroll-secret-{uuid.uuid4().hex}"
        self.previous_secret = os.environ.get("JARVIS_SECRET_TOKEN")
        os.environ["JARVIS_SECRET_TOKEN"] = self.secret

        self.brain = Brain({
            "llm": {"provider": "mock"},
            "memory": {"db_path": self.db_path},
            "google": {"enabled": False},
            "security_token": self.secret,
            "capabilities": {"web_automation": {"enabled": True}},
        })
        self.seed_long_goal()

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
        self.context = self.browser.new_context(viewport={"width": 1440, "height": 480})
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

    def seed_long_goal(self):
        now = datetime.now().isoformat()
        goal_id = f"goal-{uuid.uuid4().hex[:12]}"
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"

        self.brain.memory_engine.create_goal_record({
            "id": goal_id,
            "title": "Scroll Verification Goal",
            "objective": "Confirm long goal detail content remains reachable through the center pane scroller.",
            "status": "planned",
            "priority": "high",
            "created_at": now,
            "updated_at": now,
            "requires_approval": False,
            "current_step_index": 0,
            "summary": "Long-form goal fixture for scroll validation.",
        })
        self.brain.memory_engine.create_plan_record({
            "id": plan_id,
            "goal_id": goal_id,
            "status": "active",
            "created_by": "scroll_test",
            "created_at": now,
            "planner_type": "scroll_test",
            "planner_provider": "fixture",
            "planner_warnings": None,
            "raw_plan_hash": None,
        })

        for index in range(30):
            self.brain.memory_engine.create_plan_step_record({
                "id": f"step-{uuid.uuid4().hex[:10]}",
                "goal_id": goal_id,
                "plan_id": plan_id,
                "step_index": index,
                "title": f"Step {index + 1}",
                "description": (
                    "Scrollable step detail for the regression suite. "
                    "This content is intentionally long enough to push the goal page below the fold."
                ),
                "capability_type": "manual",
                "status": "active" if index == 0 else "planned",
                "requires_approval": False,
                "action_ref": None,
                "result_ref": None,
                "error": None,
            })

        self.brain.memory_engine.log_goal_event(
            goal_id,
            "goal_planned",
            from_status="draft",
            to_status="planned",
            plan_id=plan_id,
            reason="Seeded long goal for scroll ownership regression coverage.",
        )

    def login_owner(self):
        self.page.goto(f"{self.base_url}/ui", wait_until="domcontentloaded", timeout=30000)
        self.page.locator("#auth-token").fill(self.secret)
        self.page.locator("#login-btn").click()
        self.page.wait_for_function(
            "() => document.querySelector('#app') && !document.querySelector('#app').classList.contains('hidden')",
            timeout=15000,
        )

    def open_page(self, page_id):
        self.page.evaluate("(nextPage) => { showPage(nextPage); }", page_id)
        self.page.wait_for_function(
            "(nextPage) => document.querySelector(`#page-${nextPage}`) && !document.querySelector(`#page-${nextPage}`).classList.contains('hidden')",
            arg=page_id,
            timeout=15000,
        )

    def seed_assistant_thread_messages(self, count=48):
        self.page.evaluate(
            """
            (messageCount) => {
                state.assistant.messages = Array.from({ length: messageCount }, (_, index) => ({
                    id: `seed-${index}`,
                    role: index % 2 === 0 ? 'assistant' : 'user',
                    type: index % 2 === 0 ? 'assistant' : 'user',
                    body: `Scrollable assistant message ${index + 1}. ` + 'Signal '.repeat(48),
                    timestamp: new Date(Date.now() + index * 60000).toISOString(),
                    actions: index % 2 === 0 ? [{ label: 'Open Permissions & Access', target: 'permissions' }] : []
                }));
                renderAssistantThread();
            }
            """,
            count,
        )

    def test_body_and_html_do_not_scroll(self):
        self.login_owner()

        state_snapshot = self.page.evaluate(
            """
            () => {
                const html = document.documentElement;
                const body = document.body;
                return {
                    htmlOverflow: getComputedStyle(html).overflowY,
                    bodyOverflow: getComputedStyle(body).overflowY,
                    htmlScrollable: html.scrollHeight > html.clientHeight + 1,
                    bodyScrollable: body.scrollHeight > body.clientHeight + 1
                };
            }
            """
        )

        self.assertEqual(state_snapshot["htmlOverflow"], "hidden")
        self.assertEqual(state_snapshot["bodyOverflow"], "hidden")
        self.assertFalse(state_snapshot["htmlScrollable"])
        self.assertFalse(state_snapshot["bodyScrollable"])

    def test_main_scroll_is_the_center_pane_scroller(self):
        self.login_owner()
        self.open_page("guide")

        scroll_state = self.page.evaluate(
            """
            () => {
                const mainShell = document.querySelector('.main-shell');
                const mainScroll = document.querySelector('.main-scroll');
                const page = document.querySelector('#page-guide');
                return {
                    mainShellOverflow: getComputedStyle(mainShell).overflowY,
                    mainScrollOverflow: getComputedStyle(mainScroll).overflowY,
                    pageOverflow: getComputedStyle(page).overflowY,
                    mainScrollScrollable: mainScroll.scrollHeight > mainScroll.clientHeight + 4
                };
            }
            """
        )

        self.assertEqual(scroll_state["mainShellOverflow"], "hidden")
        self.assertIn(scroll_state["mainScrollOverflow"], ("auto", "scroll"))
        self.assertEqual(scroll_state["pageOverflow"], "visible")
        self.assertTrue(scroll_state["mainScrollScrollable"])

    def test_assistant_thread_scrolls_independently_while_sidebar_stays_fixed(self):
        self.login_owner()
        self.seed_assistant_thread_messages()

        before = self.page.evaluate(
            """
            () => {
                const thread = document.querySelector('.assistant-thread');
                const sidebar = document.querySelector('.sidebar');
                return {
                    canScroll: thread.scrollHeight > thread.clientHeight + 4,
                    scrollTop: thread.scrollTop,
                    sidebarTop: sidebar.getBoundingClientRect().top
                };
            }
            """
        )
        self.page.evaluate(
            """
            () => {
                const thread = document.querySelector('.assistant-thread');
                thread.style.scrollBehavior = 'auto';
                thread.scrollTop = thread.scrollHeight;
            }
            """
        )
        self.page.wait_for_function("() => document.querySelector('.assistant-thread').scrollTop > 0")
        after = self.page.evaluate(
            """
            () => {
                const thread = document.querySelector('.assistant-thread');
                const sidebar = document.querySelector('.sidebar');
                return {
                    scrollTop: thread.scrollTop,
                    sidebarTop: sidebar.getBoundingClientRect().top
                };
            }
            """
        )

        self.assertTrue(before["canScroll"])
        self.assertGreater(after["scrollTop"], before["scrollTop"])
        self.assertAlmostEqual(after["sidebarTop"], before["sidebarTop"], delta=1.0)

    def test_assistant_composer_stays_pinned_during_thread_scroll(self):
        self.login_owner()
        self.seed_assistant_thread_messages()

        before = self.page.evaluate(
            """
            () => {
                const composer = document.querySelector('.assistant-composer');
                return {
                    top: composer.getBoundingClientRect().top,
                    bottom: composer.getBoundingClientRect().bottom
                };
            }
            """
        )
        self.page.evaluate(
            """
            () => {
                const thread = document.querySelector('.assistant-thread');
                thread.style.scrollBehavior = 'auto';
                thread.scrollTop = thread.scrollHeight;
            }
            """
        )
        self.page.wait_for_function("() => document.querySelector('.assistant-thread').scrollTop > 0")
        after = self.page.evaluate(
            """
            () => {
                const composer = document.querySelector('.assistant-composer');
                const shell = document.querySelector('.assistant-shell');
                return {
                    top: composer.getBoundingClientRect().top,
                    bottom: composer.getBoundingClientRect().bottom,
                    shellBottom: shell.getBoundingClientRect().bottom
                };
            }
            """
        )

        self.assertAlmostEqual(after["top"], before["top"], delta=1.0)
        self.assertAlmostEqual(after["bottom"], before["bottom"], delta=1.0)
        self.assertLessEqual(after["bottom"], after["shellBottom"] + 1.0)

    def test_assistant_chip_rows_do_not_break_thread_scroll_or_composer_pin(self):
        self.login_owner()
        self.seed_assistant_thread_messages()

        before = self.page.evaluate(
            """
            () => {
                const thread = document.querySelector('.assistant-thread');
                const composer = document.querySelector('.assistant-composer');
                return {
                    chipCount: document.querySelectorAll('.message-chip').length,
                    threadCanScroll: thread.scrollHeight > thread.clientHeight + 4,
                    composerTop: composer.getBoundingClientRect().top,
                    composerBottom: composer.getBoundingClientRect().bottom
                };
            }
            """
        )

        self.page.evaluate(
            """
            () => {
                const thread = document.querySelector('.assistant-thread');
                thread.style.scrollBehavior = 'auto';
                thread.scrollTop = thread.scrollHeight;
            }
            """
        )
        self.page.wait_for_function("() => document.querySelector('.assistant-thread').scrollTop > 0")

        after = self.page.evaluate(
            """
            () => {
                const thread = document.querySelector('.assistant-thread');
                const composer = document.querySelector('.assistant-composer');
                const shell = document.querySelector('.assistant-shell');
                return {
                    scrollTop: thread.scrollTop,
                    composerTop: composer.getBoundingClientRect().top,
                    composerBottom: composer.getBoundingClientRect().bottom,
                    shellBottom: shell.getBoundingClientRect().bottom
                };
            }
            """
        )

        self.assertGreater(before["chipCount"], 0)
        self.assertTrue(before["threadCanScroll"])
        self.assertGreater(after["scrollTop"], 0)
        self.assertAlmostEqual(after["composerTop"], before["composerTop"], delta=1.0)
        self.assertAlmostEqual(after["composerBottom"], before["composerBottom"], delta=1.0)
        self.assertLessEqual(after["composerBottom"], after["shellBottom"] + 1.0)

    def test_sidebar_nav_scrolls_when_sidebar_content_overflows(self):
        self.login_owner()
        self.page.evaluate(
            """
            () => {
                const nav = document.querySelector('.sidebar-nav');
                for (let index = 0; index < 18; index += 1) {
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.className = 'nav-btn';
                    button.innerHTML = `
                        <span class="nav-btn__icon" aria-hidden="true"></span>
                        <span class="nav-btn__label">Overflow Fixture ${index + 1}</span>
                    `;
                    nav.appendChild(button);
                }
            }
            """
        )

        before = self.page.evaluate(
            """
            () => {
                const nav = document.querySelector('.sidebar-nav');
                const sidebar = document.querySelector('.sidebar');
                return {
                    canScroll: nav.scrollHeight > nav.clientHeight + 4,
                    scrollTop: nav.scrollTop,
                    sidebarTop: sidebar.getBoundingClientRect().top
                };
            }
            """
        )
        self.page.evaluate(
            """
            () => {
                const nav = document.querySelector('.sidebar-nav');
                nav.style.scrollBehavior = 'auto';
                nav.scrollTop = nav.scrollHeight;
            }
            """
        )
        self.page.wait_for_function("() => document.querySelector('.sidebar-nav').scrollTop > 0")
        after = self.page.evaluate(
            """
            () => {
                const nav = document.querySelector('.sidebar-nav');
                const sidebar = document.querySelector('.sidebar');
                return {
                    scrollTop: nav.scrollTop,
                    sidebarTop: sidebar.getBoundingClientRect().top
                };
            }
            """
        )

        self.assertTrue(before["canScroll"])
        self.assertGreater(after["scrollTop"], before["scrollTop"])
        self.assertAlmostEqual(after["sidebarTop"], before["sidebarTop"], delta=1.0)

    def test_goals_page_last_item_is_reachable_via_main_scroll(self):
        self.login_owner()
        self.open_page("goals")
        self.page.wait_for_function("() => document.querySelectorAll('#page-goals .step-card').length >= 30")

        before = self.page.evaluate(
            """
            () => {
                const scroller = document.querySelector('.main-scroll');
                const steps = Array.from(document.querySelectorAll('#page-goals .step-card'));
                const target = steps[steps.length - 1];
                const scrollerRect = scroller.getBoundingClientRect();
                const targetRect = target.getBoundingClientRect();
                return {
                    belowFold: targetRect.bottom > scrollerRect.bottom,
                    scrollable: scroller.scrollHeight > scroller.clientHeight + 4
                };
            }
            """
        )
        self.page.evaluate(
            """
            () => {
                const scroller = document.querySelector('.main-scroll');
                scroller.style.scrollBehavior = 'auto';
                scroller.scrollTop = scroller.scrollHeight;
            }
            """
        )
        self.page.wait_for_function("() => document.querySelector('.main-scroll').scrollTop > 0")
        after = self.page.evaluate(
            """
            () => {
                const scroller = document.querySelector('.main-scroll');
                const steps = Array.from(document.querySelectorAll('#page-goals .step-card'));
                const target = steps[steps.length - 1];
                const scrollerRect = scroller.getBoundingClientRect();
                const targetRect = target.getBoundingClientRect();
                return {
                    scrollTop: scroller.scrollTop,
                    targetBottom: targetRect.bottom,
                    scrollerBottom: scrollerRect.bottom
                };
            }
            """
        )

        self.assertTrue(before["belowFold"])
        self.assertTrue(before["scrollable"])
        self.assertGreater(after["scrollTop"], 0)
        self.assertLessEqual(after["targetBottom"], after["scrollerBottom"] + 2.0)

    def test_permissions_page_rows_are_reachable_via_main_scroll(self):
        self.login_owner()
        self.open_page("permissions")
        self.page.wait_for_function("() => document.querySelectorAll('#page-permissions .permission-grid .permission-card').length > 5")

        before = self.page.evaluate(
            """
            () => {
                const scroller = document.querySelector('.main-scroll');
                const cards = Array.from(document.querySelectorAll('#page-permissions .permission-grid .permission-card'));
                const target = cards[cards.length - 1];
                const scrollerRect = scroller.getBoundingClientRect();
                const targetRect = target.getBoundingClientRect();
                return {
                    belowFold: targetRect.bottom > scrollerRect.bottom,
                    scrollable: scroller.scrollHeight > scroller.clientHeight + 4
                };
            }
            """
        )
        self.page.evaluate(
            """
            () => {
                const scroller = document.querySelector('.main-scroll');
                scroller.style.scrollBehavior = 'auto';
                scroller.scrollTop = scroller.scrollHeight;
            }
            """
        )
        self.page.wait_for_function("() => document.querySelector('.main-scroll').scrollTop > 0")
        after = self.page.evaluate(
            """
            () => {
                const scroller = document.querySelector('.main-scroll');
                const cards = Array.from(document.querySelectorAll('#page-permissions .permission-grid .permission-card'));
                const target = cards[cards.length - 1];
                const scrollerRect = scroller.getBoundingClientRect();
                const targetRect = target.getBoundingClientRect();
                return {
                    scrollTop: scroller.scrollTop,
                    targetBottom: targetRect.bottom,
                    scrollerBottom: scrollerRect.bottom
                };
            }
            """
        )

        self.assertTrue(before["belowFold"])
        self.assertTrue(before["scrollable"])
        self.assertGreater(after["scrollTop"], 0)
        self.assertLessEqual(after["targetBottom"], after["scrollerBottom"] + 2.0)

    def test_capabilities_page_content_is_reachable_via_main_scroll(self):
        self.login_owner()
        self.open_page("guide")
        self.page.wait_for_function(
            "() => document.querySelectorAll('#page-guide .catalog-grid .item-card').length > 3 && document.querySelectorAll('#page-guide .workflow-list .workflow-card').length > 1"
        )

        before = self.page.evaluate(
            """
            () => {
                const scroller = document.querySelector('.main-scroll');
                const workflowCards = Array.from(document.querySelectorAll('#page-guide .workflow-list .workflow-card'));
                const target = workflowCards[workflowCards.length - 1];
                const scrollerRect = scroller.getBoundingClientRect();
                const targetRect = target.getBoundingClientRect();
                return {
                    belowFold: targetRect.bottom > scrollerRect.bottom,
                    scrollable: scroller.scrollHeight > scroller.clientHeight + 4
                };
            }
            """
        )
        self.page.evaluate(
            """
            () => {
                const scroller = document.querySelector('.main-scroll');
                scroller.style.scrollBehavior = 'auto';
                scroller.scrollTop = scroller.scrollHeight;
            }
            """
        )
        self.page.wait_for_function("() => document.querySelector('.main-scroll').scrollTop > 0")
        after = self.page.evaluate(
            """
            () => {
                const scroller = document.querySelector('.main-scroll');
                const workflowCards = Array.from(document.querySelectorAll('#page-guide .workflow-list .workflow-card'));
                const target = workflowCards[workflowCards.length - 1];
                const scrollerRect = scroller.getBoundingClientRect();
                const targetRect = target.getBoundingClientRect();
                return {
                    scrollTop: scroller.scrollTop,
                    targetBottom: targetRect.bottom,
                    scrollerBottom: scrollerRect.bottom
                };
            }
            """
        )

        self.assertTrue(before["belowFold"])
        self.assertTrue(before["scrollable"])
        self.assertGreater(after["scrollTop"], 0)
        self.assertLessEqual(after["targetBottom"], after["scrollerBottom"] + 2.0)


if __name__ == "__main__":
    unittest.main()
