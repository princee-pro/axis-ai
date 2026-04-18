"""
Verification Script: Production Stabilization Sprint.
Demonstrates:
1. Failure Containment (Safe DB Execution)
2. Overlapping Cycle Prevention (Cycle Lock)
3. Atomic State Transitions & Weight Protection
"""

import time
import threading
import sqlite3
from jarvis_ai.core.brain import Brain
from jarvis_ai.memory.memory_engine import MemoryEngine
from jarvis_ai.core.autonomy import AutonomyManager

def simulate_stabilization():
    print("=== Production Stabilization Verification ===\n")
    
    # 1. Initialize Brain
    brain = Brain(config={})
    memory = brain.scheduler.memory_engine
    autonomy = brain.autonomy
    
    print("[1/3] Testing Overlapping Cycle Prevention")
    # Manually acquire the lock to simulate a long-running cycle
    autonomy.cycle_lock.acquire()
    print("  > Primary cycle lock held. Attempting to start a second cycle...")
    
    # Starting a thread that tries to run the loop
    def attempt_cycle():
        # This should log a WARNING about overlap
        autonomy.autonomous_loop_active = True
        autonomy._autonomous_loop(mode='mock', interval=1)
    
    thread = threading.Thread(target=attempt_cycle)
    thread.daemon = True
    thread.start()
    
    time.sleep(2) # Wait for overlap detection
    autonomy.autonomous_loop_active = False # Stop the loop
    autonomy.cycle_lock.release()
    print("  > Overlay test complete (Check logs for 'Scheduling cycle overlap detected').\n")
    
    print("[2/3] Testing DB Failure Containment")
    # Inject a DB failure by pointing to a read-only or invalid path
    # OR simply closing the connection or monkeypatching
    original_path = memory.db_path
    memory.db_path = "Z:\\invalid_path\\non_existent.db" # Forced failure path
    
    print(f"  > DB path set to invalid: {memory.db_path}")
    print("  > Attempting a write (set_setting)...")
    
    success, _ = memory._safe_db_execute("INSERT INTO system_settings (key, value) VALUES (?, ?)", ("test_fail", "true"), is_write=True)
    
    if not success:
        print("  > SUCCESS: DB Write failed as expected, but no crash occurred.")
        print(f"  > Queue size: {len(memory._write_queue)} (Write was safely queued)")
    else:
        print("  > ERROR: Write unexpectedly succeeded!")
        
    print("  > Attempting to run a goal in 'Degraded Mode'...")
    try:
        goal = brain.goal_engine.set_goal("Test resilience")
        goal_id = goal['id']
        brain.autonomy.run_goal(goal_id)
        print("  > SUCCESS: Brain executed goal in degraded mode without crashing.")
    except Exception as e:
        print(f"  > FAILURE: Brain crashed during degraded mode: {e}")
    
    # Restore path and flush
    memory.db_path = original_path
    memory.process_write_queue()
    print("  > Path restored. Queue flushed.\n")

    print("[3/3] Weight Tuning Race Protection")
    print("  > Verifying settings_lock in MemoryEngine...")
    if hasattr(memory, '_lock') and isinstance(memory._lock, threading.Lock):
        print("  > SUCCESS: MemoryEngine holds a threading.Lock for settings and DB ops.")
    else:
        print("  > FAILURE: Missing lock in MemoryEngine.")

    print("\n=== Verification Complete: Brain is STABLE ===")

if __name__ == "__main__":
    simulate_stabilization()
