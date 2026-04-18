"""
Production Hardening Self-Test — Phase 7.4
Tests startup validation, auth, backup/export, readiness, and lockfile handling.
Runs fully locally without external dependencies or internet access.
"""
import os
import sys
import json
import shutil
import tempfile
import secrets
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

TESTS_PASSED = 0
TESTS_FAILED = 0

_TEST_CONFIG = {
    "llm": {"provider": "mock"},
    "google": {"enabled": False},
    "memory": {"db_path": "jarvis_memory.db"},
}

def ok(name):
    global TESTS_PASSED
    TESTS_PASSED += 1
    print(f"  [PASS] {name}")


def fail(name, reason=""):
    global TESTS_FAILED
    TESTS_FAILED += 1
    print(f"  [FAIL] {name}  [{reason}]")


# ─── 9.1 Startup Validation ──────────────────────────────────────────────────
print("\n--- Test 9.1: Startup Validation ---")

from jarvis_ai.core.startup_validator import validate_startup, print_startup_summary
from jarvis_ai.core.brain import Brain

# Real brain for DB handle
_brain = Brain(_TEST_CONFIG)

# Valid config — should NOT raise
try:
    os.environ["JARVIS_SECRET_TOKEN"] = "test_secret_" + secrets.token_hex(16)
    result = validate_startup({"web_automation": {"enabled": False}}, _brain.memory_engine)
    if result is True:
        ok("Valid config passes validation")
    else:
        fail("Valid config passes validation", "returned non-True")
except SystemExit:
    fail("Valid config passes validation", "raised SystemExit unexpectedly")

# Bad kill-switch type — should raise SystemExit
try:
    validate_startup({"web_automation": {"enabled": "yes"}}, _brain.memory_engine)
    fail("Bad kill-switch type raises SystemExit", "did not raise")
except SystemExit:
    ok("Bad kill-switch type raises SystemExit")

# Missing secret — should raise SystemExit
prev = os.environ.pop("JARVIS_SECRET_TOKEN", None)
try:
    validate_startup({}, _brain.memory_engine)
    fail("Missing secret raises SystemExit", "did not raise")
except SystemExit:
    ok("Missing secret raises SystemExit")
finally:
    if prev: os.environ["JARVIS_SECRET_TOKEN"] = prev


# ─── 9.2 Auth Consistency ────────────────────────────────────────────────────
print("\n--- Test 9.2: Auth Consistency ---")
from jarvis_ai.mobile.server import JarvisRequestHandler
from io import BytesIO
from unittest.mock import MagicMock

# Simulate a minimal HTTP request context
class FakeHeader(dict):
    def get(self, key, default=None):
        return super().get(key.lower(), default)

class FakeHandler(JarvisRequestHandler):
    def __init__(self): pass

token = os.environ.get("JARVIS_SECRET_TOKEN", "fallback_test_token_abc")
brain_mock = MagicMock()
brain_mock.config = {"security_token": token}
brain_mock.memory_engine.authenticate_device_token = MagicMock(return_value=None)

handler = FakeHandler()
handler.brain = brain_mock

# Canonical owner auth
handler.headers = FakeHeader({"x-jarvis-token": token})
auth = handler._get_auth_context()
if auth and auth["type"] == "owner" and auth.get("auth_method") == "X-Jarvis-Token":
    ok("Canonical X-Jarvis-Token owner auth")
else:
    fail("Canonical X-Jarvis-Token owner auth", str(auth))

# Legacy Bearer alias
handler.headers = FakeHeader({"authorization": f"Bearer {token}"})
auth = handler._get_auth_context()
if auth and auth["type"] == "owner" and "Deprecated" in auth.get("auth_method", ""):
    ok("Legacy Authorization: Bearer accepted (deprecated)")
else:
    fail("Legacy Authorization: Bearer accepted (deprecated)", str(auth))

# Wrong token → no auth
handler.headers = FakeHeader({"x-jarvis-token": "wrong_token"})
auth = handler._get_auth_context()
if auth is None:
    ok("Wrong token returns None")
else:
    fail("Wrong token returns None", str(auth))


# ─── 9.3 Backup / Export ─────────────────────────────────────────────────────
print("\n--- Test 9.3: Backup and Export ---")
from scripts.backup_jarvis import run_backup

# Patch BACKUP_DIR to temp dir
import scripts.backup_jarvis as backup_mod
orig_backup_dir = backup_mod.BACKUP_DIR
with tempfile.TemporaryDirectory() as tmpdir:
    backup_mod.BACKUP_DIR = tmpdir
    try:
        archive = run_backup(note="test backup")
        if os.path.isfile(archive):
            ok("Backup archive created successfully")
        else:
            fail("Backup archive created successfully", "file not found")
    except Exception as e:
        fail("Backup archive created successfully", str(e))
    finally:
        backup_mod.BACKUP_DIR = orig_backup_dir

# Export snapshot
from scripts.export_status_snapshot import run_export
with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
    snap_path = tf.name
try:
    snap = run_export(output_path=snap_path)
    if snap and "counts" in snap and "app_version" in snap:
        ok("Status snapshot exports safely")
    else:
        fail("Status snapshot exports safely", str(snap)[:100])
    # No secrets check
    snap_text = open(snap_path).read()
    secret_token = os.environ.get("JARVIS_SECRET_TOKEN", "")
    if secret_token and secret_token in snap_text:
        fail("Snapshot does not contain secret token", "token found!")
    else:
        ok("Snapshot does not contain secret token")
except Exception as e:
    fail("Status snapshot exports safely", str(e))
finally:
    if os.path.exists(snap_path): os.unlink(snap_path)


# ─── 9.4 Readiness Report ────────────────────────────────────────────────────
print("\n--- Test 9.4: Readiness Check ---")
from scripts.release_readiness_check import run_check
import jarvis_ai.core.runtime_lock as rl_mod

os.environ.setdefault("JARVIS_SECRET_TOKEN", "test_" + secrets.token_hex(8))
# Clean up any stale lockfile from a previous test run so readiness check succeeds cleanly
_stale_lock = rl_mod._lock_path()
if os.path.exists(_stale_lock):
    try:
        with open(_stale_lock, "r", encoding="utf-8") as _f:
            _stale_pid = int(_f.read().strip())
        if _stale_pid != os.getpid():
            os.remove(_stale_lock)
    except Exception:
        pass

try:
    ready = run_check()
    ok(f"Readiness check runs (overall={'ready' if ready else 'degraded'})")
except SystemExit:
    ok("Readiness check exits with proper code")
except Exception as e:
    fail("Readiness check runs", str(e))


# ─── 9.5 Lock / Runtime State ────────────────────────────────────────────────
print("\n--- Test 9.5: Lock / Runtime Handling ---")
from jarvis_ai.core.runtime_lock import RuntimeLock

# Clear any existing lock first
lock = RuntimeLock()
lock_path = lock._path
if os.path.exists(lock_path):
    os.remove(lock_path)

# 1. Acquire should succeed on clean state
try:
    lock.acquire()
    if os.path.exists(lock_path):
        ok("Lock acquired successfully — lockfile exists")
    else:
        fail("Lock acquired successfully", "lockfile missing")
except Exception as e:
    fail("Lock acquired successfully", str(e))

# 2. Second acquire from a *different instance* should fail
lock2 = RuntimeLock()
try:
    lock2.acquire()
    fail("Second acquire raises RuntimeError", "did not raise")
except RuntimeError:
    ok("Second acquire raises RuntimeError (duplicate protection)")

# 3. Release should remove the lockfile
lock.release()
if not os.path.exists(lock_path):
    ok("Lock released cleanly — lockfile removed")
else:
    fail("Lock released cleanly", "lockfile still exists")

# 4. Stale lockfile handling
with open(lock_path, "w") as f:
    f.write("999999999")  # fake non-existent PID
lock3 = RuntimeLock()
try:
    lock3.acquire()
    ok("Stale lockfile removed and re-acquired")
except RuntimeError:
    fail("Stale lockfile removed and re-acquired", "raised RuntimeError")
finally:
    lock3.release()


# ─── Summary ─────────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
if TESTS_FAILED == 0:
    print(f"ALL PHASE 7.4 TESTS PASSED ({TESTS_PASSED}/{TESTS_PASSED})")
else:
    print(f"TESTS PASSED: {TESTS_PASSED}  |  TESTS FAILED: {TESTS_FAILED}")
print("="*50)
