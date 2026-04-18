import unittest
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain

class TestBrain(unittest.TestCase):
    def setUp(self):
        self.config = {'llm': {'provider': 'mock'}}
        self.brain = Brain(self.config)

    def test_initialization(self):
        """Test if the Brain initializes correctly."""
        self.assertIsNotNone(self.brain)
        self.assertEqual(self.brain.llm_provider, 'mock')

    def test_mock_response(self):
        """Test the mock response generation."""
        response = self.brain.think("Hello")
        self.assertIn("Hello", response)
        
        response_goal = self.brain.think("I have a goal")
        self.assertIn("goal", response_goal)

if __name__ == '__main__':
    unittest.main()
