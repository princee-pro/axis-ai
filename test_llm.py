import sys
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from jarvis_ai.llm.router import chat

print("Testing direct chat call...")
try:
    result = chat([{"role": "user", "content": "hello"}])
    print(result)
except Exception as e:
    import traceback
    traceback.print_exc()
