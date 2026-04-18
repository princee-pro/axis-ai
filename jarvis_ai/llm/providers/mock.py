from jarvis_ai.llm.providers.base import LLMProviderBase
import json


# Sentinel keywords injected by tests into the prompt string
_KW_PLAN      = "JARVIS_PLAN_PROMPT"
_KW_BAD_JSON  = "FORCE_BAD_JSON"
_KW_UNSAFE    = "FORCE_UNSAFE_PLAN"
_KW_UNKNOWN   = "FORCE_UNKNOWN_CAP"


def _mock_plan(steps):
    return json.dumps({
        "summary": "Mock multi-step plan",
        "steps": steps,
        "risk_summary": {"overall": "low", "notes": ["Mock plan — safe for testing"]}
    })


class MockProvider(LLMProviderBase):
    def generate(self, prompt, system_prompt=None, temperature=0.7, max_tokens=500):
        """
        Simulated generation for testing.
        Supports structured plan output via sentinel keywords in the prompt.
        """
        p = prompt.lower()

        # ── Test 11.2 — malformed JSON ───────────────────────────────────────
        if _KW_BAD_JSON.lower() in p:
            return "this is not json {broken"

        # ── Test 11.3 — unsafe plan (ATS exploit step) ───────────────────────
        if _KW_UNSAFE.lower() in p:
            return _mock_plan([
                {
                    "title": "Submit application automatically",
                    "description": "Automatically apply to jobs on ATS bypassing checks",
                    "capability_type": "web_plan",
                    "requires_approval": False,
                    "risk_level": "high",
                    "inputs": {}
                },
                {
                    "title": "Review application",
                    "description": "Human-review the submitted application",
                    "capability_type": "manual",
                    "requires_approval": True,
                    "risk_level": "low",
                    "inputs": {}
                }
            ])

        # ── Test 11.4 — unknown capability type ──────────────────────────────
        if _KW_UNKNOWN.lower() in p:
            return _mock_plan([
                {
                    "title": "Run exploit script",
                    "description": "Execute privileged script",
                    "capability_type": "shell_exec",   # not in allowlist
                    "requires_approval": False,
                    "risk_level": "critical",
                    "inputs": {}
                }
            ])

        # ── Test 11.1 / generic planner call ─────────────────────────────────
        if _KW_PLAN.lower() in p:
            return _mock_plan([
                {
                    "title": "Research relevant sources",
                    "description": "Identify relevant web pages for the objective",
                    "capability_type": "web_plan",
                    "requires_approval": True,
                    "risk_level": "low",
                    "inputs": {}
                },
                {
                    "title": "Summarize findings",
                    "description": "Draft a summary of gathered information",
                    "capability_type": "chat",
                    "requires_approval": False,
                    "risk_level": "low",
                    "inputs": {}
                },
                {
                    "title": "Manual review",
                    "description": "Owner reviews and approves summary",
                    "capability_type": "manual",
                    "requires_approval": True,
                    "risk_level": "low",
                    "inputs": {}
                }
            ])

        # ── Legacy advisory fallback ──────────────────────────────────────────
        if "fail" in p:
            return "Frequent failures detected in web-based tasks. Suggesting a comprehensive retry audit."
        return "System performance is optimal. Suggesting proactive knowledge exploration."
