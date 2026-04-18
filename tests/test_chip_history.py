import gc
import json
import os
import sqlite3
import sys
import time
import unittest
import urllib.request
import uuid
from contextlib import closing

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain
from jarvis_ai.mobile.server import JarvisServer

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional dependency guard
    sync_playwright = None


class ChipHistoryServerTests(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_chip_history_{uuid.uuid4().hex}.db"
        self.secret = f"chip-history-secret-{uuid.uuid4().hex}"
        self.previous_secret = os.environ.get("JARVIS_SECRET_TOKEN")
        os.environ["JARVIS_SECRET_TOKEN"] = self.secret

        self.brain = Brain({
            "llm": {"provider": "mock"},
            "memory": {"db_path": self.db_path},
            "google": {"enabled": False},
            "security_token": self.secret,
            "capabilities": {"web_automation": {"enabled": True}},
        })
        self.goal = self._create_blocked_goal("Chip History Goal", "Owner approval is still required for retry.")

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

    def tearDown(self):
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

    def _request(self, method, path, payload=None):
        headers = {
            "X-Jarvis-Token": self.secret,
            "Content-Type": "application/json",
        }
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_post_chat_stores_actions_and_routing_json_in_messages_table(self):
        conversation_id = f"conv-{uuid.uuid4().hex[:10]}"

        response = self._request("POST", "/chat", {
            "conversation_id": conversation_id,
            "message": "show my blocked goals",
        })

        self.assertEqual(response["actions"][0]["target"], "goals")
        self.assertEqual(response["actions"][0]["filter"], "blocked")

        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT role, actions_json, routing_json FROM messages WHERE conversation_id = ? ORDER BY id ASC",
                (conversation_id,),
            ).fetchall()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], "user")
        self.assertIsNone(rows[0][1])
        self.assertIsNone(rows[0][2])
        self.assertEqual(rows[1][0], "assistant")
        self.assertIsNotNone(rows[1][1])
        self.assertIsNotNone(rows[1][2])

        parsed_actions = json.loads(rows[1][1])
        self.assertEqual(parsed_actions[0]["target"], "goals")
        self.assertEqual(parsed_actions[0]["filter"], "blocked")
        parsed_routing = json.loads(rows[1][2])
        self.assertEqual(parsed_routing["intent"], "blocked_goals_summary")
        self.assertEqual(parsed_routing["source"], "control_blocked")

    def test_get_conversation_history_returns_actions_and_routing_per_message(self):
        conversation_id = f"conv-{uuid.uuid4().hex[:10]}"
        self._request("POST", "/chat", {
            "conversation_id": conversation_id,
            "message": "show my blocked goals",
        })

        detail = self._request("GET", f"/conversations/{conversation_id}")

        self.assertEqual(detail["conversation_id"], conversation_id)
        assistant_messages = [message for message in detail["messages"] if message["role"] == "assistant"]
        self.assertEqual(len(assistant_messages), 1)
        self.assertTrue(assistant_messages[0]["actions"])
        self.assertEqual(assistant_messages[0]["actions"][0]["target"], "goals")
        self.assertEqual(assistant_messages[0]["actions"][0]["filter"], "blocked")
        self.assertEqual(assistant_messages[0]["routing"]["intent"], "blocked_goals_summary")
        self.assertEqual(assistant_messages[0]["routing"]["source"], "control_blocked")


class ChipHistoryBrowserTests(unittest.TestCase):
    def setUp(self):
        if sync_playwright is None:
            self.skipTest("Playwright is not available in this environment.")

        self.db_path = f"test_chip_history_browser_{uuid.uuid4().hex}.db"
        self.secret = f"chip-history-browser-secret-{uuid.uuid4().hex}"
        self.previous_secret = os.environ.get("JARVIS_SECRET_TOKEN")
        os.environ["JARVIS_SECRET_TOKEN"] = self.secret

        self.brain = Brain({
            "llm": {"provider": "mock"},
            "memory": {"db_path": self.db_path},
            "google": {"enabled": False},
            "security_token": self.secret,
            "capabilities": {"web_automation": {"enabled": True}},
        })

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
        self.page_errors = []
        self.page.on("dialog", lambda dialog: dialog.accept())
        self.page.on("pageerror", lambda error: self.page_errors.append(str(error)))

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
            timeout=30000,
        )
        if not self.page.locator("#app").is_visible():
            self.page.locator("#auth-token").fill(self.secret)
            self.page.locator("#login-btn").click(force=True)
            self.page.wait_for_function(
                "() => document.querySelector('#app') && !document.querySelector('#app').classList.contains('hidden')",
                timeout=30000,
            )

    def bind_conversation_to_storage(self, conversation_id):
        self.page.evaluate(
            """
            (nextConversationId) => {
                const scope = assistantConversationScopeKey();
                const raw = window.localStorage.getItem('axis_assistant_conv_id');
                const store = raw ? JSON.parse(raw) : {};
                store[scope] = nextConversationId;
                window.localStorage.setItem('axis_assistant_conv_id', JSON.stringify(store));
            }
            """,
            conversation_id,
        )

    def reload_for_restore(self):
        self.page.reload(wait_until="domcontentloaded")
        self.page.wait_for_function(
            "() => document.querySelector('#app') && !document.querySelector('#app').classList.contains('hidden')",
            timeout=30000,
        )
        self.page.wait_for_function(
            "() => document.querySelectorAll('#assistant-thread .message').length > 0",
            timeout=30000,
        )

    def test_restored_assistant_message_with_actions_renders_chips(self):
        conversation_id = f"history-{uuid.uuid4().hex[:10]}"
        self.brain.memory_engine.add_message(
            conversation_id,
            "assistant",
            "You should review the blocked goal next.",
            actions=[{
                "label": "View Blocked Goal",
                "target": "goals",
                "filter": "blocked",
            }],
        )

        self.login_owner()
        self.bind_conversation_to_storage(conversation_id)
        self.reload_for_restore()

        self.page.wait_for_function(
            "() => document.querySelectorAll('#assistant-thread .message-chip').length > 0",
            timeout=15000,
        )
        self.page.wait_for_function(
            "() => (document.querySelector('#assistant-restore-indicator')?.textContent || '').includes('Conversation restored')",
            timeout=15000,
        )

        chip_text = self.page.locator("#assistant-thread .message-chip").first.text_content()
        restore_note = self.page.locator("#assistant-restore-indicator").text_content()

        self.assertEqual(chip_text, "View Blocked Goal")
        self.assertIn("Conversation restored", restore_note)
        self.assertEqual(self.page_errors, [])

    def test_restored_assistant_message_with_null_actions_renders_no_chips_and_no_error(self):
        conversation_id = f"history-{uuid.uuid4().hex[:10]}"
        self.brain.memory_engine.add_message(
            conversation_id,
            "assistant",
            "This restored answer is informational only.",
        )

        self.login_owner()
        self.bind_conversation_to_storage(conversation_id)
        self.reload_for_restore()

        thread_state = self.page.evaluate(
            """
            () => ({
                messageCount: document.querySelectorAll('#assistant-thread .message').length,
                chipCount: document.querySelectorAll('#assistant-thread .message-chip').length
            })
            """
        )

        self.assertGreaterEqual(thread_state["messageCount"], 1)
        self.assertEqual(thread_state["chipCount"], 0)
        self.assertEqual(self.page_errors, [])


if __name__ == "__main__":
    unittest.main()
