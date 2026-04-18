"""
Safety Core.
Handles user confirmation and logging for real execution commands.
"""
import logging
import os
import sys

# Configure Real Execution Logger
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'real_execution.log')

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class SafetyManager:
    def __init__(self):
        pass

    def ask_confirmation(self, action_description):
        """
        Ask user for manual confirmation before executing a risky action.
        """
        print(f"\n[!!!] REAL ACTION REQUESTED: {action_description}")
        print("[!!!] Are you sure you want to proceed? (yes/no)")
        
        # In a real CLI env, we use input().
        # For tests where stdin might not be available, we default to False unless mocked.
        try:
            choice = input("> ").strip().lower()
            if choice in ['yes', 'y']:
                self.log_action(action_description, "APPROVED")
                return True
            else:
                print("[!] Action DENIED by user.")
                self.log_action(action_description, "DENIED")
                return False
        except Exception as e:
            # Fallback for non-interactive environments
            print(f"[!] Input error: {e}. Defaulting to DENIED.")
            return False

    def log_action(self, action, status):
        """
        Log the action attempt.
        """
        logging.info(f"Action: {action} | Status: {status}")
