import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_HTML = os.path.join(ROOT, 'jarvis_ai', 'ui', 'index.html')
APP_JS = os.path.join(ROOT, 'jarvis_ai', 'ui', 'static', 'app.js')


class TestDashboardTrustUI(unittest.TestCase):
    def test_axis_navigation_and_shell_sections_are_present(self):
        with open(INDEX_HTML, 'r', encoding='utf-8') as handle:
            html = handle.read()

        self.assertIn('Axis Operating System', html)
        self.assertIn('Axis Overview', html)
        self.assertIn('Axis Chat', html)
        self.assertIn('Approvals', html)
        self.assertIn('Axis Hub', html)
        self.assertIn('Capabilities &amp; Guide', html)
        self.assertIn('Permissions &amp; Access', html)
        self.assertIn('Security &amp; Compliance', html)
        self.assertIn('Profiles &amp; Plans', html)
        self.assertIn('data-page="axis-chat"', html)
        self.assertIn('id="page-axis-chat"', html)
        self.assertIn('id="page-goals"', html)
        self.assertIn('id="page-approvals"', html)
        self.assertIn('id="page-axis-hub"', html)
        self.assertIn('id="page-guide"', html)
        self.assertIn('id="page-permissions"', html)
        self.assertIn('id="page-security"', html)
        self.assertIn('id="page-settings"', html)
        self.assertIn('id="page-profiles"', html)
        self.assertIn('class="assistant-shell"', html)

    def test_goal_controls_and_assistant_shell_are_present(self):
        with open(INDEX_HTML, 'r', encoding='utf-8') as handle:
            html = handle.read()

        self.assertIn('id="assistant-thread"', html)
        self.assertIn('id="assistant-input"', html)
        self.assertIn('id="assistant-send-btn"', html)
        self.assertIn('id="new-goal-modal"', html)
        self.assertIn('id="edit-goal-modal"', html)
        self.assertIn('id="goal-submit-btn"', html)
        self.assertIn('id="edit-goal-submit-btn"', html)
        self.assertIn('id="page-title"', html)
        self.assertIn('class="status-bar"', html)

    def test_frontend_script_registers_axis_pages_profiles_settings_and_goal_edit_flow(self):
        with open(APP_JS, 'r', encoding='utf-8') as handle:
            script = handle.read()

        self.assertIn("'axis-chat':", script)
        self.assertIn("'axis-hub':", script)
        self.assertIn('permissions:', script)
        self.assertIn('guide:', script)
        self.assertIn('security:', script)
        self.assertIn('settings:', script)
        self.assertIn('profiles:', script)
        self.assertIn('function renderAxisChatPage()', script)
        self.assertIn('function renderAxisHubPage()', script)
        self.assertIn('function renderGuidePage()', script)
        self.assertIn('function renderPermissionsPage()', script)
        self.assertIn('function renderSecurityPage()', script)
        self.assertIn('function renderSettingsPage()', script)
        self.assertIn('function renderProfilesPage()', script)
        self.assertIn('async function saveGoalEdits()', script)
        self.assertIn('async function saveProfileDraft()', script)
        self.assertIn('async function handlePermissionChange(', script)
        self.assertIn('async function handlePermissionRequest(', script)
        self.assertIn('async function handleSettingUpdate(', script)

    def test_owner_facing_copy_uses_axis_branding_and_avoids_legacy_labels(self):
        with open(INDEX_HTML, 'r', encoding='utf-8') as handle:
            html = handle.read()
        with open(APP_JS, 'r', encoding='utf-8') as handle:
            script = handle.read()

        self.assertIn('Axis Assistant is standing by.', script)
        self.assertIn('Ask Axis', html)
        self.assertIn('Axis Operating System', html)
        self.assertNotIn('How Jarvis Works', script)
        self.assertNotIn('No Jarvis response yet.', script)
        self.assertNotIn('Jarvis-style', html)
        self.assertNotIn('function renderPermissions()', script)
        self.assertNotIn('function submitGoalEdit()', script)


if __name__ == '__main__':
    unittest.main()
