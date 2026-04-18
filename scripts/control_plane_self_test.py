import sys
import os
import json
import logging
import uuid
import secrets

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain
from jarvis_ai.mobile.server import JarvisRequestHandler

def generate_mock_auth(role='admin', is_owner=True):
    if is_owner:
        return {"type": "owner", "id": None, "role": "admin"}
    else:
        return {"type": "device", "id": str(uuid.uuid4()), "role": role}

class MockHandler:
    def __init__(self, brain):
        self.brain = brain
        self.sent_status = None
        self.sent_data = None
        self.logs = []
        # Simulate base class attributes
        self.command = "GET"
        self.path = "/"
        self.client_address = ("127.0.0.1", 12345)
        self.headers = {"User-Agent": "pytest"}
        self._remote_enabled = False
        self._behind_reverse_proxy = False
        self._require_https_proto = False
    
    def _send_json(self, data, status=200):
        self.sent_status = status
        self.sent_data = data
        
    def _log_request(self, auth, status_code, error=None, summary=None):
        self.logs.append({"status": status_code, "error": error, "summary": summary})
        
    def _get_client_ip(self):
        return "127.0.0.1"
        
    # Borrow RBAC checker
    _check_permission = JarvisRequestHandler._check_permission

def setup_test_data(brain):
    eng = brain.goal_engine
    mem = brain.memory_engine
    
    # 1. Active Goal
    g1 = eng.create_goal("Test Goal Active", priority="high")
    eng.advance_goal(g1['id'], brain=brain) # move from draft to active usually, or generate plan
    
    # 2. Add an action and fake a step
    # We create raw pending action to simulate approval state
    action_id = brain.propose_action('web.plan.execute', {'objective': 'test', 'steps': []}, None)
    
    # Link to a fake step
    plan_id = str(uuid.uuid4())
    step_id = str(uuid.uuid4())
    mem._safe_db_execute(
        "INSERT INTO goal_plans (id, goal_id, status) VALUES (?, ?, ?)",
        (plan_id, g1['id'], 'active'), is_write=True
    )
    mem._safe_db_execute(
        "INSERT INTO goal_plan_steps (id, goal_id, plan_id, action_ref, title, status) VALUES (?, ?, ?, ?, ?, ?)",
        (step_id, g1['id'], plan_id, action_id, "Test Approval Step", "pending"), is_write=True
    )
    
    # 3. Blocked Goal
    g2 = eng.create_goal("Test Goal Blocked")
    # Force DB update for testing counts using API
    mem.update_goal_record(g2['id'], {'status': 'blocked'})
    mem.update_goal_record(g1['id'], {'status': 'active'})
    mem.log_goal_event(g2['id'], 'transition', 'active', 'blocked', reason='Needs missing info')
    
    # 4. Result Action
    action_res_id = str(uuid.uuid4())
    res_ref = "sess_" + secrets.token_hex(4)
    mem._safe_db_execute(
        "INSERT INTO pending_actions (id, type, status, result_ref, created_at) VALUES (?, ?, ?, ?, ?)",
        (action_res_id, 'web.plan.execute', 'completed', res_ref, "2024-01-01"), is_write=True
    )

    return g1['id'], g2['id'], action_id, action_res_id

def run_tests():
    print("Initializing Brain (Mock Mode)...")
    config = {
        'llm': {'provider': 'mock'},
        'google': {'enabled': False}, # Avoid strict auth load errors
        'security_token': 'test_secret'
    }
    brain = Brain(config=config)
    eng = brain.goal_engine
    
    # Setup
    print("Setting up mock database state...")
    g1_id, g2_id, pending_action_id, action_res_id = setup_test_data(brain)

    print("\n--- Running Control Plane Tests ---\n")
    
    # Test 10.1: Summary endpoint (Owner)
    print("--- Test 10.1: Control Summary (Owner) ---")
    handler = MockHandler(brain)
    auth_owner = generate_mock_auth(is_owner=True)
    # Borrow implementation directly from server definition into our mock class
    handler._handle_control_summary = JarvisRequestHandler._handle_control_summary.__get__(handler, MockHandler)
    handler._handle_control_summary(auth_owner)
    
    assert handler.sent_status == 200, f"Expected 200, got {handler.sent_status}: {handler.sent_data}"
    data = handler.sent_data
    
    assert 'counts' in data, "Missing counts"
    print("DEBUG counts:", data['counts'])
    
    val, rows = brain.memory_engine._safe_db_execute("SELECT status, count(*) FROM goals GROUP BY status")
    print("DEBUG DB GOALS:", rows)
    
    assert data['counts']['goals_total'] >= 2, "Total goals should be at least 2"
    assert data['counts']['goals_blocked'] >= 1, "Blocked goals should be 1"
    assert data['counts']['pending_actions'] >= 1, "Should have pending actions"
    
    assert 'recommended_next_actions' in data, "Missing recommendations"
    recs = data['recommended_next_actions']
    assert isinstance(recs, list), "Recommendations should be a list"
    assert len(recs) > 0, "Should have at least one recommendation"
    print("Recommendations returned:")
    for r in recs: print(f"  - {r}")
    
    assert 'recent_goal_events' in data, "Owner should see recent goal events"
    print("Test 10.1 Passed")


    # Test 10.2: Approvals Linkage
    print("\n--- Test 10.2: Approvals Linkage ---")
    handler._handle_control_approvals = JarvisRequestHandler._handle_control_approvals.__get__(handler, MockHandler)
    from urllib.parse import urlparse
    parsed = urlparse("/control/approvals?limit=5")
    handler._handle_control_approvals(auth_owner, parsed)
    
    assert handler.sent_status == 200
    approvals = handler.sent_data.get('pending_approvals', [])
    print("DEBUG approvals:", approvals)
    assert len(approvals) >= 1, "Expected at least 1 approval"
    target_app = next((a for a in approvals if a['action_id'] == pending_action_id), None)
    assert target_app is not None, "Did not find our test pending action"
    assert target_app['goal_id'] == g1_id, f"Goal linkage failed. Expected {g1_id}, got {target_app.get('goal_id')}"
    assert target_app['preview'] == "Test Approval Step", "Preview title did not match"
    print(f"Approval Linkage looks correct: Goal {target_app['goal_id'][:8]} -> Action {target_app['action_id'][:8]}")
    print("Test 10.2 Passed")


    # Test 10.3: Blocked Surface
    print("\n--- Test 10.3: Blocked Items ---")
    handler._handle_control_blocked = JarvisRequestHandler._handle_control_blocked.__get__(handler, MockHandler)
    handler._handle_control_blocked(auth_owner, parsed)
    
    assert handler.sent_status == 200
    blocked_items = handler.sent_data.get('blocked_items', [])
    assert len(blocked_items) >= 1, "Expected at least 1 blocked item"
    target_block = next((b for b in blocked_items if b['item_type'] == 'goal' and b['goal_id'] == g2_id), None)
    assert target_block is not None, "Did not find blocked goal"
    assert target_block['blocked_reason'] == "Needs missing info", "Reason mismatch"
    print(f"Found blocked item: {target_block['item_type']} ({target_block['goal_id'][:8]}) due to '{target_block['blocked_reason']}'")
    print("Test 10.3 Passed")


    # Test 10.4: Results Surface
    print("\n--- Test 10.4: Results Surface ---")
    handler._handle_control_results = JarvisRequestHandler._handle_control_results.__get__(handler, MockHandler)
    handler._handle_control_results(auth_owner, parsed)
    
    assert handler.sent_status == 200
    results = handler.sent_data.get('results', [])
    print("DEBUG results:", results)
    assert len(results) >= 1, "Expected at least 1 result"
    target_res = results[0] # The one we inserted directly
    assert target_res['result_ref'].startswith("sess_"), "Invalid result_ref"
    assert "summary" in target_res, "Missing safe summary"
    print(f"Found safe result ref: {target_res['result_ref']} summary: {target_res['summary']}")
    print("Test 10.4 Passed")


    # Test 10.5: RBAC Restrictions (Device Lite View)
    print("\n--- Test 10.5: RBAC Testing (Device Lite) ---")
    auth_device = generate_mock_auth(role='operator', is_owner=False)
    handler._handle_control_summary(auth_device)
    
    assert handler.sent_status == 200
    device_data = handler.sent_data
    assert "recent_goal_events" not in device_data, "Device token should not see recent raw events"
    assert "feature_flags" not in device_data, "Device token should not see feature flags"
    print("Device summary successfully redacted safe fields.")
    
    # Test strict RBAC deny
    auth_reader = generate_mock_auth(role='reader', is_owner=False)
    handler._handle_control_approvals(auth_reader, parsed)
    assert handler.sent_status == 403, "Reader should not be allowed to view pending approvals surface directly"
    print("RBAC strict deny (403) worked for reader trying to access operator level /approvals.")
    
    print("Test 10.5 Passed")

    print("\nALL PHASE 7.3 TESTS PASSED")

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    run_tests()
