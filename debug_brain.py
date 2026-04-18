import sys
try:
    from jarvis_ai.core.brain import Brain
    print("Brain import success")
    b = Brain({})
    print("Brain init success")
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()
