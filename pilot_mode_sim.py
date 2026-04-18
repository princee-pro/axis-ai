import os
import sys
import sqlite3
import json
import random
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.join(os.getcwd(), 'jarvis_ai'))
from jarvis_ai.core.brain import Brain

def simulate_pilot_workload(days=7):
    print(f"Starting {days}-Day Pilot Mode Simulation...")
    
    # Initialize Brain (mock tools for simulation safety)
    brain = Brain({"dev_mode": True})
    memory = brain.scheduler.memory_engine
    db_path = memory.db_path
    
    # Clear existing history for clean simulation
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM goal_history")
        conn.commit()

    start_date = datetime.now() - timedelta(days=days)
    total_goals = 0
    
    tags_pool = ["research", "system_improvement", "automation", "optimization", "user_request"]
    
    # Simulation Logic
    for day in range(days):
        current_day = start_date + timedelta(days=day)
        # 10-15 goals per day
        daily_count = random.randint(10, 15)
        
        for _ in range(daily_count):
            total_goals += 1
            is_meta = random.random() < 0.3 # 30% meta goals
            tags = [random.choice(tags_pool)]
            if is_meta: tags.append("system_improvement")
            
            success = random.random() < 0.85 # 85% success rate
            duration = random.randint(30, 600)
            deadline_missed = random.random() < 0.1 # 10% deadline miss
            retry_count = random.randint(0, 2) if not success else 0
            
            # Decision Trace Simulation
            trace = {
                "BaseScore": round(random.uniform(50, 100), 2),
                "Components": {"Priority": 2.0, "Urgency": 1.0, "Pressure": 0.5, "Penalty": 0},
                "FinalScore": round(random.uniform(40, 120), 2),
                "RiskIndex": round(random.uniform(10, 40), 1),
                "Timestamp": current_day.isoformat()
            }
            
            # Inject into DB directly for speed
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO goal_history (
                        goal_id, description, tags, created_at, completed_at, 
                        duration_seconds, success, retry_count, deadline_missed,
                        decision_context, risk_at_execution, weights_at_execution
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    total_goals,
                    f"Simulated Goal {total_goals}",
                    ",".join(tags),
                    current_day.isoformat(),
                    (current_day + timedelta(seconds=duration)).isoformat(),
                    duration,
                    1 if success else 0,
                    retry_count,
                    1 if deadline_missed else 0,
                    json.dumps(trace),
                    trace['RiskIndex'],
                    json.dumps({"wp": 2.0, "wu": 1.0, "wd": 1.0, "wf": 1.0})
                ))
                conn.commit()

    print(f"Simulation Complete. Injected {total_goals} goal records.")
    
    # Fetch Metrics
    metrics = memory.get_pilot_metrics()
    
    # Generate Raw Metrics Table
    print("\n" + "="*50)
    print("PILOT MODE VERIFICATION - RAW METRICS TABLE")
    print("="*50)
    print(f"{'Metric':<25} | {'Value':<15}")
    print("-" * 50)
    print(f"{'Mean Time to Completion':<25} | {metrics['mttc']}s")
    print(f"{'Deadline Adherence':<25} | {metrics['deadline_adherence']}%")
    print(f"{'Retry Rate':<25} | {metrics['retry_rate']}%")
    print(f"{'Automation Adoption':<25} | {metrics['adoption_rate']}%")
    print("-" * 50)
    print(f"{'Total Processed':<25} | {total_goals} goals")
    print("="*50)

if __name__ == "__main__":
    simulate_pilot_workload()
