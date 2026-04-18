"""
Runtime Lock — Phase 7.4
Prevents duplicate Jarvis server instances by managing a PID lockfile.
"""
import os
import sys

_LOCK_DIR = "storage/runtime"
_LOCK_FILE = "jarvis.pid"


def _lock_path():
    return os.path.join(os.getcwd(), _LOCK_DIR, _LOCK_FILE)


def _is_pid_running(pid: int) -> bool:
    """Check if a PID is alive (Windows-compatible)."""
    try:
        import psutil  # optional dep
        return psutil.pid_exists(pid) and any(
            "python" in p.lower()
            for p in (psutil.Process(pid).cmdline() or [])
        )
    except Exception:
        pass
    # Fallback: try os.kill signal 0 (works on POSIX; on Windows always raises)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class RuntimeLock:
    """Acquires a PID lockfile to prevent duplicate server instances."""

    def __init__(self):
        self._path = _lock_path()

    def acquire(self):
        """Attempt to acquire the lock. Raise RuntimeError if another instance is running."""
        lock_dir = os.path.dirname(self._path)
        os.makedirs(lock_dir, exist_ok=True)

        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    old_pid = int(f.read().strip())
                if _is_pid_running(old_pid):
                    raise RuntimeError(
                        f"[JARVIS] DUPLICATE INSTANCE DETECTED: Another Jarvis server "
                        f"process (PID {old_pid}) appears to still be running.\n"
                        f"  → To stop it:  taskkill /PID {old_pid} /F\n"
                        f"  → Or use:      scripts\\stop_jarvis.ps1\n"
                        f"  → Then retry:  python -m jarvis_ai.mobile.server\n"
                        f"  → Lockfile at: {self._path}"
                    )
                else:
                    # Stale lockfile from a prior crash — remove it safely
                    print(f"[RUNTIME LOCK] Stale lockfile (PID {old_pid}) removed.")
                    os.remove(self._path)
            except (ValueError, OSError):
                # Corrupt or unreadable lockfile — remove it
                try:
                    os.remove(self._path)
                except OSError:
                    pass

        with open(self._path, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        print(f"[RUNTIME LOCK] Acquired (PID {os.getpid()})")

    def release(self):
        """Release the lockfile on normal shutdown."""
        try:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as f:
                    pid = int(f.read().strip())
                if pid == os.getpid():
                    os.remove(self._path)
                    print("[RUNTIME LOCK] Released cleanly.")
        except Exception as e:
            print(f"[RUNTIME LOCK] Warning: could not release lock: {e}")

    @staticmethod
    def check_active() -> dict:
        """Return status info about the current lock state."""
        path = _lock_path()
        if not os.path.exists(path):
            return {"locked": False, "pid": None, "path": path}
        try:
            with open(path, "r", encoding="utf-8") as f:
                pid = int(f.read().strip())
            running = _is_pid_running(pid)
            return {"locked": running, "pid": pid, "path": path, "stale": not running}
        except Exception:
            return {"locked": False, "pid": None, "path": path, "error": "unreadable"}
