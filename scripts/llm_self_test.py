import os
import sys
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.brain import Brain
from jarvis_ai.core.version import APP_VERSION

def test_llm():
    print(f"=== Jarvis AI LLM Self-Test (v{APP_VERSION}) ===")
    
    # Load config (basic mock config)
    brain = Brain({"llm": {"provider": os.environ.get('TEST_LLM_PROVIDER', 'mock')}})
    provider_name = brain.advisory.provider.__class__.__name__
    
    print(f"Using Provider: {provider_name}")
    
    # Redact key for logs
    advisory_config = brain.config.get('llm', {})
    print(f"Config: provider={advisory_config.get('provider')}, model={advisory_config.get('model')}")

    try:
        print("Sending test prompt (minimal)...")
        response = brain.advisory.provider.generate("Return exactly: OK", max_tokens=10)
        print(f"Response: {response}")
        if "OK" in response:
            print("[SUCCESS] LLM connectivity verified.")
        else:
            print("[WARNING] Received unexpected response, check provider status.")
    except Exception as e:
        print(f"[FAIL] LLM call failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_llm()
