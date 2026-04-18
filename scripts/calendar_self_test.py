"""
Calendar Integration Self-Test.
Runs only if google_token.json exists.
"""
import os
import sys
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain

def main():
    print("=== Jarvis AI: Calendar Self-Test ===")
    token_file = "storage/google_token.json"
    
    if not os.path.exists(token_file):
        print(f"[SKIPPED] {token_file} not found. Run scripts/google_oauth_setup.py first.")
        return

    try:
        brain = Brain({})
        print("Fetching upcoming events...")
        events = brain.calendar.list_events(limit=5)
        print(f"[OK] Found {len(events)} events.")
        for event in events:
            start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date'))
            print(f"  - {start}: {event.get('summary')}")
            
        print("\nProposing a test event (Approval Workflow)...")
        start_time = (datetime.utcnow() + timedelta(days=1)).isoformat() + 'Z'
        payload = {
            "title": "Jarvis Test Meeting",
            "start": start_time,
            "description": "Verification of approval workflow"
        }
        action_id = brain.propose_action('calendar_create_event', payload)
        print(f"[OK] Action proposed with ID: {action_id}")
        
        print(f"\nVerifying pending action {action_id} exists...")
        action = brain.memory_engine.get_pending_action(action_id)
        if action and action['status'] == 'pending':
            print("[OK] Pending action found in database.")
        else:
            print("[FAIL] Pending action not found or has wrong status.")
            sys.exit(1)
            
        print("\n=== Calendar Self-Test PASSED ===")
        
    except Exception as e:
        print(f"[ERROR] Calendar test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
