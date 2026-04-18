import unittest
from unittest.mock import MagicMock
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain
from jarvis_ai.tools.system_tool import SystemTool
from jarvis_ai.tools.web_tool import WebTool
from jarvis_ai.tools.mobile_tool import MobileTool

class TestTools(unittest.TestCase):
    def setUp(self):
        self.config = {'llm': {'provider': 'mock'}}
        self.brain = Brain(self.config)

    def test_system_tool_logs(self):
        """Test SystemTool mocked logging."""
        tool = SystemTool()
        result = tool.create_file("test.txt")
        self.assertIn("created successfully (MOCK)", result)
        
        result = tool.write_file("test.txt", "content")
        self.assertIn("Content written", result)

    def test_web_tool_logs(self):
        """Test WebTool mocked logging."""
        tool = WebTool()
        result = tool.open_url("http://google.com")
        self.assertIn("Opened http://google.com (MOCK)", result)

    def test_mobile_tool_logs(self):
        """Test MobileTool mocked logging."""
        tool = MobileTool()
        result = tool.send_message("123456", "Hello")
        self.assertIn("Message sent to 123456 (MOCK)", result)

    def test_brain_simulation_commands(self):
        """Test Brain simulation commands."""
        # System
        response = self.brain.think("Simulate creating file test_doc.txt")
        self.assertIn("File 'test_doc.txt' created", response)
        
        # Web
        response = self.brain.think("Simulate opening url https://example.com")
        self.assertIn("Opened https://example.com", response)
        
        # Mobile
        response = self.brain.think("Simulate sending message to 555-0100: Hello Jarvis")
        self.assertIn("Message sent to 555-0100", response)

if __name__ == '__main__':
    unittest.main()
