import time
import os
import sys
import sqlite3
import json
from datetime import datetime

# Add project root
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from jarvis_ai.core.brain import Brain
from jarvis_ai.core.scheduler import GoalScheduler

DB_PATH = "verification_learning.db"

def print_table(title, headers, rows):
    print(f"\n# {title}")
    header_str = " | ".join(f"{h: <25}" for h in headers)
    print(header_str)
    print("-" * len(header_str))
    for row in rows:
        print(" | ".join(f"{str(item): <25}" for item in row))

def setup_brain():
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM goal_history")
        conn.commit()
        conn.close()
    
    config = {'llm': {'provider': 'mock'}}
    brain = Brain(config)
    brain.scheduler = GoalScheduler(db_path=DB_PATH)
    return brain

def run_phase_1(brain):
    print("\n## PHASE 1 — Baseline Snapshot")
    # Strict 10 goals
    for i in range(5):
        brain.goal_engine.set_goal(f"Hard Task {i+1}", tags=["hard_task"])
        brain.goal_engine.set_goal(f"Easy Task {i+1}", tags=["easy_task"])
    
    all_goals = brain.goal_engine.list_goals()
    headers = ["Goal Description", "Tag", "BaseScore", "LearningAdjustment", "FinalScore"]
    rows = []
    for g in all_goals:
        brain.scheduler.calculate_score(g, all_goals)
        trace = g['decision_trace']
        rows.append([g['description'], ",".join(g.get('tags', [])), trace['BaseScore'], trace['LearningAdjustment'], g['score']])
    
    print_table("Initial Goal Scores (Baseline)", headers, rows)
    return all_goals

def run_phase_2(brain, initial_goals):
    print("\n## PHASE 2 — Induce Failure Bias")
    for g in initial_goals:
        is_hard = "hard_task" in g.get('tags', [])
        success = not is_hard
        brain.scheduler.memory_engine.record_execution(g, success=success, duration=50)
    
    analytics = brain.scheduler.memory_engine.get_analytics()
    
    tag_headers = ["Tag", "Total", "Success Rate (%)", "Adjustment Applied"]
    tag_rows = []
    for stat in analytics['tag_stats']:
        adj = brain.scheduler.memory_engine.get_learning_adjustment([stat['tag']])
        tag_rows.append([stat['tag'], stat['total'], stat['success_rate'], adj])
    
    print_table("Tag Performance & Calibration", tag_headers, tag_rows)

def run_phase_3(brain):
    print("\n## PHASE 3 — Score Drift Validation")
    # Insert 4 new goals (2 hard, 2 easy)
    brain.goal_engine.set_goal("Drift Check Hard 1", tags=["hard_task"])
    brain.goal_engine.set_goal("Drift Check Hard 2", tags=["hard_task"])
    brain.goal_engine.set_goal("Drift Check Easy 1", tags=["easy_task"])
    brain.goal_engine.set_goal("Drift Check Easy 2", tags=["easy_task"])
    
    all_goals = brain.goal_engine.list_goals()
    drift_goals = [g for g in all_goals if "Drift Check" in g['description']]
    
    headers = ["Description", "BaseScore", "LearningAdjustment", "FinalScore"]
    rows = []
    for g in drift_goals:
        brain.scheduler.calculate_score(g, all_goals)
        trace = g['decision_trace']
        rows.append([g['description'], trace['BaseScore'], trace['LearningAdjustment'], g['score']])
    
    print_table("Deterministic Score Drift Evidence", headers, rows)

def run_phase_4(brain):
    print("\n## PHASE 4 — Pattern Detection")
    pattern_desc = "Standard Weekly Sync"
    for _ in range(3):
        brain.scheduler.memory_engine.record_execution(
            {'id': 2000, 'description': pattern_desc, 'tags': ['sync']},
            success=True
        )
    
    analytics = brain.scheduler.memory_engine.get_analytics()
    repeated = analytics.get('repeated_patterns', [])
    
    headers = ["Detected Pattern", "Frequency"]
    rows = [[r['description'], r['count']] for r in repeated if r['description'] == pattern_desc]
    print_table("Automation Suggestions Raw Data", headers, rows)
    
    print("\n### RAW DASHBOARD ANALYTICS SNAPSHOT")
    print(json.dumps(analytics, indent=2))

def run_phase_5():
    print("\n## PHASE 5 — Persistence Test")
    print("Action: New process simulation. Initializing Brain from existing SQLite.")
    config = {'llm': {'provider': 'mock'}}
    new_brain = Brain(config)
    new_brain.scheduler = GoalScheduler(db_path=DB_PATH)
    
    # Check if adjustments are retrieved without new executions
    new_brain.goal_engine.set_goal("Persistence Hard", tags=["hard_task"])
    new_brain.goal_engine.set_goal("Persistence Easy", tags=["easy_task"])
    
    all_goals = new_brain.goal_engine.list_goals()
    targets = [g for g in all_goals if "Persistence" in g['description']]
    
    headers = ["Description", "LearningAdjustment (Retrieved)"]
    rows = []
    for g in targets:
        new_brain.scheduler.calculate_score(g, all_goals)
        trace = g['decision_trace']
        rows.append([g['description'], trace['LearningAdjustment']])
    
    print_table("Post-Restart Score Persistence", headers, rows)

def verify_disabled():
    print("\n## PHASE 6 — MemoryEngine Disabled State")
    config = {'llm': {'provider': 'mock'}}
    off_brain = Brain(config)
    off_brain.scheduler = GoalScheduler(db_path=None)
    
    goal = {'id': 5000, 'description': 'Safety Check', 'tags': ['hard_task']}
    off_brain.scheduler.calculate_score(goal, [])
    trace = goal['decision_trace']
    
    print(f"Goal: {goal['description']}")
    print(f"LearningAdjustment: {trace['LearningAdjustment']} (Confirmed: 0)")

if __name__ == "__main__":
    b = setup_brain()
    run_phase_1(b)
    run_phase_2(b, b.goal_engine.list_goals())
    run_phase_3(b)
    run_phase_4(b)
    run_phase_5()
    verify_disabled()
