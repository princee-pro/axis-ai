import time
import json
import os
from jarvis_ai.core.brain import Brain

def run_verification():
    print("=== JARVIS AI GOVERNANCE LAYER VERIFICATION ===")
    
    # Setup
    db_path = "jarvis_governance_test.db"
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except:
            pass
            
    config = {"dev_mode": True}
    brain = Brain(config)
    # Ensure we use the test DB
    brain.scheduler.memory_engine.db_path = db_path
    brain.scheduler.memory_engine._init_db()
    
    print("\n[PHASE 1] CONFLICT DETECTION")
    # Goal 1: Uses filesystem
    brain.goal_engine.set_goal("Backup system files", tags=["maintenance"], priority=1)
    brain.goal_engine.update_steps(1, ["Use SystemTool to copy files"])
    
    # Goal 2: Also uses filesystem
    brain.goal_engine.set_goal("Edit config files", tags=["maintenance"], priority=1)
    brain.goal_engine.update_steps(2, ["Use SystemTool to write config"])
    
    # Mark Goal 1 as running
    brain.goal_engine.update_goal_status(1, "running")
    
    # Check Goal 2 score (expect penalty/conflict)
    goal2_data = brain.goal_engine.get_goal_by_id(2)
    score_2 = brain.scheduler.calculate_score(goal2_data, brain.goal_engine.list_goals())
    
    if goal2_data.get('conflicts'):
        print(f"[OK] Conflict detected for Goal 2: {goal2_data['conflicts'][0]['type']}")
    else:
        print("[FAIL] No conflict detected for Goal 2")

    print("\n[PHASE 2] RESOURCE PRESSURE & COHERENCE")
    # Add many goals to increase pressure
    for i in range(3, 10):
        brain.goal_engine.set_goal(f"Intensive Research {i}", tags=["research"], priority=1)
        brain.goal_engine.update_steps(i, ["Use WebTool to search", "LLM Analysis"])
        brain.goal_engine.update_goal_status(i, "running")
        
    pressure = brain.governance.get_resource_pressure()
    print(f"Current Resource Pressure: {pressure}")
    
    # Check coherence of a new goal under pressure
    gid_low = brain.goal_engine.set_goal("Low priority task", priority=1).get('id')
    goal_low_data = brain.goal_engine.get_goal_by_id(gid_low)
    score_low = brain.scheduler.calculate_score(goal_low_data, brain.goal_engine.list_goals())
    print(f"Goal Coherence Modifier under pressure: {goal_low_data.get('coherence_modifier')}")
    
    if goal_low_data.get('coherence_modifier', 1.0) < 1.0:
        print("[OK] Coherence suppressed due to high pressure")
    else:
        print("[FAIL] Coherence not suppressed")

    print("\n[PHASE 3] RISK INDEX & CONSERVATIVE MODE")
    # Inject failures to increase Risk Index
    memory = brain.scheduler.memory_engine
    goal_data = brain.goal_engine.get_goal_by_id(1)
    for _ in range(10):
        memory.record_execution(goal_data, success=False, duration=10, deadline_missed=False)
        
    risk = brain.governance.get_risk_index()
    print(f"System Risk Index: {risk}")
    
    if risk > 30:
        print(f"[OK] Risk Index elevated (Risk: {risk})")
    else:
        print(f"[FAIL] Risk Index too low ({risk})")
        
    print("\n[PHASE 4] REDUNDANCY SUPPRESSION")
    # Goal 1 is completed
    brain.goal_engine.complete_goal(1)
    
    # New goal with same description (Meta-goal type)
    gid_redo = brain.goal_engine.set_goal("Backup system files", tags=["system_improvement"]).get('id')
    goal_redo_data = brain.goal_engine.get_goal_by_id(gid_redo)
    score_redo = brain.scheduler.calculate_score(goal_redo_data, brain.goal_engine.list_goals())
    
    print(f"Redundant Meta-goal Coherence: {goal_redo_data.get('coherence_modifier')}")
    if goal_redo_data.get('coherence_modifier', 1.0) < 0.5:
        print("[OK] Redundant improvement suppressed")
    else:
        print("[FAIL] Redundancy not detected")

    print("\n=== VERIFICATION COMPLETE ===")

if __name__ == "__main__":
    run_verification()
