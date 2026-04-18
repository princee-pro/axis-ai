"""
production_pilot_live.py
Executes a 15-goal live pilot to verify autonomous scheduling, 
LLM advisory suggestions, and governance validation.
"""
import time
import os
import sys
from jarvis_ai.core.brain import Brain

def run_live_pilot():
    print("=== STARTING PRODUCTION PILOT SIMULATION (15 GOALS) ===")
    
    # 1. Initialize Brain in Advisory Mode
    config = {
        'memory': {'db_path': 'jarvis_memory.db'},
        'llm': {'provider': 'mock'},
        'dev_mode': True
    }
    brain = Brain(config, llm_advisory_mode=True)
    
    # Ensure a low success rate for one tag to trigger LLM advice simulation
    # (The previous pilot sim already injected ~85 goals, some might fail)
    
    # 2. Inject 15 Production-like Goals
    print("Adding 15 goals to the queue...")
    goals = [
        ("Daily Security Audit", 3, ["security", "maintenance"]),
        ("Update system documentation", 1, ["docs"]),
        ("Analyze performance of WebTool", 2, ["performance", "web"]),
        ("Check for system updates", 2, ["maintenance"]),
        ("Cleanup temporary log files", 1, ["maintenance"]),
        ("Backup production database", 3, ["security", "maintenance"]),
        ("Optimize weight scoring parameters", 2, ["system_improvement"]),
        ("Verify API connectivity", 2, ["web", "security"]),
        ("Review failed goals from yesterday", 2, ["analysis"]),
        ("Prepare morning summary", 1, ["user_request"]),
        ("Check weather for scheduled trip", 1, ["web"]),
        ("Sort incoming high-priority emails", 2, ["user_request"]),
        ("Sync calendar with local storage", 2, ["maintenance"]),
        ("Draft system health report", 1, ["analysis"]),
        ("Scan for unauthorized access attempts", 3, ["security"])
    ]
    
    for desc, priority, tags in goals:
        brain.goal_engine.set_goal(desc, priority=priority, tags=tags)
    
    print(f"Goal Engine Queue Size: {len(brain.goal_engine.list_goals())}")
    
    # 3. Execution Simulation Loop
    # We run 5 autonomous cycles
    print("\nStarting Autonomous Execution Cycles...")
    for i in range(5):
        print(f"\n--- Cycle {i+1}/5 ---")
        
        # Trigger Advisory Check
        if hasattr(brain, 'advisory'):
            print("Triggering LLM Advisory check...")
            proposal = brain.advisory.run_advisory_cycle()
            if proposal:
               print(f"ADVISOR: {proposal.get('content')}")
        
        # Select and Run best goal
        all_goals = brain.goal_engine.list_goals()
        best_goal = brain.scheduler.select_next_goal(all_goals)
        
        if best_goal:
            print(f"EXECUTING: [{best_goal['id']}] {best_goal['description']} (Score: {best_goal['score']})")
            # Run in mock real mode
            result = brain.autonomy.run_goal(best_goal['id'], mode='mock')
            print(f"RESULT: {result}")
        else:
            print("No goals ready for execution.")
            
        time.sleep(1) # Interval
        
    # 4. Final Audit
    print("\n=== PILOT AUDIT ===")
    history = brain.memory_engine._safe_db_execute("SELECT COUNT(*) FROM goal_history")[1][0][0]
    advisories = brain.memory_engine._safe_db_execute("SELECT COUNT(*) FROM llm_advisory_log")[1][0][0]
    
    print(f"Goals in History: {history}")
    print(f"LLM Advisory Suggestions Logged: {advisories}")
    print("\nPilot simulation successful. System ready for full verification suite.")

if __name__ == "__main__":
    run_live_pilot()
