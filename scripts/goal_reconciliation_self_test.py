"""
Phase 7.1 — Goal Reconciliation Self-Test.

Tests the closed-loop reconciliation cycle:
  10.1 Approval-pending -> reconcile (status stays awaiting_approval)
  10.2 Approval approved + execution -> reconcile -> step completed + result_ref
  10.3 Rejection path -> goal blocked/failed with clear reason
  10.4 Safety-block path -> step/goal blocked with safety reason
  10.5 Resume flow -> next step chosen or summary says finished
  10.6 Events history -> goal_events persistsed and retrievable

All tests are local-only. No internet, no real browser.
"""
import os
import sys
import json
import time
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_TOKEN = "TEST_INTEGRATION_TOKEN_99"
os.environ["JARVIS_SECRET_TOKEN"] = TEST_TOKEN

from jarvis_ai.core.brain import Brain
from jarvis_ai.mobile.server import JarvisServer

DB_PATH = "test_reconcile.db"

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _http(method, path, base="http://localhost:8002", **kwargs):
    headers = {"X-Jarvis-Token": TEST_TOKEN, "Content-Type": "application/json"}
    url = base + path
    return getattr(requests, method)(url, headers=headers, **kwargs)


def _force_action_status(memory_engine, action_id, new_status, result_ref=None,
                          notes_json=None):
    """Directly update a pending_action row for test simulation."""
    updates = {'status': new_status}
    if result_ref:
        updates['result_ref'] = result_ref
    if notes_json is not None:
        updates['notes'] = json.dumps(notes_json)
    # Use internal helper to avoid lock issues
    memory_engine._safe_db_execute(
        "UPDATE pending_actions SET status=?, result_ref=?, notes=? WHERE id=?",
        (new_status, result_ref, json.dumps(notes_json) if notes_json else None, action_id),
        is_write=True
    )


def _create_web_goal_via_api(base, title, objective):
    """Helper: create + plan a web goal via API."""
    r = _http('post', '/goals', base=base, json={
        'title': title,
        'objective': objective + ' website',   # ensure web keyword
        'priority': 'normal',
        'requires_approval': True,
    })
    assert r.status_code == 200, f"Create failed: {r.text}"
    gid = r.json()['goal']['id']

    r2 = _http('post', f'/goals/{gid}/plan', base=base)
    assert r2.status_code == 200, f"Plan failed: {r2.text}"

    return gid


# ──────────────────────────────────────────────────────────────────────────────
def run_tests():
    print("\n--- PHASE 7.1: GOAL RECONCILIATION SELF-TEST ---")

    # Fresh DB
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    config = {
        'memory': {'db_path': DB_PATH},
        'security_token': TEST_TOKEN,
        'server': {'remote_enabled': False},
        'google': {'enabled': False},
    }
    brain = Brain(config)
    mem = brain.memory_engine

    print("\n[INIT] Launching test server on :8002 ...")
    server = JarvisServer(brain, port=8002, server_config=config.get('server'))
    server.start()
    time.sleep(1)
    BASE = "http://localhost:8002"

    try:
        # ── Test 10.1: Pending → reconcile → stays awaiting_approval ───────────
        print("\n[10.1] Pending → reconcile → awaiting_approval retained...")
        gid1 = _create_web_goal_via_api(BASE, "Archive Docs", "archive docs from")

        # Advance creates pending action
        adv = _http('post', f'/goals/{gid1}/advance', base=BASE)
        assert adv.status_code == 200, f"Advance failed: {adv.text}"

        # Reconcile immediately (nothing has changed on the action)
        rec = _http('post', f'/goals/{gid1}/reconcile', base=BASE)
        assert rec.status_code == 200, f"Reconcile failed: {rec.text}"
        rj = rec.json()
        assert rj['new_status'] == 'awaiting_approval', f"Expected awaiting_approval, got: {rj}"
        assert len(rj['waiting_approvals']) > 0, "Expected pending action listed"
        print(f"  ✅ Status still awaiting_approval, action_ref={rj['waiting_approvals'][0]}")

        # ── Test 10.2: Execution result → reconcile → step completed + result_ref
        print("\n[10.2] Execution result → reconcile → step completed ...")
        action_id = rj['waiting_approvals'][0]

        # Simulate: action was executed with a success result
        _force_action_status(mem, action_id, 'executed',
                              result_ref='session-abc123',
                              notes_json={'status': 'success', 'session_id': 'session-abc123'})

        rec2 = _http('post', f'/goals/{gid1}/reconcile', base=BASE)
        assert rec2.status_code == 200, f"Reconcile2 failed: {rec2.text}"
        rj2 = rec2.json()
        assert rj2['new_status'] == 'completed', f"Expected completed, got: {rj2}"
        assert rj2['steps_completed'] == 1, f"Expected 1 step completed: {rj2}"

        # Summary must have result_ref
        summary = _http('get', f'/goals/{gid1}/summary', base=BASE)
        assert summary.status_code == 200
        sj = summary.json()
        assert sj['status'] == 'completed', f"Summary status wrong: {sj}"
        assert sj['result_refs'], "Expected result_refs populated"
        print(f"  ✅ Goal completed, result_ref={sj['result_refs'][0]}")

        # ── Test 10.3: Rejection path → goal blocked ─────────────────────────
        print("\n[10.3] Rejection → goal blocked with clear reason ...")
        gid3 = _create_web_goal_via_api(BASE, "Post Update", "post update to")
        _http('post', f'/goals/{gid3}/advance', base=BASE)

        # Get the step's action_ref
        ctx = _http('get', f'/goals/{gid3}/summary', base=BASE).json()
        waiting = ctx.get('waiting_approvals', [])
        assert waiting, "Expected a waiting approval for test 10.3"
        action_id3 = waiting[0]['action_ref']

        # Simulate rejection
        _force_action_status(mem, action_id3, 'rejected')

        rec3 = _http('post', f'/goals/{gid3}/reconcile', base=BASE)
        rj3 = rec3.json()
        assert rj3['new_status'] in ('blocked', 'failed'), f"Expected blocked/failed, got: {rj3}"
        assert rj3['steps_blocked'] > 0, "Expected blocked step count"
        sum3 = _http('get', f'/goals/{gid3}/summary', base=BASE).json()
        assert sum3['status'] in ('blocked', 'failed'), f"Summary status wrong: {sum3}"
        assert sum3.get('blocked_reason') or sum3.get('current_step', {}) and sum3['current_step'].get('blocked_reason'), "Expected blocked_reason surfaced"
        print(f"  ✅ Goal moved to {rj3['new_status']}, blocked_reason recorded")

        # ── Test 10.4: Safety block → step/goal blocked ───────────────────────
        print("\n[10.4] Safety block (login_detected) → goal blocked ...")
        gid4 = _create_web_goal_via_api(BASE, "Scrape Data", "scrape data from")
        _http('post', f'/goals/{gid4}/advance', base=BASE)

        ctx4 = _http('get', f'/goals/{gid4}/summary', base=BASE).json()
        waiting4 = ctx4.get('waiting_approvals', [])
        assert waiting4, "Expected waiting approval for test 10.4"
        aref4 = waiting4[0]['action_ref']

        # Simulate: action executed but blocked by safety gate
        _force_action_status(mem, aref4, 'executed',
                              notes_json={'status': 'blocked', 'block_reason': 'login_detected'})

        rec4 = _http('post', f'/goals/{gid4}/reconcile', base=BASE)
        rj4 = rec4.json()
        assert rj4['new_status'] in ('blocked', 'failed'), f"Expected blocked, got: {rj4}"
        sum4 = _http('get', f'/goals/{gid4}/summary', base=BASE).json()
        step4 = sum4.get('current_step') or {}
        assert 'login' in (step4.get('blocked_reason') or '').lower() or \
               'login' in (sum4.get('blocked_reason') or '').lower() or \
               rj4['steps_blocked'] > 0, f"Expected safety block reason: {sum4}"
        print(f"  ✅ Goal blocked by safety gate: {step4.get('blocked_reason') or 'safety_gate'}")

        # ── Test 10.5: Resume flow ─────────────────────────────────────────────
        print("\n[10.5] Resume flow → next step chosen or finished ...")

        # Use gid1 (already completed). Resume should return completed.
        res5 = _http('post', f'/goals/{gid1}/resume', base=BASE)
        assert res5.status_code == 200, f"Resume failed: {res5.text}"
        rj5 = res5.json()
        # Either completed or can_resume=False
        assert rj5['status'] == 'completed' or not rj5.get('can_resume', True), \
            f"Expected completed or non-resumable: {rj5}"
        print(f"  ✅ Resume result: status={rj5['status']}, can_resume={rj5.get('can_resume')}")

        # ── Test 10.6: Events history ──────────────────────────────────────────
        print("\n[10.6] Events history → goal_events populated ...")
        ev_resp = _http('get', f'/goals/{gid1}/events', base=BASE)
        assert ev_resp.status_code == 200, f"Events failed: {ev_resp.text}"
        evj = ev_resp.json()
        assert evj['count'] > 0, "Expected at least 1 event"
        event_types = {e['event_type'] for e in evj['events']}
        assert 'goal_created' in event_types, f"Expected goal_created in events: {event_types}"
        assert 'reconciliation_updated' in event_types or 'step_completed' in event_types, \
            f"Expected transition events: {event_types}"
        print(f"  ✅ {evj['count']} events found, types={sorted(event_types)}")

        # ── Summary check ──────────────────────────────────────────────────────
        print("\n===============================================")
        print("✅ ALL PHASE 7.1 RECONCILIATION TESTS PASSED")
        print("===============================================")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        server.stop()
        print("\nServer stopped.")
        try:
            os.remove(DB_PATH)
        except Exception:
            pass


if __name__ == "__main__":
    run_tests()
