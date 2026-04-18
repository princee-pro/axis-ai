"""
Phase 7.2: LLM Goal Planner Self-Test
Tests multi-step planning, safety firewalls, metadata tracking, and replanning.
"""

import sys
import os
import json
import uuid
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from jarvis_ai.core.brain import Brain
from jarvis_ai.llm.providers.mock import MockProvider

def test_multi_step_plan():
    print("\n--- Test 11.1: Mock LLM Multi-Step Plan ---")
    config = {
        'llm': {'provider': 'mock'},
        'google': {'enabled': False},
        'memory': {'db_path': 'test_goal_llm.db'}
    }
    # Cleanup old test DB
    if os.path.exists('test_goal_llm.db'):
        try:
            os.remove('test_goal_llm.db')
        except:
            pass

    brain = Brain(config)
    objective = "Research renewable energy and summarize findings"
    goal = brain.goal_engine.create_goal(objective, title="Energy Research")
    
    # Run planner
    result = brain.goal_engine.plan_goal(goal['id'], brain=brain)
    
    print(f"Planner Result: {result}")
    assert result['planner_type'] == 'llm'
    assert result['steps_count'] > 1
    assert result['fallback_used'] is False
    
    summary = brain.goal_engine.summarize_goal(goal['id'])
    print(f"Goal Summary: {json.dumps(summary, indent=2)}")
    assert summary['planner_type'] == 'llm'
    assert summary['planner_provider'] == 'mock'
    print("Test 11.1 Passed")

def test_malformed_llm_output():
    print("\n--- Test 11.2: Malformed LLM Output Fallback ---")
    config = {
        'llm': {'provider': 'mock'},
        'google': {'enabled': False},
        'memory': {'db_path': 'test_goal_llm.db'}
    }
    brain = Brain(config)
    
    # Force MockProvider to return junk
    old_generate = brain.advisory.provider.generate
    brain.advisory.provider.generate = lambda x: "This is NOT json content at all."
    
    goal = brain.goal_engine.create_goal("Simple goal")
    result = brain.goal_engine.plan_goal(goal['id'], brain=brain)
    
    print(f"Result with junk output: {result}")
    assert result['planner_type'] == 'fallback'
    assert result['fallback_used'] is True
    assert any("no JSON object" in w for w in result['planner_warnings'])
    
    # Restore
    brain.advisory.provider.generate = old_generate
    print("Test 11.2 Passed")

def test_unsafe_plan_content():
    print("\n--- Test 11.3: Unsafe LLM Plan Content (Policy Rejection) ---")
    config = {
        'llm': {'provider': 'mock'},
        'google': {'enabled': False},
        'memory': {'db_path': 'test_goal_llm.db'}
    }
    brain = Brain(config)
    
    # Simulate LLM returning unsafe plan (CAPTCHA bypass)
    unsafe_json = json.dumps({
        "summary": "Unsafe plan",
        "steps": [
            {"title": "Bypass captcha", "description": "Solving captcha", "capability_type": "web_plan", "requires_approval": True}
        ],
        "risk_summary": {"overall": "low", "notes": []}
    })
    
    old_generate = brain.advisory.provider.generate
    brain.advisory.provider.generate = lambda x: unsafe_json
    
    goal = brain.goal_engine.create_goal("Unsafe task")
    result = brain.goal_engine.plan_goal(goal['id'], brain=brain)
    
    print(f"Result with unsafe output: {result}")
    assert result['planner_type'] == 'fallback'
    assert result['fallback_used'] is True
    assert any("fundamental unsafe content" in w for w in result['planner_warnings'])
    
    # Simulate step-level downgrade (Login automation)
    downgrade_json = json.dumps({
        "summary": "Plan with login",
        "steps": [
            {"title": "Automated Login", "description": "Using automated login script", "capability_type": "web_plan", "requires_approval": True}
        ],
        "risk_summary": {"overall": "low", "notes": []}
    })
    brain.advisory.provider.generate = lambda x: downgrade_json
    
    goal2 = brain.goal_engine.create_goal("Login task")
    result2 = brain.goal_engine.plan_goal(goal2['id'], brain=brain)
    
    print(f"Result with downgrade output: {result2}")
    assert result2['planner_type'] == 'llm' # Plan preserved
    assert result2['fallback_used'] is False
    assert any("downgraded to 'manual'" in w for w in result2['planner_warnings'])
    
    # Check step type
    steps = brain.memory_engine.get_goal_plan_steps(goal2['id'])
    assert steps[0]['capability_type'] == 'manual'
    
    brain.advisory.provider.generate = old_generate
    print("Test 11.3 Passed")

def test_replan_flow():
    print("\n--- Test 11.6: Replan Flow ---")
    config = {
        'llm': {'provider': 'mock'},
        'google': {'enabled': False},
        'memory': {'db_path': 'test_goal_llm.db'}
    }
    brain = Brain(config)
    
    goal = brain.goal_engine.create_goal("Initial goal")
    brain.goal_engine.plan_goal(goal['id'], brain=brain)
    
    plan1 = brain.memory_engine.get_current_plan_for_goal(goal['id'])
    steps1 = brain.memory_engine.get_goal_plan_steps(goal['id'], plan1['id'])
    
    # Replan
    brain.goal_engine.replan_goal(goal['id'], brain=brain)
    
    # Verify old steps are archived
    for s in steps1:
        refreshed = brain.memory_engine.get_plan_step_record(s['id'])
        assert refreshed['status'] == 'archived'
        
    summary = brain.goal_engine.summarize_goal(goal['id'])
    print(f"Summary after replan: {json.dumps(summary, indent=2)}")
    print("Test 11.6 Passed")

if __name__ == "__main__":
    try:
        test_multi_step_plan()
        test_malformed_llm_output()
        test_unsafe_plan_content()
        test_replan_flow()
        print("\nALL PHASE 7.2 TESTS PASSED")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
