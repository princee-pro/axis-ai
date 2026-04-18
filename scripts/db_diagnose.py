"""
db_diagnose.py — Jarvis DB diagnostics.

Prints:
  - Configured and resolved absolute DB path
  - PRAGMA database_list (actual file SQLite is using)
  - PRAGMA table_info(activity_log) with column list
  - Verifies every expected column is present

No secrets are printed. Safe to run anytime.
"""
import os
import sys
import sqlite3

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

try:
    import yaml
    CONFIG_PATH = os.path.join(PROJECT_ROOT, 'jarvis_ai', 'config', 'settings.yaml')
    with open(CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)
    configured_db = config.get('memory', {}).get('db_path', 'jarvis_memory.db')
except Exception as e:
    configured_db = 'jarvis_memory.db'
    print(f"[WARN] Could not read settings.yaml: {e}")

abs_db = os.path.abspath(os.path.join(PROJECT_ROOT, configured_db))

print("=" * 60)
print("  Jarvis DB Diagnostics")
print("=" * 60)
print(f"  Configured db_path  : {configured_db}")
print(f"  Resolved (abs) path : {abs_db}")
print(f"  File exists         : {os.path.isfile(abs_db)}")
if os.path.isfile(abs_db):
    print(f"  File size (bytes)   : {os.path.getsize(abs_db)}")

if not os.path.isfile(abs_db):
    print("\n[NOTE] DB does not exist yet — it will be created at first startup.")
else:
    with sqlite3.connect(abs_db) as conn:
        print("\n--- PRAGMA database_list ---")
        for row in conn.execute("PRAGMA database_list"):
            print(f"  seq={row[0]}  name={row[1]}  file='{row[2]}'")

        print("\n--- PRAGMA table_info(activity_log) ---")
        rows = conn.execute("PRAGMA table_info(activity_log)").fetchall()
        if not rows:
            print("  [WARN] activity_log table does not exist!")
        else:
            for row in rows:
                print(f"  cid={row[0]:2d}  name={row[1]:<18s}  type={row[2]}")

        # Verify required columns
        from jarvis_ai.memory.memory_engine import MemoryEngine
        required = {col for col, _ in MemoryEngine._ACTIVITY_LOG_COLUMNS if col != 'id'}
        present  = {row[1] for row in rows}
        missing  = required - present

        print("\n--- Column coverage check ---")
        if missing:
            print(f"  [FAIL] Missing columns: {sorted(missing)}")
            print("  Run 'python -c \"from jarvis_ai.memory.memory_engine import MemoryEngine; MemoryEngine()\"'")
            print("  to trigger auto-migration.")
        else:
            print("  [OK] All required columns present.")

print("\n--- Trigger auto-migration now ---")
try:
    from jarvis_ai.memory.memory_engine import MemoryEngine
    me = MemoryEngine(abs_db)
    with sqlite3.connect(abs_db) as conn:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(activity_log)")]
    print(f"  activity_log columns after init: {cols}")
    print("  [OK] MemoryEngine initialised successfully.")
except Exception as e:
    print(f"  [FAIL] MemoryEngine init error: {e}")

print("=" * 60)
