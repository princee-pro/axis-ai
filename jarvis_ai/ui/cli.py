"""
Command Line Interface (CLI).
The primary interface for interacting with Jarvis on the desktop.
"""

class CLI:
    def __init__(self, brain):
        self.brain = brain
        self.running = False

    def start(self):
        """
        Start the REPL loop.
        """
        self.running = True
        print("\n--- Jarvis AI CLI ---")
        print("Type 'exit' to quit.\n")

        while self.running:
            try:
                user_input = input("You: ")
                if user_input.lower() in ['exit', 'quit']:
                    self.stop()
                    break
                
                self.process_input(user_input)
            except KeyboardInterrupt:
                self.stop()
                break

    def stop(self):
        """
        Stop the CLI loop.
        """
        self.running = False
        print("\nGoodbye!")

    def process_input(self, user_input):
        """
        Send input to the Brain and print response.
        """
        if not user_input.strip():
            return

        # Get response from Brain
        response = self.brain.get_response(user_input)
        
        # Print with color/formatting if desired (kept simple for now)
        print(f"Jarvis: {response}\n")
