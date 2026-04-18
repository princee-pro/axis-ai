# demo.py
import time
import subprocess

print("=== Jarvis Full Demo ===")

# Step 1: Start client in autonomous mode
print("\n--- Starting Client ---")
subprocess.run(["python", "client_mock.py"])

# Step 2: Run commands inside client_mock.py
# The client_mock.py already executes goals automatically
# So no need to type commands manually in PowerShell

print("\n--- Demo Complete ---")
