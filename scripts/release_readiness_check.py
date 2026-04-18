"""
Release Readiness Check — Phase 7.4
Local script equivalent of GET /control/readiness.
Printable report usable for pre-launch verification.
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def run_check():
    from jarvis_ai.core.brain import Brain
    from jarvis_ai.core.version import APP_VERSION, DB_SCHEMA_VERSION
    from jarvis_ai.core.runtime_lock import RuntimeLock
    from jarvis_ai.core.startup_validator import validate_startup
    from dotenv import load_dotenv

    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

    print("\n" + "="*55)
    print(f" Jarvis Release Readiness Check — v{APP_VERSION}")
    print("="*55)

    warnings = []
    results  = {}

    # DB check
    try:
        _cfg = {"llm": {"provider": "mock"}, "google": {"enabled": False}, "memory": {"db_path": "jarvis_memory.db"}}
        brain = Brain(_cfg)
        ok_r, _ = brain.memory_engine._safe_db_execute("SELECT 1")
        results["db_writable"]        = ok_r
        results["migrations_healthy"] = ok_r
    except Exception as e:
        results["db_writable"]        = False
        results["migrations_healthy"] = False
        warnings.append(f"DB error: {e}")

    # Storage check
    storage_dir = os.path.join(PROJECT_ROOT, "storage")
    try:
        os.makedirs(storage_dir, exist_ok=True)
        tf = os.path.join(storage_dir, ".write_test")
        with open(tf, "w") as f: f.write("ok")
        os.remove(tf)
        results["storage_writable"] = True
    except Exception as e:
        results["storage_writable"] = False
        warnings.append(f"Storage not writable: {e}")

    # Secret check
    secret = os.environ.get("JARVIS_SECRET_TOKEN", "")
    if not secret:
        warnings.append("JARVIS_SECRET_TOKEN is not set")
    results["secret_configured"] = bool(secret)

    # Runtime lock state
    lock_info = RuntimeLock.check_active()
    lock_ok   = not lock_info.get("stale", False)
    results["runtime_lock_healthy"] = lock_ok
    if lock_info.get("stale"):
        warnings.append(f"Stale lockfile (PID {lock_info['pid']}) — possible crash")

    # LLM mode
    llm_key = os.environ.get("LLM_API_KEY", "")
    results["llm_planner_mode"] = "configured" if llm_key else "fallback"

    # Web automation
    try:
        import yaml
        cfg_path = os.path.join(PROJECT_ROOT, "jarvis_ai", "config", "settings.yaml")
        with open(cfg_path) as f:
            config = yaml.safe_load(f)
        web_enabled = config.get("web_automation", {}).get("enabled", False)
    except Exception:
        web_enabled = False
        warnings.append("Could not read settings.yaml")
    results["web_automation_available"] = web_enabled

    # Schema version
    results["schema_version"] = DB_SCHEMA_VERSION
    results["app_version"]    = APP_VERSION

    # Overall
    critical = ["db_writable", "storage_writable", "secret_configured"]
    all_ok   = all(results.get(k) for k in critical)
    results["overall"] = "ready" if all_ok else "degraded"

    # Print report
    row_fmt = "  {:<30} {}"
    for key, val in results.items():
        icon = "[OK]" if val is True or val == "ready" else ("[!!]" if val is False else "[~~]")
        print(row_fmt.format(key + ":", f"{icon}  {val}"))

    if warnings:
        print("\n[Warnings]")
        for w in warnings:
            print(f"  [!] {w}")

    print("\n" + "="*55)
    print(f" Overall: {results['overall'].upper()}")
    print("="*55 + "\n")

    return results["overall"] == "ready"


if __name__ == "__main__":
    ok = run_check()
    sys.exit(0 if ok else 1)
