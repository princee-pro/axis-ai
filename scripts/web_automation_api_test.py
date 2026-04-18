import requests
import json
import time

# Configuration
BASE_URL = "http://127.0.0.1:8000"
OWNER_TOKEN = "57d3231eca3d502f22d4e51bcfcb377d0937cc3a67b3ceb3948624d33ffe411a"

def test_web_automation_flow():
    headers = {
        "X-Jarvis-Token": OWNER_TOKEN,
        "Content-Type": "application/json"
    }

    print("1. Proposing Web Automation Plan...")
    plan = {
        "objective": "Test API Flow",
        "plan": {
            "start_url": "https://example.com",
            "steps": [
                {"action": "goto", "url": "https://example.com"},
                {"action": "extract", "selector": "h1", "name": "title"}
            ]
        }
    }
    
    try:
        response = requests.post(f"{BASE_URL}/web/propose", headers=headers, json=plan, timeout=10)
        print(f"Response Status: {response.status_code}")
        if response.status_code != 200:
            print(f"FAILED to propose plan: {response.text}")
            return
        
        action_id = response.json().get("action_id")
        print(f"SUCCESS: Action ID {action_id} created.")
    except Exception as e:
        print(f"ERROR calling /web/propose: {e}")
        return

    print("\n2. Approving Action...")
    approve_data = {"action_id": action_id}
    try:
        response = requests.post(f"{BASE_URL}/actions/approve", headers=headers, json=approve_data, timeout=10)
        print(f"Response Status: {response.status_code}")
        if response.status_code != 200:
            print(f"FAILED to approve action: {response.text}")
            return
        print("SUCCESS: Action approved.")
    except Exception as e:
        print(f"ERROR calling /actions/approve: {e}")
        return

    print("\n3. Executing Web Action...")
    try:
        # Execution might take longer
        response = requests.post(f"{BASE_URL}/web/actions/{action_id}/execute", headers=headers, timeout=60)
        print(f"Response Status: {response.status_code}")
        if response.status_code != 200:
            print(f"FAILED to execute action: {response.text}")
            return
        
        exec_result = response.json()
        print(f"SUCCESS: {exec_result.get('message')}")
    except Exception as e:
        print(f"ERROR calling /web/actions/execute: {e}")
        return

    print("\n4. Retrieving Results...")
    try:
        response = requests.get(f"{BASE_URL}/web/actions/{action_id}/result", headers=headers, timeout=10)
        print(f"Response Status: {response.status_code}")
        if response.status_code != 200:
            print(f"FAILED to retrieve results: {response.text}")
            return
        
        final_result = response.json()
        print("SUCCESS: Results retrieved.")
        print(json.dumps(final_result, indent=2))
    except Exception as e:
        print(f"ERROR calling /web/actions/result: {e}")
        return

    if final_result.get('status') == 'executed' or (final_result.get('result') and final_result['result'].get('status') == 'success'):
        print("\n✅ FULL WEB AUTOMATION API FLOW PASSED")
    else:
        print("\n❌ WEB AUTOMATION API FLOW FAILED")

if __name__ == "__main__":
    test_web_automation_flow()
