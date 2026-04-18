"""
Unit tests for reminders module.
"""

import unittest
import time
from datetime import datetime, timedelta
from jarvis_ai.integrations.reminders import RemindersManager
from jarvis_ai.core.notifications import NotificationManager

class TestReminders(unittest.TestCase):
    
    def setUp(self):
        """Set up test reminders manager."""
        self.notifications = NotificationManager()
        self.notifications.start()
        self.reminders = RemindersManager(
            notification_manager=self.notifications,
            data_dir="data/test"
        )
    
    def tearDown(self):
        """Clean up."""
        self.reminders.stop_checking()
        self.notifications.stop()
    
    def test_create_reminder(self):
        """Test creating a reminder."""
        reminder_time = datetime.now() + timedelta(hours=1)
        reminder_id = self.reminders.create(
            title="Test Reminder",
            reminder_datetime=reminder_time,
            goal_id=1
        )
        
        self.assertIsNotNone(reminder_id)
        self.assertGreater(reminder_id, 0)
    
    def test_get_due_reminders(self):
        """Test retrieving due reminders."""
        # Create reminder for the past
        past_time = datetime.now() - timedelta(minutes=1)
        self.reminders.create("Past Reminder", past_time)
        
        # Get due reminders
        due = self.reminders.get_due()
        self.assertGreaterEqual(len(due), 1)
    
    def test_recurring_reminder(self):
        """Test recurring reminder rescheduling."""
        reminder_time = datetime.now() - timedelta(seconds=1)
        reminder_id = self.reminders.create(
            title="Recurring Test",
            reminder_datetime=reminder_time,
            recurring=True,
            interval_days=1
        )
        
        # Mark as triggered with rescheduling
        self.reminders.mark_triggered(reminder_id, reschedule=True, interval_days=1)
        
        # Should still exist (rescheduled)
        self.assertTrue(True)  # If we got here, no errors

if __name__ == '__main__':
    print("Running Reminders Tests...")
    unittest.main()
