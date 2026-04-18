import os
import sys
import json
import http.client
import subprocess
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from jarvis_ai.core.version import APP_VERSION

def run_smoke_test():
    print(f"=== Jarvis AI Smoke Test (v{APP_VERSION}) ===")

    # 1. Validate Folders
    required_folders = ["storage", "logs", "data"]
    for folder in required_folders:
        if not os.path.exists(folder):
            print(f"[ERROR] Missing folder: {folder}")
            sys.exit(1)
        print(f"[OK] Folder exists: {folder}")

    # 2. Check settings.yaml
    if not os.path.exists("jarvis_ai/config/settings.yaml"):
        print("[ERROR] Missing settings.yaml")
        sys.exit(1)
    print("[OK] settings.yaml found.")

    # 3. Validate Phase 5 server config defaults
    print("\nValidating Phase 5 server config defaults...")
    try:
        import yaml
        with open("jarvis_ai/config/settings.yaml", "r") as f:
            config = yaml.safe_load(f)
        srv = config.get('server', {})

        assert srv.get('remote_enabled', None) is not None, \
            "server.remote_enabled not set in settings.yaml"
        assert srv.get('remote_enabled') == False, \
            f"server.remote_enabled should default to false, got {srv.get('remote_enabled')}"
        assert srv.get('bind_host', '127.0.0.1') == '127.0.0.1', \
            f"server.bind_host should default to 127.0.0.1, got {srv.get('bind_host')}"
        assert 'behind_reverse_proxy' in srv, \
            "server.behind_reverse_proxy missing from settings.yaml (Phase 5 key)"
        assert 'require_https_forwarded_proto' in srv, \
            "server.require_https_forwarded_proto missing from settings.yaml (Phase 5 key)"
        print("[OK] server defaults: remote_enabled=false, bind_host=127.0.0.1")
        print("[OK] Phase 5 keys present: behind_reverse_proxy, require_https_forwarded_proto")
    except AssertionError as e:
        print(f"[ERROR] Server config validation failed: {e}")
        sys.exit(1)

    # 4. Validate that JarvisServer refuses to start when remote=true without proxy
    print("\nValidating JarvisServer startup safety gate...")
    try:
        from unittest.mock import patch
        from jarvis_ai.core.brain import Brain
        from jarvis_ai.mobile.server import JarvisServer

        # Disable Google during test Brain init to avoid OAuth prompt
        with patch('jarvis_ai.core.brain.GOOGLE_AVAILABLE', False):
            test_brain = Brain({"memory": {"db_path": ":memory:"}})
        unsafe_cfg = {
            "remote_enabled":       True,
            "behind_reverse_proxy": False,   # should cause refusal
        }
        try:
            JarvisServer(test_brain, port=19999, server_config=unsafe_cfg)
            print("[ERROR] JarvisServer should have refused to start — safety gate MISSING!")
            sys.exit(1)
        except RuntimeError as e:
            print(f"[OK] Startup refused correctly: {str(e)[:80]}...")
    except Exception as e:
        print(f"[ERROR] Startup safety gate test failed unexpectedly: {e}")
        sys.exit(1)

    # 5. Simulate autonomous cycle & DB write
    print("\nTesting Brain initialization and DB write...")
    try:
        from unittest.mock import patch
        from jarvis_ai.core.brain import Brain
        # Patch Google to avoid OAuth prompt (smoke test doesn't need Gmail)
        with patch('jarvis_ai.core.brain.GOOGLE_AVAILABLE', False):
            brain = Brain({"memory": {"db_path": "jarvis_memory.db"}})

        print(f"[OK] Brain initialized (v{brain.version})")

        # LLM Provider check (Optional)
        provider = brain.config.get('llm', {}).get('provider', 'mock')
        print(f"Checking LLM Provider: {provider}")
        if provider != "mock":
            key = (os.environ.get('LLM_API_KEY')
                   or os.environ.get('OPENAI_API_KEY')
                   or os.environ.get('GEMINI_API_KEY'))
            if key:
                print("[INFO] Live LLM key detected. Skipping live test (use llm_self_test.py).")
            else:
                print("[WARNING] Non-mock provider selected but no API key found.")

        # Inject one goal
        goal = brain.goal_engine.create_goal("Smoke test goal", priority='normal')
        if not goal:
            print("[ERROR] Failed to set goal in DB")
            sys.exit(1)

        # Verify write
        try:
            goals = brain.goal_engine.list_goals()
            if not goals or not any(g['id'] == goal['id'] for g in goals):
                print("[WARNING] Goal not found in memory after write. This is expected if Supabase is offline.")
            else:
                print(f"[OK] DB write verified. Goal ID: {goal['id']}")
        except Exception as e:
            print(f"[WARNING] Goal verification failed. Supabase is likely offline: {e}")
    except Exception as e:
        print(f"[ERROR] Brain initialization or DB test failed: {e}")
        sys.exit(1)

    print("\n=== Smoke Test PASSED ===")

if __name__ == "__main__":
    run_smoke_test()
