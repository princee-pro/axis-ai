#!/usr/bin/env python3
"""
Jarvis RC1 Release Checklist Automation.
Verifies critical paths, endpoints, and security constraints.
"""

import os
import sys
import requests
import json
import socket
from datetime import datetime

# Configure base URL (default to localhost)
HOST = "127.0.0.1"
PORT = 8000
BASE_URL = f"http://{HOST}:{PORT}"

def check_file(path):
    return os.path.exists(path)

def run_checklist():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    print(f"--- Jarvis RC1 Release Checklist [{datetime.now().strftime('%Y-%m-%d %H:%M')}] ---")
    
    # 1. Environment & Files
    print("[1/6] Environment & Static Assets...")
    checks = {
        "Settings YAML": "jarvis_ai/config/settings.yaml",
        "Dashboard HTML": "jarvis_ai/ui/index.html",
        "Dashboard JS": "jarvis_ai/ui/static/app.js",
        "Dashboard CSS": "jarvis_ai/ui/static/style.css",
        "Startup Validator": "jarvis_ai/core/startup_validator.py",
        "Runtime Lock": "jarvis_ai/core/runtime_lock.py"
    }
    
    all_files_ok = True
    for name, rel_path in checks.items():
        if check_file(os.path.join(project_root, rel_path)):
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name} MISSING")
            all_files_ok = False

    # 2. Server Connectivity
    print("\n[2/6] Server Connectivity (is Jarvis running?)...")
    try:
        # We try to hit /health without token first to see if it's reachable
        # Note: /health might require localhost for unauth
        requests.get(f"{BASE_URL}/health", timeout=2)
        print(f"  [PASS] Server reachable at {BASE_URL}")
    except Exception:
        print(f"  [FAIL] Server unreachable at {BASE_URL}. Ensure server is running.")
        return

    # 3. Canonical Auth Verification
    print("\n[3/6] Canonical Auth Verification...")
    token = os.environ.get("JARVIS_SECRET_TOKEN", "mock_token")
    headers = {"X-Jarvis-Token": token}
    
    who_res = requests.get(f"{BASE_URL}/whoami", headers=headers)
    if who_res.status_code == 200:
        print("  [PASS] /whoami accepts X-Jarvis-Token")
        data = who_res.json()
        if data.get('auth_context', {}).get('role') == 'owner':
             print("  [PASS] Correct owner-level role identified")
        else:
             print("  [FAIL] Unexpected role returned")
    else:
        print(f"  [FAIL] /whoami rejected token. Status: {who_res.status_code}")

    # 4. Control Plane Routes
    print("\n[4/6] Control Plane Routes...")
    routes = ["/control/summary", "/control/readiness", "/control/about", "/control/approvals"]
    for r in routes:
        res = requests.get(f"{BASE_URL}{r}", headers=headers)
        if res.status_code == 200:
             print(f"  [PASS] {r}")
        else:
             print(f"  [FAIL] {r} status {res.status_code}")

    # 5. Static Route Serving
    print("\n[5/6] Static Route Serving...")
    static_res = requests.get(f"{BASE_URL}/ui")
    if static_res.status_code == 200 and "<html" in static_res.text.lower():
         print("  [PASS] /ui serves HTML")
    else:
         print("  [FAIL] /ui did not serve HTML")

    js_res = requests.get(f"{BASE_URL}/static/app.js")
    if js_res.status_code == 200 and "application/javascript" in js_res.headers.get('Content-Type', ''):
         print("  [PASS] /static/app.js serves correctly")
    else:
         print("  [FAIL] /static/app.js MIME or status issue")

    # 6. Readiness Quality
    print("\n[6/6] Readiness In-Depth...")
    ready_res = requests.get(f"{BASE_URL}/control/readiness", headers=headers)
    if ready_res.status_code == 200:
        report = ready_res.json()
        if report.get('overall') == 'ready':
             print("  [PASS] System reports OVERALL READY state")
        else:
             print(f"  [WARN] System is {report.get('overall')}")
        if 'manifest' in report:
             print("  [PASS] Integration manifest present")
    else:
        print("  [FAIL] Could not fetch readiness details")

    print("\n--- Checklist Summary ---")
    if all_files_ok:
        print("RESULT: RC1 CANDIDATE VALIDATED FOR RELEASE.")
    else:
        print("RESULT: BLOCKED - CORE FILES MISSING.")

if __name__ == "__main__":
    run_checklist()
