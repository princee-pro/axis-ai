"""
test_activity_log_migration.py — Regression test for the activity_log user_agent migration bug.

Reproduces the exact production scenario:
  1. Creates an OLD-schema activity_log WITHOUT user_agent column
  2. Starts MemoryEngine (triggers auto-migration)
  3. Verifies user_agent column now exists
  4. Inserts an activity_log row WITH user_agent — must not raise

Exits 0 on full pass, 1 on any failure.
"""
import os
import sys
import sqlite3
import tempfile

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

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

print("=" * 60)
print("  activity_log Migration Regression Test")
print("=" * 60)

# ── Step 1: Create a temp DB with the OLD schema (no user_agent) ─────────────
tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
tmp.close()
old_schema_db = tmp.name

print(f"\n[1] Creating old-schema DB at: {old_schema_db}")
with sqlite3.connect(old_schema_db) as conn:
    conn.execute("""
        CREATE TABLE system_settings (key TEXT PRIMARY KEY, value TEXT)
    """)
    # Old activity_log WITHOUT user_agent (simulates pre-Phase5 DB)
    conn.execute("""
        CREATE TABLE activity_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp    DATETIME,
            actor_type   TEXT,
            device_id    TEXT,
            endpoint     TEXT,
            method       TEXT,
            status_code  INTEGER,
            action_summary TEXT,
            error        TEXT,
            ip           TEXT
            -- user_agent intentionally MISSING to reproduce the bug
        )
    """)
    conn.execute(
        "INSERT INTO system_settings VALUES ('db_schema_version', '2.0')"
    )
    conn.commit()

# Verify it really is missing
cols_before = {row[1] for row in sqlite3.connect(old_schema_db).execute("PRAGMA table_info(activity_log)")}
check("Old schema lacks user_agent (pre-condition)", "user_agent" not in cols_before,
      f"columns found: {cols_before}")

# ── Step 2: Start MemoryEngine — must auto-migrate ────────────────────────────
print("\n[2] Starting MemoryEngine (expect auto-migration) ...")
try:
    from jarvis_ai.memory.memory_engine import MemoryEngine
    me = MemoryEngine(old_schema_db)
    check("MemoryEngine initialised without exception", True)
except Exception as e:
    check("MemoryEngine initialised without exception", False, str(e))
    me = None

# ── Step 3: Verify column now present ─────────────────────────────────────────
print("\n[3] Verifying migration applied ...")
cols_after = {row[1] for row in sqlite3.connect(old_schema_db).execute("PRAGMA table_info(activity_log)")}
check("user_agent column now exists in activity_log", "user_agent" in cols_after,
      f"columns present: {sorted(cols_after)}")

# ── Step 4: Insert with user_agent — must not raise ───────────────────────────
print("\n[4] Inserting activity_log row including user_agent ...")
if me:
    try:
        me.log_activity(
            actor_type="owner",
            device_id=None,
            endpoint="/health",
            method="GET",
            status_code=200,
            action_summary="migration test",
            ip="127.0.0.1",
            user_agent="TestAgent/1.0",
        )
        check("log_activity with user_agent succeeds (no exception)", True)
        # Confirm row stored
        with sqlite3.connect(old_schema_db) as conn:
            rows = conn.execute("SELECT user_agent FROM activity_log").fetchall()
        check("user_agent value stored correctly",
              any(r[0] == "TestAgent/1.0" for r in rows),
              f"rows: {rows}")
    except Exception as e:
        check("log_activity with user_agent succeeds (no exception)", False, str(e))
        check("user_agent value stored correctly", False, "insert failed")
else:
    check("log_activity with user_agent succeeds (no exception)", False, "MemoryEngine init failed")
    check("user_agent value stored correctly", False, "MemoryEngine init failed")

# ── Step 5: Idempotency — run MemoryEngine again on same DB ──────────────────
print("\n[5] Idempotency: reinitialise MemoryEngine on already-migrated DB ...")
try:
    me2 = MemoryEngine(old_schema_db)
    check("Second MemoryEngine init on migrated DB succeeds", True)
except Exception as e:
    check("Second MemoryEngine init on migrated DB succeeds", False, str(e))

# Cleanup
try:
    os.unlink(old_schema_db)
except OSError:
    pass

# ── Summary ──────────────────────────────────────────────────────────────────
total = PASS_COUNT + FAIL_COUNT
print("\n" + "=" * 60)
print(f"  Results: {PASS_COUNT}/{total} passed, {FAIL_COUNT} failed")
print("=" * 60)

if FAIL_COUNT > 0:
    sys.exit(1)
else:
    print("  ALL CHECKS PASSED")
    sys.exit(0)
