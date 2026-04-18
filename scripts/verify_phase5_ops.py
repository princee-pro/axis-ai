"""
Phase 5 Operational Verification Test.
Extends device_bridge_self_test.py to verify new diagnostic endpoints and RBAC.
"""

import os
import sys
import json
import time
import http.client
import threading
import tempfile
import socket
import yaml
from unittest.mock import patch

# ── Path setup ────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from jarvis_ai.core.brain import Brain
from jarvis_ai.mobile.server import JarvisServer

# ── Helpers ───────────────────────────────────────────────────────────────────
PASS_COUNT = 0
FAIL_COUNT = 0

def check(label, condition, detail=""):
    global PASS_COUNT, FAIL_COUNT
    if condition:
        PASS_COUNT += 1
        print(f"  [PASS] {label}")
    else:
        FAIL_COUNT += 1
        print(f"  [FAIL] {label}")
        if detail:
            print(f"         Detail: {detail}")

def _free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def _get(conn, path, headers=None):
    conn.request("GET", path, headers=headers or {})
    r = conn.getresponse()
    body = json.loads(r.read().decode())
    return r.status, body

def _post(conn, path, payload=None, headers=None):
    body_bytes = json.dumps(payload or {}).encode()
    h = {"Content-Type": "application/json", "Content-Length": str(len(body_bytes))}
    h.update(headers or {})
    conn.request("POST", path, body=body_bytes, headers=h)
    r = conn.getresponse()
    body = json.loads(r.read().decode())
    return r.status, body

def run_test():
    print("=" * 60)
    print("  Jarvis Phase 5 — Operational Verification Suite")
    print("=" * 60)

    config_path = os.path.join(PROJECT_ROOT, 'jarvis_ai', 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    owner_token = os.environ.get('JARVIS_SECRET_TOKEN') or config.get('security_token', 'test_owner_token')
    owner_hdr = {"X-Jarvis-Token": owner_token}

    tmp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp_db.close()
    test_db = tmp_db.name

    port = _free_port()
    srv_cfg = {
        "remote_enabled": False,
        "behind_reverse_proxy": False,
        "require_https_forwarded_proto": True,
        "trusted_proxy_ips": [],
    }
    test_config = dict(config)
    test_config["memory"] = {"db_path": test_db}
    test_config["google"] = {"enabled": False}

    with patch('jarvis_ai.core.brain.GOOGLE_AVAILABLE', False):
        brain = Brain(test_config)
    
    server = JarvisServer(brain, port=port, host="127.0.0.1", server_config=srv_cfg)
    server.start()
    time.sleep(0.5)
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)

    try:
        # 1. /whoami as owner
        print("\n[1] /whoami as Owner")
        st, body = _get(conn, "/whoami", owner_hdr)
        check("Status is 200", st == 200, f"got {st}: {body}")
        check("auth_type is owner_token", body.get('auth_type') == 'owner_token')
        check("is_owner is True", body.get('is_owner') is True)

        # 2. /debug/config as owner
        print("\n[2] /debug/config as Owner")
        st, body = _get(conn, "/debug/config", owner_hdr)
        check("Status is 200", st == 200, f"got {st}: {body}")
        check("Contains db_path", 'db_path' in body, str(body))

        # 3. Create device and test /whoami
        print("\n[3] Device Registration and /whoami")
        st, body = _post(conn, "/pairing/code", {"role": "operator", "name": "OpsTestDevice"}, owner_hdr)
        p_code = body['code']
        st, body = _post(conn, "/pairing/register", {"code": p_code, "device_name": "OpsPhone"})
        device_id = body['device_id']
        device_token = body['device_token']
        dev_hdr = {"X-Device-Token": device_token}

        st, body = _get(conn, "/whoami", dev_hdr)
        check("Status is 200", st == 200)
        check("auth_type is device_token", body.get('auth_type') == 'device_token')
        check("is_owner is False", body.get('is_owner') is False)
        check("device_id matches", body.get('device_id') == device_id)
        check("device_role is operator", body.get('device_role') == 'operator')

        # 4. /debug/config restricted for device
        print("\n[4] /debug/config restricted for Device")
        st, body = _get(conn, "/debug/config", dev_hdr)
        check("Status is 403", st == 403)

        # 5. /activity/recent RBAC
        print("\n[5] /activity/recent RBAC")
        # Generate some activity
        _get(conn, "/health", owner_hdr)
        _get(conn, "/health", dev_hdr)
        
        # Owner views all
        print("  - Owner viewing all activity")
        st, body = _get(conn, "/activity/recent", owner_hdr)
        check("Status is 200", st == 200)
        check("Returns list", isinstance(body.get('activity'), list))
        
        # Device views own
        print("  - Device viewing own activity")
        st, body = _get(conn, "/activity/recent", dev_hdr)
        check("Status is 200", st == 200)
        # Verify all returned entries are for this device or lack device_id (if some system logs exist)
        activities = body.get('activity', [])
        all_own = all(a.get('device_id') == device_id or a.get('actor_type') == 'unauthorized' for a in activities)
        # Note: /whoami isn't logged in my implementation, but /health is.
        check("Only own device entries returned", all_own)

        # Device tries to view other device (using dummy device_id)
        print("  - Device unauthorized device_id filter")
        st, body = _get(conn, "/activity/recent?device_id=dummy-id", dev_hdr)
        check("Status is 403", st == 403)

        # 6. Revocation blocks /whoami
        print("\n[6] Revocation blocks /whoami")
        _post(conn, f"/devices/{device_id}/revoke", {}, owner_hdr)
        conn.close()
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        st, body = _get(conn, "/whoami", dev_hdr)
        check("Status is 403 after revocation", st == 403)

    finally:
        conn.close()
        server.stop()
        time.sleep(1)  # Give SQLite time to close
        try:
            if os.path.exists(test_db):
                os.unlink(test_db)
        except OSError as e:
            print(f"  [WARN] Could not delete temp DB: {e}")

    total = PASS_COUNT + FAIL_COUNT
    print("-" * 60)
    print(f"  Final Results: {PASS_COUNT}/{total} passed, {FAIL_COUNT} failed")
    print("-" * 60)
    sys.exit(0 if FAIL_COUNT == 0 else 1)

if __name__ == "__main__":
    run_test()
