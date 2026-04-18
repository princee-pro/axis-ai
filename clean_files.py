import os

def check_and_fix(filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, 'rb') as f:
        content = f.read()
    if b'\x00' in content:
        print(f"FIXING: {filepath} (Null bytes found)")
        new_content = content.replace(b'\x00', b'')
        with open(filepath, 'wb') as f:
            f.write(new_content)
    else:
        print(f"CLEAN: {filepath}")

files = [
    "jarvis_ai/integrations/google/__init__.py",
    "jarvis_ai/integrations/google/auth.py",
    "jarvis_ai/integrations/google/gmail_client.py",
    "jarvis_ai/integrations/google/calendar_client.py",
    "jarvis_ai/core/brain.py",
    "jarvis_ai/mobile/server.py",
    "jarvis_ai/memory/memory_engine.py"
]

for f in files:
    check_and_fix(f)
