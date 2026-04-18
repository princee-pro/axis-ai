"""
Phase 5 Device Bridge Self-Test.

Self-contained: starts an in-process Jarvis server on a random high port,
exercises the full pairing + RBAC + revocation flow, then shuts down.

Requirements:
  - No Google OAuth tokens required
  - No external server process needed
  - Reads owner token from settings.yaml (does NOT keep it in source)
  - Exits 0 on full pass, 1 on any failure
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
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))


def _free_port():
    """Find an available TCP port."""
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
    h = {"Content-Type": "application/json",
         "Content-Length": str(len(body_bytes))}
    h.update(headers or {})
    conn.request("POST", path, body=body_bytes, headers=h)
    r = conn.getresponse()
    body = json.loads(r.read().decode())
    return r.status, body


# ── Main test ─────────────────────────────────────────────────────────────────
def run_test():
    print("=" * 60)
    print("  Jarvis Phase 5 — Device Bridge Self-Test")
    print("=" * 60)

    # ── Load config / owner token ─────────────────────────────────────────
    config_path = os.path.join(PROJECT_ROOT, 'jarvis_ai', 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    owner_token = (
        os.environ.get('JARVIS_SECRET_TOKEN')
        or config.get('security_token', '')
    )
    if not owner_token:
        print("[ERROR] No owner token found. Set JARVIS_SECRET_TOKEN or security_token in settings.yaml")
        sys.exit(1)

    owner_hdr = {"X-Jarvis-Token": owner_token}

    # ── Spin up in-process server with isolated temp DB ───────────────────
    tmp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp_db.close()
    test_db = tmp_db.name

    port = _free_port()
    srv_cfg = {
        "remote_enabled":              False,
        "behind_reverse_proxy":        False,
        "require_https_forwarded_proto": True,
        "trusted_proxy_ips":           [],
    }
    test_config = dict(config)
    test_config["memory"] = {"db_path": test_db}
    # Disable Google so Brain init doesn't trigger OAuth prompt
    test_config["google"] = {"client_file": "__nonexistent__"}

    brain_module_path = 'jarvis_ai.core.brain.GOOGLE_AVAILABLE'
    from unittest.mock import patch
    with patch(brain_module_path, False):
        brain = Brain(test_config)
    server = JarvisServer(brain, port=port, host="127.0.0.1", server_config=srv_cfg)
    server.start()

    # Give the server a moment to bind
    time.sleep(0.4)
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)

    print(f"\n[0] Server started on 127.0.0.1:{port}")

    try:
        # ── [1] Health check as owner ─────────────────────────────────────
        print("\n[1] Owner Health Check")
        st, body = _get(conn, "/health", owner_hdr)
        check("Owner can GET /health (200)", st == 200, f"got {st}: {body}")

        # ── [2] Create pairing code ───────────────────────────────────────
        print("\n[2] Create Pairing Code (reader role)")
        st, body = _post(conn, "/pairing/code",
                         {"role": "reader", "name": "SelfTestDevice"},
                         owner_hdr)
        check("Owner can create pairing code (200)", st == 200, f"got {st}: {body}")
        check("Response includes 'code'",      'code'       in body, str(body))
        check("Response includes 'expires_at'", 'expires_at' in body, str(body))
        pairing_code = body.get('code', '')

        # ── [3] Register device (public endpoint) ─────────────────────────
        print("\n[3] Register Device via Pairing Code")
        st, body = _post(conn, "/pairing/register", {
            "code":           pairing_code,
            "device_name":    "SelfTest Phone",
            "requested_role": "reader",
        })
        check("Device registration returns 200", st == 200, f"got {st}: {body}")
        check("Response includes device_id",    'device_id'    in body, str(body))
        check("Response includes device_token", 'device_token' in body, str(body))
        device_id    = body.get('device_id', '')
        device_token = body.get('device_token', '')
        device_role  = body.get('role', '')
        check("Device role is 'reader'", device_role == 'reader', f"got={device_role}")

        dev_hdr = {"X-Device-Token": device_token}

        # ── [4] Reader endpoint ACCESS (should pass) ──────────────────────
        print("\n[4] Reader Role — Allowed Endpoint")
        st, body = _get(conn, "/health", dev_hdr)
        check("Reader device can GET /health (200)", st == 200, f"got {st}: {body}")

        st, body = _get(conn, "/actions", dev_hdr)
        check("Reader device can GET /actions (200)", st == 200, f"got {st}: {body}")

        # ── [5] Executor endpoint BLOCKED for reader (should fail) ────────
        print("\n[5] Executor Endpoint — Must Be Blocked for Reader")
        st, body = _post(conn, "/actions/fake-action-id/execute", {}, dev_hdr)
        check("Executor endpoint blocked for reader (403)", st == 403,
              f"got {st}: {body}")

        # ── [6] Admin endpoint BLOCKED for device ─────────────────────────
        print("\n[6] Owner-Only Endpoint — Must Be Blocked for Device")
        st, body = _get(conn, "/devices", dev_hdr)
        check("GET /devices blocked for device (403)", st == 403, f"got {st}: {body}")

        # ── [7] Revoke device ─────────────────────────────────────────────
        print("\n[7] Revoke Device")
        st, body = _post(conn, f"/devices/{device_id}/revoke", {}, owner_hdr)
        check("Owner can revoke device (200)", st == 200, f"got {st}: {body}")

        # ── [8] Revoked token rejected ────────────────────────────────────
        print("\n[8] Revoked Token Rejected")
        # Need a new connection because the old connection may be cached
        conn.close()
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        st, body = _get(conn, "/health", dev_hdr)
        check("Revoked device token is rejected (403)", st == 403, f"got {st}: {body}")

        # ── [9] Pairing code is single-use ────────────────────────────────
        print("\n[9] Pairing Code Single-Use")
        # Re-use the same code (should fail)
        conn.close()
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        st, body = _post(conn, "/pairing/register", {
            "code":        pairing_code,
            "device_name": "ReusedCode",
        })
        check("Pairing code cannot be reused (403)", st == 403, f"got {st}: {body}")

        # ── [10] Rate limit on pairing/register ───────────────────────────
        print("\n[10] Rate Limit on /pairing/register (synthetic)")
        # Hit endpoint 11 times with a fake code to trigger the limiter
        # (from the same IP, rapid fire)
        conn.close()
        rate_hit = False
        for i in range(12):
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            s, _ = _post(c, "/pairing/register", {"code": "XXXXXXXX"})
            c.close()
            if s == 429:
                rate_hit = True
                break
        check("Rate limiter fires 429 after excess attempts", rate_hit)

    finally:
        conn.close()
        server.stop()
        # Clean up temp DB
        try:
            os.unlink(test_db)
        except OSError:
            pass

    # ── Summary ───────────────────────────────────────────────────────────
    total = PASS_COUNT + FAIL_COUNT
    print("\n" + "=" * 60)
    print(f"  Results: {PASS_COUNT}/{total} passed, {FAIL_COUNT} failed")
    print("=" * 60)

    if FAIL_COUNT > 0:
        sys.exit(1)
    else:
        print("  ALL CHECKS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    run_test()
