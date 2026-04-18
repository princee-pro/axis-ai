import os
import sys
import time
import requests
import json
import uuid

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test token for Jarvis Bridge
TEST_TOKEN = "TEST_INTEGRATION_TOKEN_99"
os.environ["JARVIS_SECRET_TOKEN"] = TEST_TOKEN

# We don't start the server exactly like web_automation_self_test. 
# We'll just instantiate the Brain and Server here.
from jarvis_ai.core.brain import Brain
from jarvis_ai.mobile.server import JarvisServer

def run_tests():
    print("\n--- PHASE 7: GOAL ENGINE INTEGRATION SELF-TEST ---")
    
    # 1. Initialize Brain & DB
    print("\n[1] Initializing Test Brain (In-Memory DB Mode)...")
    if os.path.exists('test_goals.db'):
        os.remove('test_goals.db')
    config = {
        'memory': {'db_path': 'test_goals.db'},
        'security_token': TEST_TOKEN,
        'server': {'remote_enabled': False},
        'google': {'enabled': False}
    }
    brain = Brain(config)
    
    # 2. Launch Server
    print("\n[2] Handing off to Server...")
    server = JarvisServer(brain, port=8001, server_config=config.get('server'))
    server.start()
    
    time.sleep(1) # allow bind
    
    headers = {"X-Jarvis-Token": TEST_TOKEN, "Content-Type": "application/json"}
    base_url = "http://localhost:8001"
    
    try:
        # 3. Create Goal
        print("\n[3] Testing Goal Creation (/goals)...")
        res = requests.post(f"{base_url}/goals", headers=headers, json={
            "title": "Check Weather",
            "objective": "Go to weather.com website and find the weather for New York",
            "priority": "normal"
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "goal" in data
        goal_id = data["goal"]["id"]
        print(f"✅ Goal created successfully: {goal_id}")
        
        # 4. Plan Goal
        print(f"\n[4] Testing Planning Strategy (/goals/{goal_id}/plan)...")
        res = requests.post(f"{base_url}/goals/{goal_id}/plan", headers=headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        plan_data = res.json()
        assert "plan_id" in plan_data
        print(f"✅ Goal planned: Plan ID {plan_data['plan_id']} with {plan_data.get('steps_count')} steps")
        
        # 5. Check List & Summary
        print(f"\n[5] Verifying Summarization endpoint (/goals/{goal_id}/summary)...")
        res = requests.get(f"{base_url}/goals/{goal_id}/summary", headers=headers)
        assert res.status_code == 200
        summary_data = res.json()
        assert summary_data["status"] == "planned"
        print(f"✅ Summary output looks correct: {json.dumps(summary_data)}")
        
        # 6. Advance Goal (Route to Pending Actions)
        print(f"\n[6] Advancing Goal Execution (/goals/{goal_id}/advance)...")
        res = requests.post(f"{base_url}/goals/{goal_id}/advance", headers=headers)
        assert res.status_code == 200
        print(f"✅ Goal advanced successfully.")
        
        # Check if action was proposed
        res = requests.get(f"{base_url}/goals/{goal_id}/summary", headers=headers)
        summary = res.json()
        assert summary["status"] == "awaiting_approval", f"Expected awaiting_approval, got {summary['status']}: {json.dumps(summary)}"
        action_ref = summary.get("latest_action_reference")
        assert action_ref is not None, "Action reference was not populated"
        print(f"✅ Verified action delegation to generic approval queue: Action_Ref={action_ref}")
        
        # 7. Test Unsafe Routing (ATS Exploit)
        print("\n[7] Testing Unsafe Goal Constraints (ATS Exploit)...")
        res = requests.post(f"{base_url}/goals", headers=headers, json={
            "title": "Mass Apply",
            "objective": "Automatically apply to jobs on greenhouse.io bypassing recaptcha"
        })
        unsafe_goal_id = res.json()["goal"]["id"]
        
        res = requests.post(f"{base_url}/goals/{unsafe_goal_id}/plan", headers=headers)
        assert res.status_code == 400
        unsafe_res = res.json()
        assert "CAPTCHA bypass requested" in unsafe_res["error"] or "ATS exploit detected" in unsafe_res["error"]
        print(f"✅ Unsafe plan correctly rejected prior to action mapping: {unsafe_res['error']}")
        
        print("\n===============================================")
        print("✅ ALL GOAL ENGINE INTEGRATION TESTS PASSED")
        print("===============================================")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        raise e
    finally:
        print("\nStopping server...")
        server.stop()

if __name__ == "__main__":
    run_tests()
