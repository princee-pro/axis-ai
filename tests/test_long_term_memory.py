
import unittest
import json
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.memory.long_term import LongTermMemory
from jarvis_ai.core.brain import Brain

class TestLongTermMemory(unittest.TestCase):
    def setUp(self):
        self.filename = "test_memory.json"
        self.memory = LongTermMemory(self.filename)
        # Ensure clean state
        if os.path.exists(self.filename):
            os.remove(self.filename)
        self.memory.data = {} # Reset in-memory too just in case

    def tearDown(self):
        if os.path.exists(self.filename):
            os.remove(self.filename)

    def test_save_load(self):
        """Test persistent save and load."""
        self.memory.save("user_pref", "dark_mode")
        
        # Verify in memory
        self.assertEqual(self.memory.load("user_pref"), "dark_mode")
        
        # Verify persistence (reload from file)
        new_mem = LongTermMemory(self.filename)
        self.assertEqual(new_mem.load("user_pref"), "dark_mode")

    def test_delete(self):
        """Test deleting stored data."""
        self.memory.save("temp", "value")
        self.memory.delete("temp")
        self.assertIsNone(self.memory.load("temp"))
        
        # Verify persistence
        new_mem = LongTermMemory(self.filename)
        self.assertIsNone(new_mem.load("temp"))

    def test_brain_commands(self):
        """Test Brain integration for memory commands."""
        brain = Brain({'llm': {'provider': 'mock'}})
        # Override brain's memory file to avoid polluting real memory
        brain.long_term_memory = LongTermMemory(self.filename)
        
        # Save
        resp = brain.think("Remember this permanently: My favorite color is blue")
        self.assertIn("Saved 'note_", resp)
        self.assertIn("to long-term memory", resp)
        
        # Retrieve
        resp = brain.think("Show my saved data")
        self.assertIn("favorite color is blue", resp)

if __name__ == '__main__':
    unittest.main()
