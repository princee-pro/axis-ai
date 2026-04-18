"""
Export Status Snapshot — Phase 7.4
Dumps a compact JSON snapshot of the current Jarvis system state.
No secrets are included. Useful for support and debugging.
"""
import os
import sys
import json
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def run_export(output_path: str = None):
    from jarvis_ai.core.brain import Brain
    from jarvis_ai.core.version import APP_VERSION, DB_SCHEMA_VERSION

    _config = {
        "llm": {"provider": "mock"},
        "google": {"enabled": False},
        "memory": {"db_path": "jarvis_memory.db"},
    }
    brain = Brain(_config)

    counts   = brain.memory_engine.get_control_counts()
    approvals= brain.memory_engine.get_pending_approvals_with_linkage(limit=5)
    blocked  = brain.memory_engine.get_blocked_items(limit=5)
    results  = brain.memory_engine.get_recent_results(limit=5)
    events   = brain.memory_engine.get_recent_events(limit=5) if hasattr(brain.memory_engine, "get_recent_events") else []

    snapshot = {
        "exported_at":    datetime.utcnow().isoformat() + "Z",
        "app_version":    APP_VERSION,
        "schema_version": DB_SCHEMA_VERSION,
        "counts":         counts,
        "top_pending_approvals": approvals,
        "top_blocked":    blocked,
        "top_results":    results,
        "recent_events":  events,
    }

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, default=str)
        print(f"[SNAPSHOT] Saved to {output_path}")
    else:
        print(json.dumps(snapshot, indent=2, default=str))

    return snapshot


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else None
    run_export(output_path=out)
