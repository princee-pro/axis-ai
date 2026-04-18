"""
Demo: Continuous Intelligence & Adaptive Learning Layer.
Simulates a series of goal executions to demonstrate how Jarvis learns from history.
"""
import time
import os
import sys

# Add project root
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from jarvis_ai.core.brain import Brain
from jarvis_ai.core.scheduler import GoalScheduler

def run_demo():
    print("=== JARVIS ADAPTIVE LEARNING DEMO ===")
    
    # 1. Setup Brain with a specific test DB
    db_path = "demo_learning.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    config = {'llm': {'provider': 'mock'}}
    brain = Brain(config)
    # Re-init scheduler with demo db
    brain.scheduler = GoalScheduler(db_path=db_path)

    print("\n[1] Initial State: No History")
    goal1 = brain.think("Add a goal: System backup tags: system, maintenance")
    print(f"Goal 1 Score: {brain.goal_engine.list_goals()[0]['score']} (Learning Adj: 0)")

    print("\n[2] Simulating Failures in 'system' category...")
    # Inject failure history directly into DB for speed of demo
    for _ in range(5):
        brain.scheduler.memory_engine.record_execution(
            {'id': 99, 'description': 'Fail', 'tags': ['system']},
            success=False
        )

    print("\n[3] Adding new 'system' goal. Expecting penalty.")
    brain.think("Add a goal: Clean logs tags: system")
    # Goal 2 should have a lower score due to failure penalty
    new_goals = brain.goal_engine.list_goals()
    g2_data = [g for g in new_goals if "clean logs" in g['description'].lower()][-1]
    print(f"Goal 2 Score: {g2_data['score']} (Learning Adj: {g2_data['learning_adjustment']})")

    print("\n[4] Simulating Success in 'web' category...")
    for _ in range(5):
        brain.scheduler.memory_engine.record_execution(
            {'id': 100, 'description': 'Success', 'tags': ['web']},
            success=True
        )

    print("\n[5] Adding new 'web' goal. Expecting boost.")
    brain.think("Add a goal: Search for news tags: web")
    g3_data = [g for g in brain.goal_engine.list_goals() if "search for news" in g['description'].lower()][-1]
    print(f"Goal 3 Score: {g3_data['score']} (Learning Adj: {g3_data['learning_adjustment']})")

    print("\n[6] Simulating Repeated Patterns...")
    for _ in range(3):
        brain.scheduler.memory_engine.record_execution(
            {'id': 101, 'description': 'Monthly Report', 'tags': ['office']},
            success=True
        )
    
    analytics = brain.scheduler.memory_engine.get_analytics()
    if analytics['repeated_patterns']:
        print(f"Found Pattern: {analytics['repeated_patterns'][0]['description']} (Suggested for automation)")

    print("\nDemo Complete! Run 'mobile/server.py' (pointing to demo_learning.db) to see stats in dashboard.")

if __name__ == "__main__":
    run_demo()
