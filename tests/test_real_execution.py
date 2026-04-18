
import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.tools.system_tool import SystemTool
from jarvis_ai.core.safety import SafetyManager
from jarvis_ai.core.brain import Brain

class TestRealExecution(unittest.TestCase):
    def setUp(self):
        self.tool = SystemTool(execution_mode='real')

    @patch('builtins.input', return_value='yes')
    @patch('builtins.open', new_callable=MagicMock)
    def test_create_file_real_confirmed(self, mock_open, mock_input):
        """Test real file creation with confirmation 'yes'."""
        # We mock open to avoid actual file system changes during test, 
        # but we verify the logic reaches the open call.
        result = self.tool.create_file("param_test.txt")
        
        self.assertIn("(REAL)", result)
        mock_open.assert_called_with("param_test.txt", 'w')

    @patch('builtins.input', return_value='no')
    @patch('builtins.open', new_callable=MagicMock)
    def test_create_file_real_denied(self, mock_open, mock_input):
        """Test real file creation with confirmation 'no'."""
        result = self.tool.create_file("param_test.txt")
        
        self.assertIn("Action cancelled", result)
        mock_open.assert_not_called()

    def test_brain_parsing_real_mode(self):
        """Test that Brain correctly parses 'real mode' command."""
        brain = Brain({'llm': {'provider': 'mock'}})
        brain.autonomy = MagicMock()
        
        brain.think("Run goal 1 in real mode")
        brain.autonomy.run_goal.assert_called_with(1, mode='real')
        
        brain.think("Run goal 2 in autonomous mode") # Default mock
        brain.autonomy.run_goal.assert_called_with(2, mode='mock')

if __name__ == '__main__':
    unittest.main()
