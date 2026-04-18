import time
import json
import os
import csv
from datetime import datetime
from jarvis_ai.core.brain import Brain

class StressTester:
    def __init__(self, db_name="stress_test.db"):
        self.db_name = db_name
        if os.path.exists(self.db_name):
            try: os.remove(self.db_name)
            except: pass
            
        self.config = {"dev_mode": True}
        self.brain = Brain(self.config)
        self.brain.scheduler.memory_engine.db_path = self.db_name
        self.brain.scheduler.memory_engine._init_db()
        
        # Reports
        self.weight_history = []
        self.risk_history = []
        self.meta_goal_counts = []
        self.suppression_events = []
        
    def log_state(self, cycle, note=""):
        weights = {
            'cycle': cycle,
            'wp': float(self.brain.scheduler.memory_engine.get_setting('weight_priority', 2.0)),
            'wu': float(self.brain.scheduler.memory_engine.get_setting('weight_urgency', 1.0)),
            'wf': float(self.brain.scheduler.memory_engine.get_setting('weight_failure', 1.0)),
            'risk': self.brain.governance.get_risk_index(),
            'pressure': self.brain.governance.get_resource_pressure(),
            'note': note
        }
        self.weight_history.append(weights)
        
    def run_explosion_test(self):
        print("\n--- TEST 1: META-GOAL EXPLOSION ---")
        # Create 50 failures
        goal_data = self.brain.goal_engine.set_goal("Test Goal", tags=["failing_tag"])
        for i in range(50):
            self.brain.scheduler.memory_engine.record_execution(
                goal_data, success=False, duration=10
            )
        
        # Run strategic cycles
        meta_counts = []
        for i in range(10):
            self.brain.strategic.run_cycle(force=True)
            active = self.brain.goal_engine.list_goals()
            meta = [g for g in active if "system_improvement" in g.get('tags', [])]
            meta_counts.append(len(meta))
            print(f"Cycle {i}: Meta-goals = {len(meta)}")
            
        self.meta_goal_counts.append({"test": "Explosion", "counts": meta_counts})
        if meta_counts[-1] < 50:
            print("[OK] Meta-goal explosion throttled.")
        else:
            print("[WARNING] High meta-goal count detected.")

    def run_oscillation_test(self):
        print("\n--- TEST 2: WEIGHT OSCILLATION ---")
        goal_good = self.brain.goal_engine.set_goal("Good", tags=["reliable"])
        goal_bad = self.brain.goal_engine.set_goal("Bad", tags=["flakey"])
        
        for epoch in range(5):
            # Failure Epoch
            print(f"Epoch {epoch} [FAILURE]")
            for _ in range(20):
                self.brain.scheduler.memory_engine.record_execution(goal_bad, success=False)
            self.brain.strategic.run_cycle(force=True)
            self.log_state(epoch * 2, "Failure Epoch")
            
            # Success Epoch
            print(f"Epoch {epoch} [SUCCESS]")
            for _ in range(20):
                self.brain.scheduler.memory_engine.record_execution(goal_good, success=True)
            self.brain.strategic.run_cycle(force=True)
            self.log_state(epoch * 2 + 1, "Success Epoch")

    def run_deadlock_test(self):
        print("\n--- TEST 3: GOVERNANCE DEADLOCK ---")
        # User goals should never be suppressed, but conflict detection should fire
        for i in range(5):
            self.brain.goal_engine.set_goal(f"User Task {i}", tags=["maintenance"], priority=3)
            self.brain.goal_engine.update_steps(i+1, ["Use SystemTool"])
            self.brain.goal_engine.update_goal_status(i+1, "running")
            
        all_goals = self.brain.goal_engine.list_goals()
        for g in all_goals:
            self.brain.scheduler.calculate_score(g, all_goals)
            if g.get('conflicts'):
                print(f"Goal {g['id']} Conflicts: {len(g['conflicts'])}")
                self.suppression_events.append({"id": g['id'], "conflicts": len(g['conflicts'])})

    def run_risk_saturation(self):
        print("\n--- TEST 4: RISK SATURATION ---")
        # Flood failures to trigger Conservative Mode
        gd = self.brain.goal_engine.get_goal_by_id(1)
        for _ in range(100):
            self.brain.scheduler.memory_engine.record_execution(gd, success=False)
            
        risk = self.brain.governance.get_risk_index()
        print(f"Risk saturated: {risk}")
        self.brain.strategic.run_cycle(force=True) # Should log warning in StrategicEngine
        self.log_state(99, "Risk Saturation")

    def run_stability_test(self):
        print("\n--- TEST 5: LONG-RUN STABILITY ---")
        start_time = datetime.now()
        for i in range(500):
            # Mix of success/fail
            success = i % 3 != 0 
            self.brain.scheduler.memory_engine.record_execution(
                {"id": 1, "tags": ["stress"]}, success=success
            )
            if i % 50 == 0:
                self.brain.strategic.run_cycle(force=True)
                self.log_state(100+i, "Stability Run")
        
        duration = (datetime.now() - start_time).total_seconds()
        print(f"Simulated 500 cycles in {duration}s")

    def generate_report(self):
        print("\n=== STRESS TEST REPORT ===")
        print("\n[TIME-SERIES WEIGHT EVOLUTION]")
        header = "Cycle | Wp | Wu | Wf | Risk | Pressure | Note"
        print("-" * len(header))
        print(header)
        for w in self.weight_history:
            print(f"{w['cycle']:5} | {w['wp']:.1f} | {w['wu']:.1f} | {w['wf']:.1f} | {w['risk']:4.1f} | {w['pressure']:.2f} | {w['note']}")

        with open('stress_evidence.json', 'w') as f:
            json.dump({
                "weights": self.weight_history,
                "meta_goals": self.meta_goal_counts,
                "suppression": self.suppression_events
            }, f, indent=2)
        print("\nStructured evidence saved to stress_evidence.json")

if __name__ == "__main__":
    tester = StressTester()
    tester.run_explosion_test()
    tester.run_oscillation_test()
    tester.run_deadlock_test()
    tester.run_risk_saturation()
    tester.run_stability_test()
    tester.generate_report()
