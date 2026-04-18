"""
Main entry point for Jarvis AI System.
Initializes components and starts the interaction loop.
"""

import sys
import os
import yaml

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain
from jarvis_ai.ui.cli import CLI

def load_config():
    """Load configuration from settings.yaml"""
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'settings.yaml')
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("Config file not found. Using defaults.")
        return {}

def main():
    """
    Main execution loop.
    1. Load Config
    2. Initialize Core Brain
    3. Start CLI Loop
    """
    print("Initializing Jarvis AI System...")
    config = load_config()
    
    brain = Brain(config)
    cli = CLI(brain)
    
    print("Jarvis is ready. Type 'exit' to quit.")
    
    try:
        cli.start()
    except KeyboardInterrupt:
        print("\nShutting down Jarvis...")
        sys.exit(0)

if __name__ == "__main__":
    main()
