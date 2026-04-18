#!/usr/bin/env python3
"""
Jarvis RC1 End-to-End Acceptance Test.
Automates full-stack journeys using Playwright.
"""

import os
import sys
import time
import subprocess
from playwright.sync_api import sync_playwright

# Configuration
TEST_HOST = "127.0.0.1"
TEST_PORT = 8000
BASE_URL = f"http://{TEST_HOST}:{TEST_PORT}/ui"
TOKEN = os.environ.get("JARVIS_SECRET_TOKEN", "mock_token")

def run_e2e():
    print("--- Jarvis RC1 E2E Acceptance Test ---")
    
    with sync_playwright() as p:
        # 1. Launch Browser
        print("[STEP 1] Launching Browser...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 2. Open UI
        print("[STEP 2] Navigating to Dashboard...")
        try:
            page.goto(BASE_URL, timeout=15000)
        except Exception as e:
            print(f"[FAIL] Dashboard unreachable at {BASE_URL}. Error: {e}")
            browser.close()
            return

        # 3. Auth Flow
        print("[STEP 3] Testing Authentication Flow...")
        # Fill token and login
        page.select_option("#auth-mode", "owner")
        page.fill("#auth-token", TOKEN)
        page.click("#login-btn")

        # Wait for app visibility
        page.wait_for_selector("#app:not(.hidden)", timeout=5000)
        print("  [PASS] Login successful, app view visible")

        # 4. Verify Identity
        print("[STEP 4] Verifying Context (whoami)...")
        page.wait_for_selector("#whoami-info:has-text('owner')", timeout=5000)
        print("  [PASS] Role identified as 'owner'")

        # 5. Check Overview
        print("[STEP 5] Checking Overview Stats...")
        page.click("[data-page='overview']")
        page.wait_for_selector("#stat-active-goals:not(:has-text('-'))", timeout=5000)
        print("  [PASS] Overview stats loaded")

        # 6. Goal Creation Journey
        print("[STEP 6] Testing Goal Creation...")
        page.click("[data-page='goals']")
        page.click("#new-goal-btn")
        page.fill("#goal-title", "E2E Test Goal")
        page.fill("#goal-objective", "Verify RC1 E2E stability via automated test.")
        page.click("#goal-submit-btn")
        
        # Verify goal appears in list
        page.wait_for_selector(".item-card:has-text('E2E Test Goal')", timeout=20000)
        print("  [PASS] Goal created and visible in list")

        # 7. Approvals Journey (Smoke)
        print("[STEP 7] Checking Approvals Tab...")
        page.click("[data-page='approvals']")
        # Even if empty, it should render cleanly
        page.wait_for_selector("#approvals-list", timeout=5000)
        print("  [PASS] Approvals view rendered")

        # 8. Voice Text Fallback
        print("[STEP 8] Testing Voice Text Fallback...")
        page.click("[data-page='voice']")
        page.fill("#voice-text-input", "Hello Jarvis, run RC1 diagnostics.")
        page.click("#voice-send-btn")
        
        # Wait for response in chat history
        page.wait_for_selector(".chat-msg .msg-jarvis", timeout=10000)
        print("  [PASS] Chat response received")

        # 9. Cleanup
        print("[STEP 9] Logout...")
        page.click("#logout-btn")
        page.wait_for_selector("#auth-overlay:not(.hidden)", timeout=5000)
        print("  [PASS] Logout successful")

        browser.close()
        print("\n--- E2E TEST RESULT: ALL JOURNEYS PASSED ---")

if __name__ == "__main__":
    run_e2e()
