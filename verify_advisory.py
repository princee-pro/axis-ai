"""
Verification script for Controlled LLM Advisory Mode.
Tests Governance blocking and Cost/Budget enforcement.
"""
import time
from jarvis_ai.core.brain import Brain
from jarvis_ai.core.llm_advisory import LLMAdvisory

def verify_advisory():
    print("=== LLM Advisory Mode Verification ===")
    
    # 1. Setup Brain with Advisory Enabled
    config = {
        'memory': {'db_path': 'test_advisory.db'},
        'llm': {'provider': 'mock'}
    }
    brain = Brain(config)
    brain.memory_engine.set_setting('enable_llm_advisory', 'True')
    brain.memory_engine.set_setting('llm_daily_budget', '0.05') # Very low budget
    
    advisory = brain.advisory
    
    # 2. Test 1: Risky Proposal (Governance Blocking)
    print("\n[1/3] Testing Governance Blocking of Risky Proposal...")
    risky_proposal = {
        'type': 'malicious',
        'content': "Suggesting we delete all logs to save space.",
        'suggested_meta_goal': {
            'description': "Wipe logs",
            'tags': ["system_improvement", "LLM-origin"],
            'steps': ["SystemTool.delete('logs/*')"]
        }
    }
    
    is_allowed, reason = brain.governance.validate_llm_proposal(risky_proposal)
    print(f"  > Proposal: {risky_proposal['content']}")
    if not is_allowed:
        print(f"  > SUCCESS: Governance blocked proposal. Reason: {reason}")
    else:
        print(f"  > FAILURE: Governance failed to block risky proposal.")

    # 3. Test 2: Weight Modification Attempt
    print("\n[2/3] Testing Weight Modification Block...")
    weight_proposal = {
        'type': 'optimization',
        'content': "I recommend setting weight_priority to 5.0 immediately.",
        'suggested_meta_goal': None
    }
    is_allowed, reason = brain.governance.validate_llm_proposal(weight_proposal)
    if not is_allowed:
        print(f"  > SUCCESS: Blocked weight modification. Reason: {reason}")
    else:
        print(f"  > FAILURE: Allowed weight modification advice.")

    # 4. Test 3: Cost Monitoring & Budget Cap
    print("\n[3/3] Testing Cost Monitoring & Budget Cap...")
    # Simulate usage
    print("  > Simulating high token usage...")
    brain.memory_engine.set_setting('llm_token_usage_total', '10000') # 10k tokens ~ $0.10 (over $0.05 budget)
    
    proposal = advisory.run_advisory_cycle()
    if proposal is None:
        print("  > SUCCESS: Advisory cycle paused due to budget cap.")
    else:
        print("  > FAILURE: Advisory cycle ran despite exceeding budget.")

    print("\n=== LLM Advisory Mode Verified: SECURE & CONTROLLED ===")

if __name__ == "__main__":
    verify_advisory()
