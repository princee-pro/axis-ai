import unittest
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.memory.short_term import ShortTermMemory

class TestMemory(unittest.TestCase):
    def setUp(self):
        self.stm = ShortTermMemory()

    def test_short_term_addition(self):
        """Test adding messages to short-term memory."""
        self.stm.add_message("user", "Hello")
        context = self.stm.get_context()
        self.assertEqual(len(context), 1)
        self.assertEqual(context[0]['content'], "Hello")

    def test_context_windowing(self):
        """Test retrieving limited context."""
        for i in range(5):
            self.stm.add_message("user", f"Message {i}")
        
        # Get last 3
        context = self.stm.get_context(n=3)
        self.assertEqual(len(context), 3)
        self.assertEqual(context[0]['content'], "Message 2")
        self.assertEqual(context[-1]['content'], "Message 4")

    def test_clear_memory(self):
        """Test clearing memory."""
        self.stm.add_message("user", "Hello")
        self.stm.clear()
        self.assertEqual(len(self.stm.get_context()), 0)

    def test_persistence_placeholder(self):
        """Placeholder for long-term memory tests."""
        # TODO: Implement when LongTermMemory has actual logic
        pass

if __name__ == '__main__':
    unittest.main()
