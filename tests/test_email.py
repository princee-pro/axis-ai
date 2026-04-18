"""
Unit tests for email integration.
"""

import unittest
from jarvis_ai.integrations.email_integration import EmailIntegration

class TestEmail(unittest.TestCase):
    
    def setUp(self):
        """Set up test email integration (mock mode)."""
        self.email = EmailIntegration(mock_mode=True)
    
    def test_send_email_mock(self):
        """Test sending email in mock mode."""
        result = self.email.send(
            to="test@example.com",
            subject="Test Subject",
            body="Test body"
        )
        
        self.assertTrue(result)
    
    def test_send_goal_report(self):
        """Test sending goal summary report."""
        goals = [
            {'id': 1, 'description': 'Goal 1', 'status': 'completed', 'priority': 1, 'progress': 100},
            {'id': 2, 'description': 'Goal 2', 'status': 'pending', 'priority': 2, 'progress': 50}
        ]
        
        result = self.email.send_goal_report(goals, "test@example.com")
        self.assertTrue(result)

if __name__ == '__main__':
    print("Running Email Integration Tests...")
    unittest.main()
