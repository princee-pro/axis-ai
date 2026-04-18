import sys
import os
import json
import urllib.request
import urllib.error
import time
import threading

# Add project root to path (placeholder mechanism)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class MobileClient:
    def __init__(self, server_url="http://localhost:8000"):
        self.server_url = server_url
        self.auth_token = "jarvis_secret_123"
        self.polling_active = False
        self.poll_thread = None
        print("Mobile Client Initialized.")

    def send_command(self, command):
        """
        Send a command to Jarvis Server.
        """
        print(f"[CLIENT] Sending command: {command}")
        
        data = json.dumps({
            "command": command,
            "token": self.auth_token
        }).encode('utf-8')

        req = urllib.request.Request(self.server_url, data=data, headers={'Content-Type': 'application/json'})
        
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                print(f"[CLIENT] Response: {result.get('response')}")
                return result.get('response')
        except urllib.error.HTTPError as error:
            error.close()
            print(f"[CLIENT] Error connecting to server: {error}")
            return f"Error: {error}"
        except urllib.error.URLError as e:
            print(f"[CLIENT] Error connecting to server: {e}")
            return f"Error: {e}"

    def check_status(self):
        """
        Poll server for status updates.
        """
        req = urllib.request.Request(f"{self.server_url}/status")
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result
        except urllib.error.HTTPError as error:
            error.close()
            print(f"[CLIENT] Error checking status: {error}")
            return None
        except urllib.error.URLError as e:
            print(f"[CLIENT] Error checking status: {e}")
            return None

    def display_status(self):
        """
        Display current status and logs.
        """
        status = self.check_status()
        if status:
            print("\n=== JARVIS STATUS ===")
            print(f"Active Goals: {len(status.get('active_goals', []))}")
            print(f"Autonomous Loop: {'ACTIVE' if status.get('autonomous_loop_active') else 'INACTIVE'}")
            
            for goal in status.get('active_goals', []):
                priority_label = "🔴 CRITICAL" if goal['priority'] == 3 else "🟠 HIGH" if goal['priority'] == 2 else "🟢 NORMAL"
                chain_info = f" → Goal {goal['next_goal_id']}" if goal.get('next_goal_id') else ""
                print(f"  {priority_label} [{goal['id']}] {goal['description']} ({goal['status']}, {goal['progress']}%){chain_info}")
            
            print(f"\nRecent Logs ({len(status.get('recent_logs', []))} entries):")
            for log in status.get('recent_logs', [])[-5:]:  # Show last 5 logs
                print(f"  {log}")
            print("=====================\n")
        else:
            print("[CLIENT] Could not retrieve status.")
    
    def start_autonomous_loop(self, mode='mock'):
        """Start the autonomous execution loop on the server."""
        print(f"[CLIENT] Starting autonomous loop (mode: {mode})...")
        data = json.dumps({
            "mode": mode,
            "token": self.auth_token
        }).encode('utf-8')
        
        req = urllib.request.Request(f"{self.server_url}/autonomous/start", data=data, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                print(f"[CLIENT] {result.get('response')}")
                return result.get('response')
        except urllib.error.HTTPError as error:
            error.close()
            print(f"[CLIENT] Error: {error}")
            return f"Error: {error}"
        except urllib.error.URLError as e:
            print(f"[CLIENT] Error: {e}")
            return f"Error: {e}"
    
    def stop_autonomous_loop(self):
        """Stop the autonomous execution loop on the server."""
        print("[CLIENT] Stopping autonomous loop...")
        data = json.dumps({
            "token": self.auth_token
        }).encode('utf-8')
        
        req = urllib.request.Request(f"{self.server_url}/autonomous/stop", data=data, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                print(f"[CLIENT] {result.get('response')}")
                return result.get('response')
        except urllib.error.HTTPError as error:
            error.close()
            print(f"[CLIENT] Error: {error}")
            return f"Error: {error}"
        except urllib.error.URLError as e:
            print(f"[CLIENT] Error: {e}")
            return f"Error: {e}"

    def start_polling(self, interval=2, callback=None):
        """
        Start real-time status polling.
        
        Args:
            interval: Seconds between polls
            callback: Optional callback function(status_data)
        """
        if self.polling_active:
            print("[CLIENT] Polling already active.")
            return
        
        self.polling_active = True
        self.poll_thread = threading.Thread(target=self._poll_loop, args=(interval, callback))
        self.poll_thread.daemon = True
        self.poll_thread.start()
        print(f"[CLIENT] Started real-time polling (interval: {interval}s)")
    
    def _poll_loop(self, interval, callback):
        """Internal polling loop."""
        while self.polling_active:
            status = self.check_status()
            if status:
                if callback:
                    callback(status)
                else:
                    # Default: just display
                    self.display_status()
            time.sleep(interval)
    
    def stop_polling(self):
        """Stop real-time polling."""
        self.polling_active = False
        print("[CLIENT] Stopped polling.")

    def receive_notification(self, message):
        """
        Simulate receiving a notification.
        """
        print(f"[CLIENT] Received notification: {message}")

if __name__ == "__main__":
    # Test script
    client = MobileClient()
    
    print("\n--- Adding goals ---")
    client.send_command("Add a goal: Test mobile integration high priority")
    client.send_command("Add a goal: Second goal normal")
    
    print("\n--- Listing goals ---")
    client.send_command("List my goals")
    
    print("\n--- Checking status ---")
    client.display_status()
    
    print("\n--- Running goal autonomously ---")
    client.send_command("Run goal 1 in autonomous mode")
    
    time.sleep(1)  # Wait for execution
    
    print("\n--- Final status ---")
    client.display_status()
