"""
Restore Jarvis — Phase 7.4
Restores DB and storage from a backup archive produced by backup_jarvis.py.
"""
import os
import sys
import zipfile
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH      = os.path.join(PROJECT_ROOT, "jarvis_memory.db")
STORAGE_DIR  = os.path.join(PROJECT_ROOT, "storage")
LOCK_FILE    = os.path.join(STORAGE_DIR, "runtime", "jarvis.pid")


def run_restore(backup_zip: str, yes: bool = False):
    if not os.path.isfile(backup_zip):
        print(f"[RESTORE] ERROR: Backup file not found: {backup_zip}")
        sys.exit(1)

    # Safety: check no live server is running
    if os.path.exists(LOCK_FILE):
        print("[RESTORE] ERROR: A Jarvis server appears to be running (lockfile exists).")
        print(f"  → Lock: {LOCK_FILE}")
        print("  → Stop the server first:  scripts\\stop_jarvis.ps1")
        sys.exit(1)

    print("=" * 50)
    print(" JARVIS RESTORE WARNING")
    print("=" * 50)
    print(f"Source archive : {backup_zip}")
    print(f"Current DB     : {DB_PATH}")
    print(f"Storage dir    : {STORAGE_DIR}")
    print("=" * 50)
    print("⚠  This will OVERWRITE the current database and storage files.")

    if not yes:
        confirm = input("Type YES to proceed: ").strip()
        if confirm != "YES":
            print("[RESTORE] Aborted by user.")
            sys.exit(0)

    # Pre-backup current state before overwriting
    if os.path.exists(DB_PATH):
        pre_backup = DB_PATH + ".pre_restore"
        shutil.copy2(DB_PATH, pre_backup)
        print(f"[RESTORE] Pre-restore snapshot saved: {pre_backup}")

    print(f"[RESTORE] Extracting {backup_zip}...")
    with zipfile.ZipFile(backup_zip, "r") as zf:
        names = zf.namelist()
        for name in names:
            target = os.path.join(PROJECT_ROOT, name)
            # Validate path (prevent zip-slip)
            real_target = os.path.realpath(target)
            if not real_target.startswith(os.path.realpath(PROJECT_ROOT)):
                print(f"  ⚠ Skipping unsafe path: {name}")
                continue
            os.makedirs(os.path.dirname(real_target), exist_ok=True)
            with zf.open(name) as src, open(real_target, "wb") as dst:
                dst.write(src.read())
            print(f"  ✓ Restored {name}")

    print("[RESTORE] Complete. Start server to verify.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/restore_jarvis.py <backup.zip> [--yes]")
        sys.exit(1)
    backup_arg = sys.argv[1]
    yes_flag   = "--yes" in sys.argv
    run_restore(backup_arg, yes=yes_flag)
