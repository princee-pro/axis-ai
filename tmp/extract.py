import os

filepath = r'd:\Axis\jarvis_ai\ui\static\app.js'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

auth_lines = [i for i, line in enumerate(lines) if 'auth-overlay' in line]
if auth_lines:
    start = max(0, auth_lines[0] - 10)
    end = min(len(lines), auth_lines[-1] + 100)
    
    os.makedirs('d:/Axis/tmp', exist_ok=True)
    with open('d:/Axis/tmp/app_init.js', 'w', encoding='utf-8') as out:
        out.writelines(lines[start:end])
    print("Extracted to d:/Axis/tmp/app_init.js")
else:
    print("Could not find auth-overlay in app.js")
