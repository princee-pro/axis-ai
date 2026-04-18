"""
Gmail Integration Self-Test.
Runs only if google_token.json exists.
"""
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain

def main():
    print("=== Jarvis AI: Gmail Self-Test ===")
    token_file = "storage/google_token.json"
    
    if not os.path.exists(token_file):
        print(f"[SKIPPED] {token_file} not found. Run scripts/google_oauth_setup.py first.")
        return

    try:
        brain = Brain({})
        print("Fetching inbox...")
        messages = brain.gmail.list_messages(limit=3)
        print(f"[OK] Found {len(messages)} messages.")
        for msg in messages:
            print(f"  - [{msg['id']}] From: {msg.get('from')} Subject: {msg.get('subject')}")
            
        print("\nCreating a test draft...")
        draft = brain.gmail.create_draft(to="test@example.com", subject="Jarvis Self-Test", body="This is a test draft.")
        print(f"[OK] Draft created with ID: {draft['id']}")
        
        print("\n=== Gmail Self-Test PASSED ===")
        
    except Exception as e:
        print(f"[ERROR] Gmail test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
