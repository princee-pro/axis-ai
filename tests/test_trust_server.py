import gc
import json
import os
import sys
import time
import unittest
import urllib.error
import urllib.request
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain
from jarvis_ai.mobile.server import JarvisServer


class TestTrustServer(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_trust_server_{uuid.uuid4().hex}.db"
        self.secret = f"trust-secret-{uuid.uuid4().hex}"
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

    def _request(self, method, path, data=None, headers=None):
        payload = None if data is None else json.dumps(data).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=payload,
            method=method,
            headers=headers or {},
        )
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                body = response.read().decode("utf-8")
                return response.status, json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")
                return exc.code, json.loads(body) if body else {}
            finally:
                exc.close()

    def _owner_headers(self, user_agent="Axis Desktop Test"):
        return {
            "X-Jarvis-Token": self.secret,
            "User-Agent": user_agent,
        }

    def test_about_reports_axis_rebrand_and_new_navigation_sections(self):
        status, payload = self._request("GET", "/control/about", headers=self._owner_headers())

        self.assertEqual(status, 200)
        self.assertEqual(payload["app_name"], "Axis")
        self.assertEqual(payload["legacy_internal_name"], "Jarvis")
        self.assertIn("Axis Hub", payload["dashboard_sections"])
        self.assertIn("Security & Compliance", payload["dashboard_sections"])
        self.assertIn("Settings", payload["dashboard_sections"])
        self.assertIn("Profiles & Plans", payload["dashboard_sections"])

    def test_axis_foundation_endpoints_return_expected_shape(self):
        axis_status, axis_payload = self._request("GET", "/control/axis-hub", headers=self._owner_headers())
        security_status, security_payload = self._request("GET", "/control/security", headers=self._owner_headers())
        settings_status, settings_payload = self._request("GET", "/control/settings", headers=self._owner_headers())
        profiles_status, profiles_payload = self._request("GET", "/control/profiles", headers=self._owner_headers())
        help_status, help_payload = self._request("GET", "/control/help-center?page=axis-hub", headers=self._owner_headers())

        self.assertEqual(axis_status, 200)
        self.assertTrue(axis_payload["skills"])
        self.assertIn("training_visibility", axis_payload)

        self.assertEqual(security_status, 200)
        self.assertTrue(security_payload["cards"])
        self.assertIn("trust_overview", security_payload)

        self.assertEqual(settings_status, 200)
        self.assertIn("groups", settings_payload)
        self.assertTrue(settings_payload["can_manage"])

        self.assertEqual(profiles_status, 200)
        self.assertEqual(profiles_payload["active_plan"]["id"], "foundation_free")
        self.assertTrue(profiles_payload["can_manage"])

        self.assertEqual(help_status, 200)
        self.assertEqual(help_payload["assistant_name"], "Axis Help Center")
        self.assertEqual(help_payload["page_title"], "Axis Hub")
        self.assertIn("skills", help_payload["page_copy"].lower())

    def test_owner_can_update_axis_profile_and_settings(self):
        settings_status, settings_payload = self._request(
            "POST",
            "/control/settings/update",
            data={"key": "voice.reply_mode", "value": "text_only"},
            headers=self._owner_headers(),
        )
        profiles_status, profiles_payload = self._request(
            "POST",
            "/control/profiles/update",
            data={"display_name": "Developer Workspace", "profile_type": "developer", "plan_id": "builder"},
            headers=self._owner_headers(),
        )

        self.assertEqual(settings_status, 200)
        self.assertTrue(settings_payload["success"])
        voice_setting = next(
            item
            for items in settings_payload["snapshot"]["groups"].values()
            for item in items
            if item["key"] == "voice.reply_mode"
        )
        self.assertEqual(voice_setting["value"], "text_only")

        self.assertEqual(profiles_status, 200)
        self.assertTrue(profiles_payload["success"])
        self.assertEqual(profiles_payload["snapshot"]["active_profile"]["display_name"], "Developer Workspace")
        self.assertEqual(profiles_payload["snapshot"]["active_profile"]["profile_type"], "developer")
        self.assertEqual(profiles_payload["snapshot"]["active_plan"]["id"], "builder")

    def test_permissions_snapshot_is_read_only_for_mobile_owner(self):
        status, payload = self._request(
            "GET",
            "/control/permissions",
            headers=self._owner_headers("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)"),
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["session_class"], "mobile_owner")
        self.assertFalse(payload["can_manage"])
        self.assertIn("read-only", payload["session_guidance"])

    def test_mobile_owner_cannot_change_permissions(self):
        status, payload = self._request(
            "POST",
            "/control/permissions/goals.execute",
            data={"state": "disabled"},
            headers=self._owner_headers("Mozilla/5.0 (Android 15; Mobile)"),
        )

        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "desktop_owner_required")

    def test_goal_control_endpoint_enforces_disabled_permission(self):
        goal = self.brain.goal_engine.create_goal("Prepare a quick summary", title="Pause Gate")
        self.brain.goal_engine.plan_goal(goal["id"], brain=None)
        self.brain.permissions.set_permission_state("goals.control", "disabled")

        status, payload = self._request(
            "POST",
            f"/goals/{goal['id']}/pause",
            data={"reason": "Testing permission gate"},
            headers=self._owner_headers(),
        )

        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "permission_blocked")
        self.assertEqual(payload["permission_key"], "goals.control")

    def test_permission_request_can_be_approved_from_desktop_owner_session(self):
        self.brain.permissions.set_permission_state("goals.manage", "disabled")
        result = self.brain.chat_with_metadata("server-permission-request", "create a goal to prepare release notes")
        request_id = result["routing"]["context"]["permission_request"]["id"]

        status, payload = self._request(
            "POST",
            f"/control/permission-requests/{request_id}/approve",
            data={"note": "Approved from test"},
            headers=self._owner_headers(),
        )

        self.assertEqual(status, 200)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["decision"], "approved")
        self.assertEqual(payload["request"]["status"], "approved")
        self.assertEqual(payload["permission"]["current_state"], "enabled")


if __name__ == "__main__":
    unittest.main()
