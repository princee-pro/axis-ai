"""
Long-term Memory.
Stores persistent data using JSON (or SQLite in future).
"""

import json
import os

class LongTermMemory:
    def __init__(self, storage_file="memory.json"):
        self.storage_file = storage_file
        self.data = self._load_data()

    def _load_data(self):
        """
        Load data from storage file.
        """
        if not os.path.exists(self.storage_file):
            return {}
        try:
            with open(self.storage_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading memory: {e}")
            return {}

    def _save_data(self):
        """
        Save data to storage file.
        """
        try:
            with open(self.storage_file, 'w') as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            print(f"Error saving memory: {e}")

    def save(self, key, value):
        """
        Store data permanently.
        """
        self.data[key] = value
        self._save_data()
        return f"Saved '{key}' to long-term memory."

    def load(self, key):
        """
        Retrieve stored data.
        """
        return self.data.get(key)

    def delete(self, key):
        """
        Remove stored data.
        """
        if key in self.data:
            del self.data[key]
            self._save_data()
            return f"Deleted '{key}' from long-term memory."
        return f"Key '{key}' not found."

    def get_all(self):
        """
        Return all stored data.
        """
        return self.data
