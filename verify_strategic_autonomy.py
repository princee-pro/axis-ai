import os
import sys
import time
import json
import sqlite3
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from jarvis_ai.core.brain import Brain

def verify_strategic_autonomy():
    print("=== JARVIS STRATEGIC AUTONOMY VERIFICATION ===")
    
    # 1. Initialize Brain with SQLite Memory
    config = {'llm': {'provider': 'mock'}}
    brain = Brain(config)
    memory = brain.scheduler.memory_engine
    
    # Reset DB for clean test
    db_path = memory.db_path
    if hasattr(memory, 'close'): memory.close()
    
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except PermissionError:
            print("Warning: Could not remove DB file, clearing tables instead.")
            # Fallback: clear tables
            with sqlite3.connect(db_path) as conn:
                conn.execute("DELETE FROM goal_history")
                conn.execute("DELETE FROM system_settings")
    
    memory._init_db()
    
    print("\n[PHASE 1] Initial State & Baseline Weights")
    wp = memory.get_setting('weight_priority')
    wf = memory.get_setting('weight_failure')
    print(f"Initial Weight Priority: {wp}")
    print(f"Initial Weight Failure: {wf}")
    print(f"Initial Health Index: {brain.strategic.get_health_index()}%")

    # 2. Induce Tag failure bias (Strategic Meta-Goal Trigger)
    print("\n[PHASE 2] Inducing Tag Failure Bias ('flakey_task')")
    for _ in range(5):
        memory.record_execution(
            {'id': 100, 'description': 'Flakey Task', 'tags': ['flakey_task']},
            success=False,
            duration=1.0
        )
    
    # Run Strategic Cycle
    brain.strategic.run_cycle(force=True)
    
    goals = brain.goal_engine.list_goals()
    meta_goals = [g for g in goals if 'system_improvement' in g.get('tags', [])]
    
    print(f"Generated Meta-Goals: {len(meta_goals)}")
    for mg in meta_goals:
        print(f" - {mg['description']} (Reason: {mg.get('reason', 'N/A')})")
    
    if any("Improve strategy for flakey_task" in mg['description'] for mg in meta_goals):
        print("[OK] SUCCESS: Meta-goal generated for high failure tag.")
    else:
        print("[FAIL] FAILURE: No meta-goal generated for high failure tag.")

    # 3. Weight Tuning Test (Low Global Success -> Increase Failure Penalty)
    print("\n[PHASE 3] Weight Self-Tuning (Low Success)")
    wf_before = float(memory.get_setting('weight_failure'))
    
    # We already have 5 failures and 0 successes
    brain.strategic.run_cycle(force=True)
    
    wf_after = float(memory.get_setting('weight_failure'))
    print(f"Weight Failure: {wf_before} -> {wf_after}")
    
    if wf_after > wf_before:
        print("[OK] SUCCESS: Failure weight increased due to low success rate.")
    else:
        print("[FAIL] FAILURE: Failure weight did not increase.")
        
    # 4. Success-based Tuning (High Success -> Increase Priority Weight)
    print("\n[PHASE 4] Weight Self-Tuning (High Success)")
    for _ in range(50):
        memory.record_execution(
            {'id': 200, 'description': 'Solid Task', 'tags': ['reliable']},
            success=True,
            duration=0.5
        )
    
    wp_before = float(memory.get_setting('weight_priority'))
    brain.strategic.run_cycle(force=True)
    wp_after = float(memory.get_setting('weight_priority'))
    
    print(f"Weight Priority: {wp_before} -> {wp_after}")
    if wp_after > wp_before:
        print("[OK] SUCCESS: Priority weight increased due to high success rate.")
    else:
        print("[FAIL] FAILURE: Priority weight did not increase.")

    # 5. Adaptive Retry Strategy Verification
    print("\n[PHASE 5] Adaptive Retry Strategy")
    # For flakey_task (0% success), backoff should be high
    # For reliable (100% success), backoff should be low
    
    flakey_goal = {'id': 301, 'tags': ['flakey_task'], 'retry_count': 1, 'last_failure': datetime.now().isoformat()}
    reliable_goal = {'id': 302, 'tags': ['reliable'], 'retry_count': 1, 'last_failure': datetime.now().isoformat()}
    
    backoff_flakey = brain.scheduler._get_adaptive_backoff(flakey_goal)
    backoff_reliable = brain.scheduler._get_adaptive_backoff(reliable_goal)
    
    print(f"Backoff for High-Failure Tag: {backoff_flakey}s")
    print(f"Backoff for High-Success Tag: {backoff_reliable}s")
    
    if backoff_flakey > backoff_reliable:
        print("[OK] SUCCESS: Adaptive backoff correctly differentiates based on tag history.")
    else:
        print("[FAIL] FAILURE: Backoff durations are not correctly adapted.")

    # 6. System Health Index
    health = brain.strategic.get_health_index()
    print(f"\nFinal System Health Index: {health}%")
    if health < 100:
        print("[OK] SUCCESS: Health index reflects past failures.")
    else:
        print("[FAIL] FAILURE: Health index is stuck at 100%.")

    print("\n=== VERIFICATION COMPLETE ===")

if __name__ == "__main__":
    verify_strategic_autonomy()
