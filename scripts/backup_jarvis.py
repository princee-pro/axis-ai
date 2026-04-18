"""
Backup Jarvis — Phase 7.4
Creates a timestamped backup of the SQLite DB and storage manifest.
"""
import os
import sys
import shutil
import zipfile
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH      = os.path.join(PROJECT_ROOT, "jarvis_memory.db")
STORAGE_DIR  = os.path.join(PROJECT_ROOT, "storage")
BACKUP_DIR   = os.path.join(STORAGE_DIR, "backups")


def run_backup(note: str = ""):
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    label      = f"{timestamp}_backup"
    backup_out = os.path.join(BACKUP_DIR, f"{label}.zip")

    os.makedirs(BACKUP_DIR, exist_ok=True)

    print(f"[BACKUP] Creating backup → {backup_out}")

    with zipfile.ZipFile(backup_out, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. DB file
        if os.path.exists(DB_PATH):
            zf.write(DB_PATH, arcname="jarvis_memory.db")
            print(f"  ✓ Added jarvis_memory.db")
        else:
            print(f"  ⚠ DB not found at {DB_PATH}")

        # 2. Storage directory (excluding backups themselves)
        for dirpath, dirnames, filenames in os.walk(STORAGE_DIR):
            # Skip the backups sub-dir to avoid recursion
            dirnames[:] = [d for d in dirnames if d != "backups"]
            for fname in filenames:
                full_path = os.path.join(dirpath, fname)
                arcname   = os.path.relpath(full_path, PROJECT_ROOT)
                zf.write(full_path, arcname=arcname)
                print(f"  ✓ Added {arcname}")

        # 3. Runbook snapshot (no secrets)
        runbook = os.path.join(PROJECT_ROOT, "README_RUNBOOK.md")
        if os.path.exists(runbook):
            zf.write(runbook, arcname="README_RUNBOOK.md")
            print(f"  ✓ Added README_RUNBOOK.md")

        # 4. Note file if provided
        if note:
            zf.writestr("BACKUP_NOTE.txt", note)
            print(f"  ✓ Added backup note")

    size_kb = os.path.getsize(backup_out) / 1024
    print(f"[BACKUP] Done! Archive: {backup_out} ({size_kb:.1f} KB)")
    return backup_out


if __name__ == "__main__":
    note_arg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    run_backup(note=note_arg)
