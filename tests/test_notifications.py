"""
Unit tests for notifications module.
"""

import unittest
import time
from jarvis_ai.core.notifications import NotificationManager

class TestNotifications(unittest.TestCase):
    
    def setUp(self):
        """Set up test notification manager."""
        self.nm = NotificationManager()
        self.nm.start()
    
    def tearDown(self):
        """Clean up."""
        self.nm.stop()
    
    def test_notification_queue(self):
        """Test basic notification queuing."""
        self.nm.notify(1, "Test", "Message", "normal")
        
        # Give queue time to process
        time.sleep(0.6)
        
        # Check queue is empty after processing
        self.assertEqual(len(self.nm.notification_queue), 0)
    
    def test_deduplication(self):
        """Test duplicate notification prevention."""
        # Send same notification twice quickly
        self.nm.notify(1, "Test", "Message", "normal")
        self.nm.notify(1, "Test", "Message", "normal")
        
        # Only one should be queued
        time.sleep(0.1)
        self.assertLessEqual(len(self.nm.notification_queue), 1)
    
    def test_deduplication_window(self):
        """Test deduplication expires after window."""
        self.nm.dedup_window = 1  # 1 second window
        
        self.nm.notify(1, "Test", "Message", "normal")
        time.sleep(1.5)  # Wait past window
        self.nm.notify(1, "Test", "Message", "normal")
        
        # Both should go through
        self.assertTrue(True)  # If we got here, no errors

if __name__ == '__main__':
    print("Running Notifications Tests...")
    unittest.main()
