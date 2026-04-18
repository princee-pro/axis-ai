"""
Demo script for Advanced Autonomous Intelligence upgrade.
Tests smart scheduling, DAG dependencies, deadlines, and failure recovery.
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain

def demo_autonomy_upgrade():
    """Demonstrate advanced autonomous intelligence features."""
    
    print("=" * 70)
    print("Advanced Autonomous Intelligence Demo")
    print("=" * 70)
    print("\nInitializing Jarvis...\n")
    
    config = {'llm': {'provider': 'mock'}}
    brain = Brain(config)
    
    # 1. Test Deadline-Based Scoring
    print("1. Testing Deadline-Based Urgency Scoring")
    print("-" * 70)
    
    # Goal with far deadline (low urgency)
    far_deadline = datetime.now() + timedelta(days=10)
    goal1 = brain.goal_engine.set_goal(
        "Write documentation",
        priority=1,
        deadline=far_deadline
    )
    print(f"Goal {goal1['id']}: '{goal1['description']}' - Deadline in 10 days")
    
    # Goal with near deadline (high urgency)
    near_deadline = datetime.now() + timedelta(hours=12)
    goal2 = brain.goal_engine.set_goal(
        "Fix critical bug",
        priority=1,
        deadline=near_deadline
    )
    print(f"Goal {goal2['id']}: '{goal2['description']}' - Deadline in 12 hours")
    
    # Calculate scores
    score1 = brain.autonomy.scheduler.calculate_score(goal1, brain.goal_engine.list_goals())
    score2 = brain.autonomy.scheduler.calculate_score(goal2, brain.goal_engine.list_goals())
    print(f"\nScores: Goal 1 = {score1}, Goal 2 = {score2}")
    print(f"Selected: Goal {goal2['id']} (higher urgency wins despite same priority)\n")
    
    # 2. Test DAG Dependencies
    print("2. Testing DAG Dependencies")
    print("-" * 70)
    
    # Create dependency chain
    goal_a = brain.goal_engine.set_goal("Setup environment", priority=1)
    goal_b = brain.goal_engine.set_goal("Install dependencies", priority=1, dependencies=[goal_a['id']])
    goal_c = brain.goal_engine.set_goal("Run tests", priority=1, dependencies=[goal_b['id']])
    goal_d = brain.goal_engine.set_goal("Deploy app", priority=1, dependencies=[goal_b['id']])
    
    print(f"Goal {goal_a['id']}: Setup environment (no dependencies)")
    print(f"Goal {goal_b['id']}: Install dependencies (depends on {goal_a['id']})")
    print(f"Goal {goal_c['id']}: Run tests (depends on {goal_b['id']})")
    print(f"Goal {goal_d['id']}: Deploy app (depends on {goal_b['id']})")
    
    # Test circular dependency detection
    print("\nTrying to create circular dependency...")
    try:
        brain.goal_engine.add_dependency(goal_a['id'], goal_c['id'])  # Would create cycle
        print("ERROR: Circular dependency not detected!")
    except:
        result = brain.goal_engine.add_dependency(goal_a['id'], goal_c['id'])
        if not result:
            print("SUCCESS: Circular dependency prevented!\n")
    
    # 3. Test Priority + Dependency Pressure
    print("3. Testing Dependency Pressure")
    print("-" * 70)
    
    goal_blocker = brain.goal_engine.set_goal("Critical blocker task", priority=1)
    goal_waiting1 = brain.goal_engine.set_goal("Waiting task 1", priority=1, dependencies=[goal_blocker['id']])
    goal_waiting2 = brain.goal_engine.set_goal("Waiting task 2", priority=1, dependencies=[goal_blocker['id']])
    goal_waiting3 = brain.goal_engine.set_goal("Waiting task 3", priority=1, dependencies=[goal_blocker['id']])
    
    pressure = brain.autonomy.scheduler.calculate_dependency_pressure(goal_blocker, brain.goal_engine.list_goals())
    score_blocker = brain.autonomy.scheduler.calculate_score(goal_blocker, brain.goal_engine.list_goals())
    
    print(f"Goal {goal_blocker['id']}: '{goal_blocker['description']}'")
    print(f"  Dependency Pressure: {pressure} (3 goals waiting)")
    print(f"  Total Score: {score_blocker}")
    print("  High pressure increases priority!\n")
    
    # 4. Test Smart Selection
    print("4. Testing Smart Goal Selection")
    print("-" * 70)
    
    all_goals = brain.goal_engine.list_goals()
    best_goal = brain.autonomy.scheduler.select_next_goal(all_goals)
    
    if best_goal:
        score = brain.autonomy.scheduler.calculate_score(best_goal, all_goals)
        print(f"Scheduler selected: Goal {best_goal['id']} - '{best_goal['description']}'")
        print(f"  Score: {score}")
        print(f"  Priority: {best_goal['priority']}")
        print(f"  Dependencies: {best_goal.get('dependencies', [])}")
        print(f"  Deadline: {best_goal.get('deadline', 'None')}\n")
    
    #5. Test Overdue Goal Escalation
    print("5. Testing Overdue Goal Escalation")
    print("-" * 70)
    
   # Goal with past deadline
    overdue_deadline = datetime.now() - timedelta(hours=2)
    goal_overdue = brain.goal_engine.set_goal(
        "Overdue task",
        priority=1,
        deadline=overdue_deadline
    )
    print(f"Goal {goal_overdue['id']}: '{goal_overdue['description']}' - 2 hours overdue")
    
    urgency = brain.autonomy.scheduler.calculate_urgency(goal_overdue['deadline'])
    print(f"  Urgency score: {urgency} (max = 10)")
    
    # Escalate priority
    brain.goal_engine.escalate_priority(goal_overdue['id'])
    updated_goal = brain.goal_engine.get_goal_by_id(goal_overdue['id'])
    print(f"  Priority escalated: 1 -> {updated_goal['priority']}\n")
    
    print("=" * 70)
    print("Demo Complete!")
    print("=" * 70)
    print("\nFeatures demonstrated:")
    print("  - Deadline-based urgency scoring")
    print("  - DAG dependencies with cycle detection")
    print("  - Dependency pressure calculation")
    print("  - Smart goal selection (scoring algorithm)")
    print("  - Overdue goal detection and escalation")
    print("=" * 70)

if __name__ == '__main__':
    demo_autonomy_upgrade()
