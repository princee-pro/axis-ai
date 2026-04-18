"""
Gmail Insights Self-Test.
Verifies LLM-assisted inbox classification.
"""
import os
import sys
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain

def main():
    print("=== Jarvis AI: Gmail Insights Self-Test ===")
    token_file = "storage/google_token.json"
    
    # We can test the logic even without a live token by mocking the Gmail response
    # if token doesn't exist.
    
    try:
        brain = Brain({})
        
        if not os.path.exists(token_file):
            print(f"[INFO] {token_file} not found. Running with MOCKED inbox data to verify LLM classification logic.")
            mock_messages = [
                {"id": "1", "from": "boss@work.com", "subject": "URGENT: Meeting moved", "snippet": "We need to talk about the project now."},
                {"id": "2", "from": "newsletter@tech.com", "subject": "Weekly Digest", "snippet": "Here is what happened this week..."},
                {"id": "3", "from": "mom@family.com", "subject": "Lunch tomorrow?", "snippet": "Are you free for lunch at 12?"}
            ]
            # Monkey patch list_messages for this test
            if brain.gmail:
                brain.gmail.list_messages = lambda limit=10: mock_messages
            else:
                print("[SKIPPED] Google integrations not installed. Cannot run test.")
                return
        
        print("Analyzing inbox insights...")
        insights = brain.get_inbox_insights(limit=5)
        
        if "error" in insights:
            print(f"[FAIL] Insight analysis failed: {insights['error']}")
            sys.exit(1)
            
        print("[OK] Insights generated:")
        print(json.dumps(insights, indent=2))
        
        if insights.get("summaries"):
            print(f"[OK] Classified {len(insights['summaries'])} messages.")
        else:
            print("[FAIL] No summaries returned.")
            sys.exit(1)
            
        print("\n=== Gmail Insights Self-Test PASSED ===")
        
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
