"""
Demo script for notifications and productivity integrations.
Tests calendar, email, reminders, and notifications together.
"""

import sys
import os
import time
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain

def demo_integrations():
    """Demonstrate all integrations working together."""
    
    print("=" * 60)
    print("Jarvis Integrations Demo")
    print("=" * 60)
    print("\nInitializing Jarvis with all integrations....\n")
    
    config = {'llm': {'provider': 'mock'}}
    brain = Brain(config)
    
    print("1. Creating High-Priority Goal (triggers notification)")
    print("-" * 60)
    goal1 = brain.goal_engine.set_goal("Prepare presentation", priority=2)
    time.sleep(1)
    
    print("\n2. Creating Calendar Event for Goal")
    print("-" * 60)
    tomorrow = datetime.now() + timedelta(days=1, hours=10)
    event = brain.calendar.create_event(
        title="Presentation Meeting",
        start=tomorrow,
        description="Quarterly review presentation",
        goal_id=goal1['id']
    )
    print(f"Created event: {event['title']} at {event['start']}")
    
    print("\n3. Setting Reminder for Goal Deadline")
    print("-" * 60)
    reminder_time = datetime.now() + timedelta(seconds=3)
    reminder_id = brain.reminders.create(
        title=f"Deadline: {goal1['description']}",
        reminder_datetime=reminder_time,
        goal_id=goal1['id']
    )
    print(f"Reminder created (ID: {reminder_id}) will trigger in 3 seconds...")
    
    print("\n4. Completing First Goal (triggers notification)")
    print("-" * 60)
    brain.goal_engine.complete_goal(goal1['id'])
    time.sleep(1)
    
    print("\n5. Creating Goals for Email Report")
    print("-" * 60)
    goal2 = brain.goal_engine.set_goal("Research competitors", priority=1)
    goal3 = brain.goal_engine.set_goal("Write blog post", priority=1)
    brain.goal_engine.complete_goal(goal2['id'])
    brain.goal_engine.complete_goal(goal3['id'])
    time.sleep(1)
    
    print("\n6. Sending Email Report (Mock Mode)")
    print("-" * 60)
    all_goals = brain.goal_engine.list_goals()
    brain.email.send_goal_report(all_goals, "user@example.com")
    
    print("\n7. Checking Calendar for Upcoming Events")
    print("-" * 60)
    upcoming = brain.calendar.get_upcoming(days=7)
    print(f"Found {len(upcoming)} upcoming event(s):")
    for evt in upcoming:
        print(f"  - {evt['title']} on {evt['start']}")
    
    print("\n8. Waiting for Reminder to Trigger...")
    print("-" * 60)
    time.sleep(4)  # Wait for reminder
    print("Reminder should have triggered!")
    
    print("\n9. Goal Status Summary")
    print("-" * 60)
    completed = [g for g in all_goals if g['status'] == 'completed']
    pending = [g for g in all_goals if g['status'] == 'pending']
    print(f"Completed Goals: {len(completed)}")
    print(f"Pending Goals: {len(pending)}")
    
    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)
    print("\nFeatures demonstrated:")
    print("  - Desktop notifications (on goal creation/completion)")
    print("  - Calendar events linked to goals")
    print("  - Reminders with scheduled notifications")
    print("  - Email reports (mock mode)")
    print("=" * 60)

if __name__ == '__main__':
    demo_integrations()
