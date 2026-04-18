import gc
import os
import re
import sys
import time
import unittest
import urllib.request
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain
from jarvis_ai.mobile.server import JarvisServer

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:  # pragma: no cover
    expect = None
    sync_playwright = None


class TestDashboardBrowserWorkflows(unittest.TestCase):
    def setUp(self):
        if sync_playwright is None:
            self.skipTest('Playwright is not available in this environment.')

        self.db_path = f"test_dashboard_browser_{uuid.uuid4().hex}.db"
        self.secret = f"browser-secret-{uuid.uuid4().hex}"
        self.previous_secret = os.environ.get('JARVIS_SECRET_TOKEN')
        os.environ['JARVIS_SECRET_TOKEN'] = self.secret
        self.brain = Brain({
            'llm': {'provider': 'mock'},
            'memory': {'db_path': self.db_path},
            'google': {'enabled': False},
            'security_token': self.secret,
            'capabilities': {'web_automation': {'enabled': True}},
        })
        self.server = JarvisServer(self.brain, port=0, host='127.0.0.1', server_config={})
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
        self.context = self.browser.new_context()
        self.context.route(
            'https://cdnjs.cloudflare.com/ajax/libs/three.js/**',
            lambda route: route.fulfill(
                status=200,
                content_type='application/javascript',
                body='window.THREE = window.THREE || {};',
            ),
        )
        self.page = self.context.new_page()
        self.page.set_default_timeout(15000)
        self.page.on('dialog', lambda dialog: dialog.accept())

    def tearDown(self):
        for attr_name in ('page', 'context', 'browser'):
            target = getattr(self, attr_name, None)
            if target:
                try:
                    target.close()
                except Exception:
                    pass
                setattr(self, attr_name, None)
        if getattr(self, 'playwright_manager', None):
            try:
                self.playwright_manager.stop()
            except Exception:
                pass
            self.playwright_manager = None
        if getattr(self, 'server', None):
            self.server.stop()
            self.server = None
        if getattr(self, 'brain', None):
            self.brain.close()
            self.brain = None
        if self.previous_secret is None:
            os.environ.pop('JARVIS_SECRET_TOKEN', None)
        else:
            os.environ['JARVIS_SECRET_TOKEN'] = self.previous_secret
        gc.collect()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def login_owner(self):
        self.page.goto(f"{self.base_url}/ui", wait_until='domcontentloaded')
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
        if not self.page.locator('#app').is_visible():
            self.page.locator('#auth-token').fill(self.secret)
            self.page.locator('#login-btn').click(force=True)
            self.page.wait_for_function(
                "() => document.querySelector('#app') && !document.querySelector('#app').classList.contains('hidden')",
                timeout=15000,
            )
        expect(self.page.locator('#page-title')).to_have_text('Axis Overview')

    def refresh_owner_shell(self):
        self.page.reload(wait_until='domcontentloaded')
        self.page.wait_for_function(
            """() => {
                const isVisible = (node) => {
                    if (!node || node.classList.contains('hidden')) {
                        return false;
                    }
                    const style = window.getComputedStyle(node);
                    return style.display !== 'none'
                        && style.visibility !== 'hidden'
                        && node.getClientRects().length > 0;
                };

                const app = document.querySelector('#app');
                const overlay = document.querySelector('#auth-overlay');
                const authError = document.querySelector('#auth-error');
                const hasStoredAuth = Boolean(window.sessionStorage.getItem('jarvis_auth'));

                return isVisible(app) || (isVisible(overlay) && (!hasStoredAuth || isVisible(authError)));
            }""",
            timeout=15000,
        )
        if not self.page.locator('#app').is_visible():
            expect(self.page.locator('#auth-token')).to_be_visible()
            expect(self.page.locator('#login-btn')).to_be_visible()
            self.page.locator('#auth-token').fill(self.secret)
            self.page.locator('#login-btn').click()
            self.page.wait_for_function(
                "() => document.querySelector('#app') && !document.querySelector('#app').classList.contains('hidden')",
                timeout=15000,
            )
        expect(self.page.locator('#page-title')).to_have_text('Axis Overview')

    def open_page(self, page_id):
        self.page.locator(f'.sidebar .nav-btn[data-page="{page_id}"]').click()
        self.page.wait_for_function(
            "(pageId) => document.querySelector(`#page-${pageId}`) && !document.querySelector(`#page-${pageId}`).classList.contains('hidden')",
            arg=page_id,
            timeout=15000,
        )
        expect(self.page.locator(f'#page-{page_id}')).to_be_visible()

    def create_goal_from_dashboard(self, title, objective, priority='high'):
        self.open_page('goals')
        self.page.locator('#new-goal-btn').click()
        expect(self.page.locator('#new-goal-modal')).to_be_visible()
        self.page.locator('#goal-title').fill(title)
        self.page.locator('#goal-objective').fill(objective)
        self.page.locator('#goal-priority').select_option(priority)
        self.page.locator('#goal-submit-btn').click()
        expect(self.page.locator('#page-goals .detail-title')).to_have_text(title)
        expect(self.page.locator('#page-goals .detail-copy')).to_contain_text(objective)

    def status_pill(self):
        return self.page.locator('#page-goals .detail-header .status-pill').first

    def permission_card(self, permission_key):
        return self.page.locator(f'[data-permission-key-card="{permission_key}"]').first

    def permission_request_card(self, permission_key):
        return self.page.locator(f'[data-permission-request-key="{permission_key}"]').first

    def approval_card(self, title_text):
        return self.page.locator('#page-approvals [data-approval-card]').filter(has_text=title_text).first

    def seed_manual_approval_goal(self, title, objective, extra_action_details=None):
        goal_id = f"goal-{uuid.uuid4().hex[:12]}"
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        step_id = f"step-{uuid.uuid4().hex[:8]}"
        action_id = f"action-{uuid.uuid4().hex[:8]}"
        now = time.strftime('%Y-%m-%dT%H:%M:%S')

        self.brain.memory_engine.create_goal_record({
            'id': goal_id,
            'title': title,
            'objective': objective,
            'status': 'awaiting_approval',
            'priority': 'high',
            'created_at': now,
            'updated_at': now,
            'requires_approval': True,
            'current_step_index': 0,
            'summary': objective,
        })
        self.brain.memory_engine.create_plan_record({
            'id': plan_id,
            'goal_id': goal_id,
            'status': 'active',
            'created_by': 'browser_test',
            'created_at': now,
            'planner_type': 'browser_test',
            'planner_provider': 'fixture',
            'planner_warnings': None,
            'raw_plan_hash': None,
        })
        self.brain.memory_engine.create_pending_action(
            action_id,
            'manual.review.complete',
            {
                'title': title,
                'description': objective,
                'goal_id': goal_id,
                'step_id': step_id,
                'capability_type': 'manual',
                **(extra_action_details or {}),
            },
            created_by='browser_test',
        )
        self.brain.memory_engine.create_plan_step_record({
            'id': step_id,
            'goal_id': goal_id,
            'plan_id': plan_id,
            'step_index': 0,
            'title': 'Owner review',
            'description': objective,
            'capability_type': 'manual',
            'status': 'awaiting_approval',
            'requires_approval': True,
            'action_ref': action_id,
            'result_ref': None,
            'error': None,
        })
        self.brain.memory_engine.log_goal_event(
            goal_id,
            'goal_planned',
            from_status='draft',
            to_status='awaiting_approval',
            plan_id=plan_id,
            step_id=step_id,
            action_ref=action_id,
            reason='Seeded browser approval fixture',
        )

    def seed_permission_blocked_goal(self, title, objective):
        goal = self.brain.goal_engine.create_goal(objective, title=title, priority='high')
        blocked_reason = 'Web automation is disabled for this Axis session.'
        self.brain.memory_engine.update_goal_record(goal['id'], {
            'status': 'blocked',
            'last_error': blocked_reason,
        })
        self.brain.memory_engine.log_goal_event(
            goal['id'],
            'goal_blocked',
            from_status='draft',
            to_status='blocked',
            reason=blocked_reason,
        )
        self.brain.memory_engine.create_permission_request(
            'browser.web_automation',
            'Web automation',
            'Axis needs web automation access to continue this goal.',
            goal_id=goal['id'],
            goal_title=title,
            action_label='Execute Web Automation',
            source='goal_step',
        )

    def test_axis_shell_navigation_help_center_profiles_and_settings_persist(self):
        self.login_owner()
        expect(self.page.locator('.sidebar')).to_contain_text('Axis Overview')
        expect(self.page.locator('.sidebar')).to_contain_text('Axis Chat')
        expect(self.page.locator('.sidebar')).to_contain_text('Axis Hub')
        expect(self.page.locator('.sidebar')).to_contain_text('Security & Compliance')
        expect(self.page.locator('.sidebar')).to_contain_text('Settings')
        expect(self.page.locator('.sidebar')).to_contain_text('Profiles & Plans')

        self.open_page('axis-hub')
        expect(self.page.locator('#page-title')).to_have_text('Axis Hub')
        expect(self.page.locator('#page-axis-hub')).to_contain_text('Ecosystem activity')

        self.open_page('security')
        expect(self.page.locator('#page-title')).to_have_text('Security & Compliance')
        expect(self.page.locator('#page-security')).to_contain_text('Trust overview')

        self.open_page('settings')
        expect(self.page.locator('#page-title')).to_have_text('Settings')
        expect(self.page.locator('#page-settings')).to_contain_text('Voice Preferences')

        self.open_page('profiles')
        expect(self.page.locator('#page-title')).to_have_text('Profiles & Plans')
        expect(self.page.locator('#page-profiles')).to_contain_text('Active workspace identity')
        expect(self.page.locator('#page-profiles')).to_contain_text('Feature matrix')

    def test_owner_can_update_profiles_plans_and_settings_in_browser(self):
        self.login_owner()
        self.open_page('profiles')
        self.page.locator('#profile-display-name').fill('Developer Workspace')
        self.page.locator('[data-select-profile="student"]').click()
        self.page.locator('[data-select-plan="builder"]').click()
        self.page.locator('#save-profile-btn').click()
        expect(self.page.locator('#profile-display-name')).to_have_value('Developer Workspace')
        expect(self.page.locator('#page-profiles .profile-card.is-selected')).to_contain_text('Student')
        expect(self.page.locator('#page-profiles .plan-card.is-selected')).to_contain_text('Builder')
        expect(self.page.locator('#session-name')).to_have_text('Student')
        expect(self.page.locator('#topbar-plan')).to_have_text('Plan: Builder')

        self.open_page('settings')
        voice_toggle = self.page.locator('input[data-setting-key="voice.prefer_browser_speech"]')
        expect(voice_toggle).to_be_checked()
        voice_toggle.click()
        expect(self.page.locator('input[data-setting-key="voice.prefer_browser_speech"]')).not_to_be_checked()

    def test_owner_can_run_goal_lifecycle_controls_in_browser(self):
        self.login_owner()
        self.create_goal_from_dashboard('Workflow Goal', 'Prepare a project summary')

        self.page.locator('[data-goal-action="edit"]').click()
        expect(self.page.locator('#edit-goal-modal')).to_be_visible()
        self.page.locator('#edit-goal-title').fill('Workflow Goal Revised')
        self.page.locator('#edit-goal-objective').fill('Prepare a revised project summary')
        self.page.locator('#edit-goal-submit-btn').click()
        expect(self.page.locator('#page-goals .detail-title')).to_have_text('Workflow Goal Revised')
        expect(self.page.locator('#page-goals .detail-copy')).to_contain_text('Prepare a revised project summary')

        self.page.locator('[data-goal-action="plan"]').click()
        expect(self.status_pill()).to_have_text(re.compile('planned', re.IGNORECASE))

        self.page.locator('[data-goal-action="pause"]').click()
        expect(self.status_pill()).to_have_text(re.compile('paused', re.IGNORECASE))

        self.page.locator('[data-goal-action="resume"]').click()
        expect(self.status_pill()).to_have_text(re.compile(r'awaiting\s+approval', re.IGNORECASE))
        expect(self.page.locator('#page-goals .detail-metric').filter(has_text='Waiting approvals')).to_contain_text('1')

        self.page.locator('[data-goal-action="stop"]').click()
        expect(self.status_pill()).to_have_text(re.compile('stopped', re.IGNORECASE), timeout=15000)

        self.page.locator('[data-goal-action="replan"]').click()
        expect(self.status_pill()).to_have_text(re.compile('planned', re.IGNORECASE), timeout=15000)
        expect(self.page.locator('#page-goals .step-card').first).to_be_visible()

    def test_permission_blocked_goal_flow_updates_through_trust_center(self):
        self.login_owner()
        self.open_page('permissions')
        self.permission_card('browser.web_automation').locator('select[data-permission-key="browser.web_automation"]').select_option('disabled')
        expect(self.permission_card('browser.web_automation')).to_contain_text('Disabled')

        self.create_goal_from_dashboard('Website Audit', 'Open a website and inspect the pricing page')
        self.page.locator('[data-goal-action="plan"]').click()
        expect(self.status_pill()).to_have_text(re.compile('planned', re.IGNORECASE))

        self.page.locator('[data-goal-action="resume"]').click()
        expect(self.status_pill()).to_have_text(re.compile('blocked', re.IGNORECASE), timeout=15000)
        expect(self.page.locator('#page-goals')).to_contain_text('Web automation')

        self.open_page('permissions')
        request_card = self.permission_request_card('browser.web_automation')
        expect(request_card).to_contain_text('Web automation')
        request_card.locator('[data-request-action="approve"]').click()
        expect(self.permission_card('browser.web_automation')).to_contain_text('Active')

    def test_command_routing_shows_permission_link_and_recovers_after_approval(self):
        self.login_owner()
        self.open_page('permissions')
        self.permission_card('goals.manage').locator('select[data-permission-key="goals.manage"]').select_option('disabled')
        expect(self.permission_card('goals.manage')).to_contain_text('Disabled')

        self.open_page('axis-chat')
        self.page.locator('#assistant-input').fill('create a goal to review the release notes')
        self.page.locator('#assistant-send-btn').click()
        expect(self.page.locator('#assistant-thread')).to_contain_text('Goal management is currently disabled')
        expect(self.page.locator('#assistant-thread')).to_contain_text('Open Permissions & Access')
        self.open_page('permissions')
        expect(self.page.locator('#page-permissions')).to_be_visible()
        self.permission_card('goals.manage').locator('select[data-permission-key="goals.manage"]').select_option('enabled')
        expect(self.permission_card('goals.manage')).to_contain_text('Active')

        self.open_page('axis-chat')
        self.page.locator('#assistant-input').fill('create a goal to review the release notes')
        self.page.locator('#assistant-send-btn').click()
        expect(self.page.locator('#assistant-thread')).to_contain_text('created a new draft goal')
        self.refresh_owner_shell()
        self.open_page('goals')
        expect(self.page.locator('#page-goals')).to_be_visible()
        expect(self.page.locator('#page-goals .detail-title')).to_have_text('Review The Release Notes')

    def test_capabilities_guide_renders_realism_badges_and_filtering(self):
        self.login_owner()
        self.open_page('guide')
        expect(self.page.locator('#guide-filter-input')).to_be_visible()
        expect(self.page.locator('#page-guide')).to_contain_text('Capability guide')
        expect(self.page.locator('#page-guide')).to_contain_text('Workflow guide')
        self.page.locator('#guide-filter-input').fill('voice')
        expect(self.page.locator('#page-guide')).to_contain_text('Voice')
        expect(self.page.locator('#page-guide')).to_contain_text(re.compile('mocked|partial|live', re.IGNORECASE))

    def test_overview_surfaces_trust_requests_and_permission_blocked_goals(self):
        self.brain.permissions.set_permission_state('browser.web_automation', 'disabled')
        self.seed_permission_blocked_goal('Overview Trust Goal', 'Open a website and inspect the pricing page')
        self.login_owner()
        self.open_page('overview')
        overview = self.page.locator('#page-overview')
        expect(overview).to_contain_text('Trust and attention points')
        expect(overview).to_contain_text('Review permissions')
        expect(overview).to_contain_text('Overview Trust Goal')

        overview.get_by_role('button', name='Review permissions').first.click()
        expect(self.page.locator('#page-permissions')).to_be_visible()
        expect(self.permission_request_card('browser.web_automation')).to_be_visible()

        self.open_page('overview')
        overview.get_by_role('button', name='Inspect goal').first.click()
        expect(self.page.locator('#page-goals')).to_be_visible()
        expect(self.page.locator('#page-goals .detail-title')).to_have_text('Overview Trust Goal')

    def test_owner_can_review_approve_execute_and_deny_approvals_in_browser(self):
        self.seed_manual_approval_goal(
            'Executable Approval Goal',
            'Prepare the project summary for review',
            extra_action_details={'changes': {'scope': 'summary', 'owner': 'browser test'}},
        )
        self.seed_manual_approval_goal('Denied Approval Goal', 'Prepare a flow that should be denied')
        self.login_owner()

        self.open_page('approvals')
        executable_card = self.approval_card('Executable Approval Goal')
        expect(executable_card).to_contain_text(re.compile('pending', re.IGNORECASE))
        executable_card.locator('[data-approval-action="approve"]').click()
        expect(executable_card).to_contain_text(re.compile('approved', re.IGNORECASE))
        executable_card.locator('[data-approval-action="execute"]').click()
        executable_card.get_by_role('button', name='Open Goal').click()
        expect(self.page.locator('#page-goals')).to_be_visible()
        expect(self.page.locator('#page-goals .detail-title')).to_have_text('Executable Approval Goal')
        expect(self.status_pill()).to_have_text(re.compile('completed', re.IGNORECASE))

        self.open_page('approvals')
        denied_card = self.approval_card('Denied Approval Goal')
        expect(denied_card).to_contain_text(re.compile('pending', re.IGNORECASE))
        denied_card.locator('[data-approval-action="reject"]').click()
        self.refresh_owner_shell()
        self.open_page('goals')
        expect(self.page.locator('#page-goals')).to_be_visible()
        expect(self.page.locator('#page-goals .detail-title')).to_have_text('Denied Approval Goal')
        expect(self.status_pill()).to_have_text(re.compile('blocked', re.IGNORECASE))


if __name__ == '__main__':
    unittest.main()
