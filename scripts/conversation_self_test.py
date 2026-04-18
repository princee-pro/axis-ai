import os
import sys
import uuid

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain
from jarvis_ai.core.version import APP_VERSION

def run_conversation_test():
    print(f"=== Jarvis AI Conversation Self-Test (v{APP_VERSION}) ===")
    
    # Load config with mock provider
    config = {
        "llm": {"provider": "mock"},
        "memory": {"db_path": "jarvis_memory_test.db"},
        "memory_session_summarize_every_n_turns": 3 # Low for testing
    }
    
    brain = Brain(config)
    conv_id = str(uuid.uuid4())
    
    print(f"Starting conversation session: {conv_id}")
    
    # Send 10 messages
    for i in range(10):
        print(f"Turn {i+1}...")
        reply = brain.chat(conv_id, f"Hello turn {i+1}")
        print(f"Assistant: {reply[:50]}...")
        
    # Verify summarization persistence
    summary = brain.memory_engine.get_summary(conv_id)
    if summary:
        print(f"[OK] Summary persisted: {summary['summary_text'][:50]}...")
    else:
        print("[FAIL] Summary not found in DB")
        sys.exit(1)
        
    # Restart Brain and verify context recovery
    print("Restarting Brain...")
    brain_new = Brain(config)
    messages = brain_new.memory_engine.get_messages(conv_id, limit=100)
    if len(messages) >= 10:
        print(f"[OK] Recovered {len(messages)} messages from history.")
    else:
        print(f"[FAIL] Only recovered {len(messages)} messages.")
        sys.exit(1)
        
    # Test Long-term memory search (Explicit Policy)
    print("Testing long-term memory policy (Explicit)...")
    
    # 1. Normal message - should NOT be stored
    brain_new.chat(conv_id, "Actually, my favorite animal is a cat.")
    results = brain_new.memory_engine.search_long_term_memory("favorite animal")
    if not results:
        print("[OK] Normal message NOT stored in long-term memory.")
    else:
        print(f"[FAIL] Normal message was stored: {results[0]['text']}")
        sys.exit(1)
        
    # 2. Explicit message - should BE stored
    brain_new.chat(conv_id, "remember this: my favorite color is green.")
    results = brain_new.memory_engine.search_long_term_memory("favorite color")
    if results and "green" in results[0]['text'].lower():
        print(f"[OK] Explicit memory retrieved: {results[0]['text']}")
    else:
        print("[FAIL] Explicit memory retrieval failed or not stored.")
        sys.exit(1)

    # 3. Test list/delete management (Task 2)
    print("Testing memory management (List/Delete)...")
    mems = brain_new.memory_engine.list_long_term_memories()
    if len(mems) > 0:
        mid = mems[0]['id']
        print(f"Deleting memory ID: {mid}")
        brain_new.memory_engine.delete_long_term_memory(mid)
        mems_after = brain_new.memory_engine.list_long_term_memories()
        if len(mems_after) < len(mems):
            print("[OK] Memory deleted successfully.")
        else:
            print("[FAIL] Deletion failed.")
            sys.exit(1)
    else:
        print("[FAIL] No memories to test deletion.")
        sys.exit(1)

    print("\n=== Conversation Self-Test PASSED ===")

if __name__ == "__main__":
    if os.path.exists("jarvis_memory_test.db"):
        os.remove("jarvis_memory_test.db")
    run_conversation_test()
