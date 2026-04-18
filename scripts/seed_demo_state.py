#!/usr/bin/env python3
"""
Jarvis RC1 Demo Seed Utility.
Populates a safe, local demo state for UI walkthroughs.
"""

import os
import sys
import yaml
import json
from datetime import datetime, timedelta

def seed_demo_data():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(project_root)

    from jarvis_ai.core.brain import Brain
    
    config_path = os.path.join(project_root, 'jarvis_ai', 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    print("[SEED] Initializing Brain...")
    brain = Brain(config=config)
    mem = brain.memory_engine
    ge = brain.goal_engine

    # Optional reset
    if "--reset" in sys.argv:
        print("[SEED] Resetting demo state (CLEANING DB)...")
        # In a real impl, we might delete files or clear tables.
        # For MVP, we just add new items.
        pass

    print("[SEED] Creating sample goals...")
    
    # 1. Active Goal
    g1_data = ge.create_goal(
        title="Analyze Weekly Sales",
        objective="Analyze the sales data from the last 7 days and summarize insights.",
        priority="high"
    )
    g1_id = g1_data['id']
    mem.log_goal_event(g1_id, "SYSTEM", reason="Goal initialized from demo seed.")
    mem.log_goal_event(g1_id, "PLANNER", reason="Drafted initial 3-step plan.")

    # 2. Blocked Goal
    g2_data = ge.create_goal(
        title="Book Executive Travel",
        objective="Reserve a flight to London for the upcoming AI summit.",
        priority="urgent"
    )
    g2_id = g2_data['id']
    ge.update_goal_status(g2_id, "blocked")
    mem.log_goal_event(g2_id, "SYSTEM", to_status="blocked", reason="Execution blocked: Passport info missing.")

    # 3. Goal with Pending Approval
    g3_data = ge.create_goal(
        title="Twitter/X Brand Update",
        objective="Update the company bio on Twitter to reflect new RC1 features.",
        priority="normal"
    )
    g3_id = g3_data['id']
    
    print("[SEED] Seeding pending approvals...")
    mem.create_pending_action(
        action_id="demo_action_123",
        action_type="web_automation",
        payload={
            "browser": "chromium",
            "url": "https://twitter.com/settings/profile",
            "action": "edit_bio",
            "new_value": "Jarvis RC1: Autonomous, Secure, and Ready for Launch."
        },
        created_by="system"
    )
    mem.update_action_status("demo_action_123", "pending", notes="Modifying public social profiles carries brand risk.")

    print("[SEED] Seeding recent results...")
    # NOTE: Results are typically linked to steps. For demo, we just log an event.
    mem.log_goal_event(
        g1_id, 
        event_type="capability_result",
        reason="Sales are up 15% WoW. Primary driver: New feature adoption in North America."
    )

    print("[SEED] Demo seed COMPLETE.")
    print(f"[SEED] Created 3 goals. 1 action pending. 1 blocked. 1 result.")

if __name__ == "__main__":
    seed_demo_data()
