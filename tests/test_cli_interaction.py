import unittest
from unittest.mock import MagicMock, patch
import sys
import os
from io import StringIO

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.ui.cli import CLI
from jarvis_ai.core.brain import Brain

class TestCLIInteraction(unittest.TestCase):
    def setUp(self):
        self.config = {'llm': {'provider': 'mock'}}
        self.brain = Brain(self.config)
        self.cli = CLI(self.brain)

    @patch('builtins.input', side_effect=['My name is JarvisUser', 'Remember what I said', 'Exit'])
    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_loop(self, mock_stdout, mock_input):
        """
        Simulate a CLI session with:
        1. Context setting -> "My name is JarvisUser"
        2. Memory Recall -> "Remember what I said"
        3. Exit
        """
        self.cli.start()
        
        output = mock_stdout.getvalue()
        
        
        # Verify prompts and responses
        self.assertIn("I heard you say", output) # Generic response to unknown input
        self.assertIn("JarvisUser", output) # Should recall the name in the "remember" response

if __name__ == '__main__':
    unittest.main()
