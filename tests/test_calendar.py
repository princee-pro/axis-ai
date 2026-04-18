"""
Unit tests for calendar integration.
"""

import unittest
from datetime import datetime, timedelta
from jarvis_ai.integrations.calendar_integration import CalendarIntegration

class TestCalendar(unittest.TestCase):
    
    def setUp(self):
        """Set up test calendar."""
        self.calendar = CalendarIntegration(data_dir="data/test")
    
    def test_create_event(self):
        """Test creating calendar event."""
        start = datetime.now() + timedelta(days=1)
        event = self.calendar.create_event(
            title="Test Event",
            start=start,
            description="Test description"
        )
        
        self.assertIsNotNone(event)
        self.assertEqual(event['title'], "Test Event")
        self.assertIn('id', event)
    
    def test_get_upcoming_events(self):
        """Test retrieving upcoming events."""
        # Create event for tomorrow
        tomorrow = datetime.now() + timedelta(days=1)
        self.calendar.create_event("Tomorrow Event", tomorrow)
        
        # Get upcoming events
        upcoming = self.calendar.get_upcoming(days=7)
        
        self.assertGreaterEqual(len(upcoming), 1)
    
    def test_link_to_goal(self):
        """Test linking event to goal."""
        start = datetime.now() + timedelta(hours=2)
        event = self.calendar.create_event("Test", start)
        
        result = self.calendar.link_to_goal(event['id'], goal_id=5)
        self.assertTrue(result)
        
        # Verify link
        updated_event = self.calendar.events[event['id']]
        self.assertEqual(updated_event['goal_id'], 5)

if __name__ == '__main__':
    print("Running Calendar Integration Tests...")
    unittest.main()
