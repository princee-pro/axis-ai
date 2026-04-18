"""
Demo script to test dashboard with live data.
Run this after starting the server to populate goals for dashboard testing.
"""

import sys
import os
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.mobile.client_app.client_mock import MobileClient

def demo_dashboard():
    """Populate the server with sample goals for dashboard demo."""
    client = MobileClient()
    
    print("=" * 60)
    print("Jarvis Dashboard Demo")
    print("=" * 60)
    print("\nDashboard URL: file:///c:/Users/princ/OneDrive/Desktop/jarvis/jarvis_ai/mobile/dashboard.html")
    print("Server URL: http://localhost:8000/status")
    print("\nPopulating sample goals...\n")
    
    # Add goals with different priorities
    print("Adding goals...")
    client.send_command("Add a goal: Get weather for Kigali critical")
    time.sleep(0.5)
    
    client.send_command("Add a goal: Fetch latest tech news high priority")
    time.sleep(0.5)
    
    client.send_command("Add a goal: Get AAPL stock price high priority")
    time.sleep(0.5)
    
    client.send_command("Add a goal: Daily system backup normal")
    time.sleep(0.5)
    
    print("\n✅ 4 goals added!\n")
    
    # Start autonomous loop
    print("Starting autonomous execution loop...")
    result = client.start_autonomous_loop(mode='mock')
    print(f"Result: {result}")
    
    print("\n" + "=" * 60)
    print("Dashboard is now live with sample data!")
    print("=" * 60)
    print("\nOpen the dashboard in your browser to see:")
    print("  - Goals with different priorities (CRITICAL, HIGH, NORMAL)")
    print("  - Progress bars updating in real-time")
    print("  - Step execution status")
    print("  - Live logs panel")
    print("  - Autonomous loop status: ACTIVE (pulsing green)")
    print("\nThe dashboard auto-refreshes every 3 seconds.")
    print("\nTo stop the autonomous loop, run:")
    print("  client.stop_autonomous_loop()")
    print("=" * 60)

if __name__ == '__main__':
    demo_dashboard()
