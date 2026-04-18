import os
import json
import time
import threading
import http.server
import socketserver
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

# Create minimal HTML files for testing
SAFE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Jarvis Safe Page</title></head>
<body>
    <h1 id="title">Hello Jarvis</h1>
    <p id="content">Contact us at admin@example.com or use token Bearer abcdef12345===</p>
    <div class="price">$99.99</div>
</body>
</html>
"""

RISKY_HTML = """
<!DOCTYPE html>
<html>
<head><title>Jarvis Risky Page</title></head>
<body>
    <h1>Login Required</h1>
    <form>
        <input type="password" name="password">
    </form>
</body>
</html>
"""

COMMIT_HTML = """
<!DOCTYPE html>
<html>
<head><title>Jarvis Commit Page</title></head>
<body>
    <button id="submit-btn" type="submit">Place Order</button>
</body>
</html>
"""

UPLOAD_HTML = """
<!DOCTYPE html>
<html>
<head><title>Jarvis Upload Page</title></head>
<body>
    <input type="file" id="file-upload">
</body>
</html>
"""

def run_test_server(port=8080):
    class TestHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            if self.path == "/login":
                self.wfile.write(RISKY_HTML.encode())
            elif self.path == "/commit":
                self.wfile.write(COMMIT_HTML.encode())
            elif self.path == "/upload":
                self.wfile.write(UPLOAD_HTML.encode())
            else:
                self.wfile.write(SAFE_HTML.encode())
    
    with socketserver.TCPServer(("127.0.0.1", port), TestHandler) as httpd:
        print(f"Test server running at http://127.0.0.1:{port}")
        httpd.serve_forever()

def main():
    # 1. Check dependencies
    try:
        import playwright
        print("✅ Playwright is installed.")
    except ImportError:
        print("❌ Playwright is NOT installed. Skipping automation test.")
        return

    # 2. Start local server in background
    server_thread = threading.Thread(target=run_test_server, daemon=True)
    server_thread.start()
    time.sleep(2) # Wait for server to start

    # 3. Import Jarvis components
    try:
        import yaml
        from jarvis_ai.core.brain import Brain
        print("✅ Jarvis core components imported.")
    except ImportError as e:
        print(f"❌ Error importing Jarvis components: {e}")
        return

    # 4. Setup Brain with enabled web_automation
    config_path = Path(__file__).parent.parent / 'jarvis_ai' / 'config' / 'settings.yaml'
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        config = {}

    # Force enable for test
    if 'capabilities' not in config: config['capabilities'] = {}
    if 'web_automation' not in config['capabilities']: config['capabilities']['web_automation'] = {}
    config['capabilities']['web_automation']['enabled'] = True
    
    brain = Brain(config)
    
    # 5. Define Plan
    test_plan = {
        "start_url": "http://127.0.0.1:8080",
        "steps": [
            {"action": "goto", "url": "http://127.0.0.1:8080"},
            {"action": "extract", "selector": "#title", "name": "page_title"},
            {"action": "extract", "selector": "#content", "name": "page_content"},
            {"action": "extract", "selector": ".price", "name": "product_price"},
            {"action": "screenshot", "name": "test_page"}
        ],
        "constraints": {
            "timeout_ms": 10000,
            "max_steps": 5
        }
    }

    # 6. Test Scenario A: Normal Execution
    print("\n--- Running Normal Execution Test ---")
    result = brain.web_automation.run_plan(test_plan)
    print(f"Result Status: {result.get('status')}")
    print(f"Extracted Data: {result.get('extracted_data')}")
    
    if result.get('status') == 'success' and 'Hello Jarvis' in str(result.get('extracted_data')):
        print("✅ Normal execution test PASSED")
    else:
        print("❌ Normal execution test FAILED")

    # 7. Test Scenario B: Safety Heuristic (Login Detection)
    print("\n--- Running Safety Heuristic Test (Login) ---")
    login_plan = {
        "start_url": "http://127.0.0.1:8080/login",
        "steps": [
            {"action": "goto", "url": "http://127.0.0.1:8080/login"}
        ]
    }
    # Note: The test page has a password field, so it should be blocked.
    result = brain.web_automation.run_plan(login_plan)
    print(f"Result Status: {result.get('status')}")
    print(f"Reason: {result.get('reason')}")
    print(f"Evidence: {result.get('evidence')}")

    if result.get('status') == 'blocked' and result.get('reason') == 'login':
        print("✅ Safety heuristic test PASSED")
    else:
        print("❌ Safety heuristic test FAILED (Expected block on login field)")

    # 7.3 Commit-risk stop
    print("\n--- Running Commit-Risk Test ---")
    commit_plan = {
        "start_url": "http://127.0.0.1:8080/commit",
        "has_commit_risk": True,
        "commit_risk_reasons": ["Testing commit heuristic"],
        "steps": [
            {"action": "goto", "url": "http://127.0.0.1:8080/commit"},
            {"action": "click", "selector": "#submit-btn"}
        ]
    }
    result = brain.web_automation.run_plan(commit_plan)
    print(f"Result Status: {result.get('status')}")
    print(f"Reason: {result.get('reason')}")
    if result.get('status') == 'partial' and result.get('reason') == 'commit_confirmation_required':
        print("✅ Commit-risk test PASSED")
    else:
        print("❌ Commit-risk test FAILED")

    # 7.4 File upload block
    print("\n--- Running File Upload Block Test ---")
    upload_plan = {
        "start_url": "http://127.0.0.1:8080/upload",
        "steps": [
            {"action": "goto", "url": "http://127.0.0.1:8080/upload"},
            {"action": "click", "selector": "#file-upload"}
        ]
    }
    result = brain.web_automation.run_plan(upload_plan)
    print(f"Result Status: {result.get('status')}")
    print(f"Reason: {result.get('reason')}")
    if result.get('status') == 'blocked' and result.get('reason') == 'file_upload_blocked':
        print("✅ File upload block test PASSED")
    else:
        print("❌ File upload block test FAILED")

    # 7.5 & 7.6 API level tests
    import types
    from jarvis_ai.mobile.server import JarvisRequestHandler

    class MockHandler:
        def __init__(self, brain):
            self.brain = brain
            self.last_json = None
            self.last_status = None
        def _send_json(self, data, status=200):
            self.last_json = data
            self.last_status = status
        def _log_request(self, *args, **kwargs):
            pass

    mock_handler = MockHandler(brain)
    mock_handler._handle_web_propose = types.MethodType(JarvisRequestHandler._handle_web_propose, mock_handler)
    mock_handler._handle_web_result = types.MethodType(JarvisRequestHandler._handle_web_result, mock_handler)

    print("\n--- Running Invalid Plan Rejection Test ---")
    invalid_plan_req = {
        "objective": "Bad plan",
        "plan": {
            "steps": [{"action": "delete_db_action_fake"}]
        }
    }
    mock_handler._handle_web_propose({"id": "test", "type": "owner", "role": "admin"}, invalid_plan_req)
    if mock_handler.last_status == 400:
        print("✅ Invalid plan rejected (400) PASSED")
    else:
        print(f"❌ Invalid plan rejection FAILED (Got {mock_handler.last_status})")

    print("\n--- Running Result Endpoint Test ---")
    good_plan_req = {
        "objective": "API Test Plan",
        "plan": {
            "steps": [{"action": "goto", "url": "http://127.0.0.1:8080"}]
        }
    }
    mock_handler._handle_web_propose({"id": "test", "type": "owner", "role": "admin"}, good_plan_req)
    action_id = mock_handler.last_json.get("action_id")
    
    # Approve and execute
    brain.memory_engine.update_action_status(action_id, 'approved')
    brain.execute_pending_action(action_id)
    
    # Check result
    mock_handler._handle_web_result({"id": "test", "type": "owner", "role": "admin"}, action_id)
    if mock_handler.last_status == 200 and 'result' in mock_handler.last_json:
        print("✅ Result endpoint PASSED")
    else:
        print("❌ Result endpoint FAILED")

    print("\nTests complete.")

if __name__ == "__main__":
    main()
