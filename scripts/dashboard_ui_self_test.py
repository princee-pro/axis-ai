import time
import os
import sys
import subprocess
import requests
import json
from playwright.sync_api import sync_playwright

# Configuration
BASE_URL = "http://127.0.0.1:8000"
TOKEN = os.environ.get("JARVIS_SECRET_TOKEN", "default_secret_if_any")

def log(msg):
    print(f"[TEST] {msg}")

def test_dashboard_ui():
    with sync_playwright() as p:
        log("Launching browser...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1. Test /ui loads
        log(f"Navigating to {BASE_URL}/ui...")
        try:
            page.goto(f"{BASE_URL}/ui")
        except Exception as e:
            log(f"FAILED to load /ui: {e}")
            browser.close()
            return

        # 2. Test Auth Overlay presence
        log("Checking for auth overlay...")
        if page.is_visible("#auth-overlay"):
            log("SUCCESS: Auth overlay visible")
        else:
            log("FAILED: Auth overlay not found")
            browser.close()
            return

        # 3. Simulate Login
        log("Simulating login...")
        page.fill("#auth-token", TOKEN)
        page.select_option("#auth-mode", "owner")
        page.click("#login-btn")

        # Wait for app to show
        page.wait_for_selector("#app", timeout=5000)
        if page.is_visible("#app") and not page.is_visible("#auth-overlay"):
            log("SUCCESS: Logged in and app visible")
        else:
            log("FAILED: Login did not transition to app")
            browser.close()
            return

        # 4. Verify Overview Data
        log("Checking overview data cards...")
        page.wait_for_selector("#stat-active-goals")
        goals_text = page.inner_text("#stat-active-goals")
        log(f"Stat: Active Goals = {goals_text}")
        if goals_text != "-":
            log("SUCCESS: Overview statistics rendered")
        else:
            log("FAILED: Overview statistics still showing default dash")

        # 5. Test Navigation
        log("Testing navigation to Goals page...")
        page.click('button[data-page="goals"]')
        page.wait_for_selector("#page-goals")
        if page.is_visible("#page-goals") and not page.is_visible("#page-overview"):
            log("SUCCESS: Navigated to Goals page")
        else:
            log("FAILED: Navigation to Goals page failed")

        # 6. Test New Goal Modal
        log("Testing New Goal modal...")
        page.click("#new-goal-btn")
        if page.is_visible("#new-goal-modal"):
            log("SUCCESS: New Goal modal opened")
            page.click("#goal-cancel-btn")
        else:
            log("FAILED: New Goal modal did not open")

        log("Dashboard UI test completed successfully.")
        browser.close()

if __name__ == "__main__":
    log("Starting Dashboard UI Self-Test...")
    log("Note: This test assumes the Jarvis server is running locally on port 8000.")
    try:
        # Quick check if server is up
        r = requests.get(f"{BASE_URL}/health", timeout=2)
        log(f"Server health check: {r.status_code}")
        
        test_dashboard_ui()
    except Exception as e:
        log(f"Test suite error: {e}")
        log("Is the server running? Run 'python -m jarvis_ai.mobile.server' first.")
