"""
Short-term Memory.
Maintains the context of the current conversation and active tasks.
"""

class ShortTermMemory:
    def __init__(self):
        self.conversation_history = []
        self.current_context = {}

    def add_context(self, role, content):
        """
        Add a message to the conversation history.
        Alias for add_message for clarity.
        """
        self.add_message(role, content)

    def add_message(self, role, content):
        """
        Add a message to the conversation history.
        """
        self.conversation_history.append({"role": role, "content": content})
        # Limit memory size to prevent overflow (e.g., last 50 messages)
        if len(self.conversation_history) > 50:
            self.conversation_history.pop(0)

    def get_context(self, n=None):
        """
        Retrieve current context for the Brain.
        Args:
            n (int, optional): Number of recent messages to return.
        Returns:
            list: List of message dictionaries.
        """
        if n is None:
            return self.conversation_history
        return self.conversation_history[-n:]

    def clear(self):
        """
        Clear the conversation history.
        """
        self.conversation_history = []
