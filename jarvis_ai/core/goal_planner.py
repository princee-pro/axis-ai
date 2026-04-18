"""
Goal Planner — Phase 7.2
LLM-backed multi-step planning with policy firewall and deterministic fallback.
"""

from datetime import datetime
import hashlib
import json
import re
import uuid

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_STEPS = 5          # default soft cap
HARD_CAP_STEPS = 8    # never exceed this

ALLOWED_CAPABILITY_TYPES = {
    'manual', 'chat', 'web_plan', 'gmail_draft', 'calendar_proposal',
}

# Keywords that trigger policy rejection / downgrade
UNSAFE_PATTERNS = [
    # Must reject the whole plan if the *plan* is fundamentally unsafe
    (r'(captcha|bypass|solve|circumvent).{0,30}(captcha|bypass|solve|circumvent)', 'CAPTCHA bypass/solving'),
    (r'(bypass|circumvent|evade|ats|applicant.tracking).{0,30}(bypass|circumvent|evade|ats|applicant.tracking)', 'ATS exploit'),
    (r'(stealth|anti.bot|undetectable|evasion)', 'Anti-bot/stealth evasion'),
    (r'(privilege.escalation|root.access|admin.bypass|escalate)', 'Privilege escalation'),
    (r'(mass.spam|bulk.spam|send.spam|bulk.email)', 'Bulk spam'),
    (r'(security.circumvention|bypass.security|exploit.vulnerability)', 'Security circumvention'),
]

# Keywords that downgrade a single *step* to manual with a warning
UNSAFE_STEP_PATTERNS = [
    (r'login.{0,30}automat', 'Login automation'),
    (r'password.{0,30}(enter|fill|automat)', 'Password entry automation'),
    (r'payment.{0,30}automat', 'Payment automation'),
    (r'(deceptive|mislead|fake).{0,30}(application|message|behavior)', 'Deceptive behavior'),
    (r'(auto.{0,10}apply|automatically.apply).{0,40}job', 'Automatic job application'),
    (r'(untruthful|deceived|fake.identity)', 'Untruthful behavior'),
]

# Goal category → canonical fallback plan
_FALLBACK_TEMPLATES = {
    'web_research': [
        ('Define search scope', 'Identify relevant domains and search queries', 'manual', True),
        ('Gather information', 'Browse and read relevant web pages', 'web_plan', True),
        ('Draft summary', 'Summarize key findings', 'chat', False),
        ('Manual review', 'Owner reviews and approves summary', 'manual', True),
    ],
    'outreach': [
        ('Draft message', 'Compose initial outreach draft', 'chat', False),
        ('Review draft', 'Owner reviews and adjusts message', 'manual', True),
        ('Send / schedule', 'Owner sends or schedules approved message', 'manual', True),
    ],
    'document': [
        ('Outline content', 'Identify key sections and structure', 'chat', False),
        ('Draft document', 'Write initial content', 'chat', False),
        ('Manual review', 'Owner reviews and refines the draft', 'manual', True),
    ],
    'analysis': [
        ('Identify data sources', 'Locate relevant information sources', 'manual', True),
        ('Gather data', 'Collect data points or summaries', 'web_plan', True),
        ('Summarize analysis', 'Write analysis summary', 'chat', False),
        ('Owner review', 'Owner validates conclusions', 'manual', True),
    ],
    'general': [
        ('Clarify objective', 'Break down the goal into concrete sub-tasks', 'chat', False),
        ('Execute first step', 'Handle the primary action', 'manual', True),
        ('Manual review', 'Owner reviews outcomes', 'manual', True),
    ],
}

_CATEGORY_KEYWORDS = {
    'web_research': ['research', 'find', 'search', 'look up', 'gather info', 'survey', 'explore'],
    'outreach': ['email', 'message', 'contact', 'reach out', 'send', 'draft'],
    'document': ['write', 'document', 'report', 'draft', 'summarize', 'create a'],
    'analysis': ['analyze', 'compare', 'evaluate', 'assess', 'review data', 'study'],
}

PLANNER_PROMPT_SENTINEL = "JARVIS_PLAN_PROMPT"


# ── Helper ─────────────────────────────────────────────────────────────────────

def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode('utf-8', errors='replace')).hexdigest()[:16]


# ── Main class ────────────────────────────────────────────────────────────────

class GoalPlanner:
    """
    Wraps the LLM advisory provider to generate policy-constrained,
    multi-step goal plans with automatic fallback.
    """

    def __init__(self, brain):
        self.brain = brain
        self.memory = brain.memory_engine
        self._provider_name = self._detect_provider_name()

    def _detect_provider_name(self):
        try:
            prov = self.brain.advisory.provider
            return type(prov).__name__.lower().replace('provider', '') or 'mock'
        except Exception:
            return 'mock'

    # ── Public entry point ────────────────────────────────────────────────────

    def plan(self, goal_id):
        """
        Generate and persist a plan for goal_id.
        Returns a dict:  {plan_id, steps_count, planner_type, planner_provider,
                          planner_warnings, fallback_used, plan_id, error?}
        """
        goal = self.memory.get_goal_record(goal_id)
        if not goal:
            return {'error': 'Goal not found'}

        prompt = self._build_planner_prompt(goal)
        raw = None
        planner_type = 'fallback'
        warnings = []
        fallback_used = False

        # ── Step 1: try LLM ───────────────────────────────────────────────────
        try:
            raw = self.brain.advisory.provider.generate(prompt)
        except Exception as exc:
            warnings.append(f"LLM call failed: {exc}")
            raw = None

        # ── Step 2: parse JSON output ─────────────────────────────────────────
        llm_steps = None
        llm_summary = None
        llm_risk = None
        raw_hash = None

        if raw:
            raw_hash = _sha1(raw)
            parsed, parse_warn = self._parse_plan_json(raw)
            warnings.extend(parse_warn)
            if parsed:
                llm_steps = parsed.get('steps', [])
                llm_summary = parsed.get('summary')
                llm_risk = parsed.get('risk_summary', {})
                planner_type = 'llm'
            else:
                fallback_used = True

        # ── Step 3: policy firewall ───────────────────────────────────────────
        if llm_steps is not None:
            safe_steps, fw_warnings, is_fundamental_violation = self._validate_plan(goal, llm_steps)
            warnings.extend(fw_warnings)
            if is_fundamental_violation:
                fallback_used = True
                llm_steps = None
                planner_type = 'fallback'
            else:
                llm_steps = safe_steps

        # ── Step 4: fallback if needed ────────────────────────────────────────
        if llm_steps is None:
            llm_steps = self._fallback_plan(goal)
            llm_summary = None
            llm_risk = None
            planner_type = 'fallback'
            fallback_used = True

        # ── Step 5: cap steps ─────────────────────────────────────────────────
        if len(llm_steps) > HARD_CAP_STEPS:
            warnings.append(f"Plan truncated from {len(llm_steps)} to {HARD_CAP_STEPS} steps.")
            llm_steps = llm_steps[:HARD_CAP_STEPS]

        # ── Step 6: persist plan ──────────────────────────────────────────────
        plan_id = str(uuid.uuid4())[:12]
        risk_note = (llm_risk.get('overall', 'unknown') if llm_risk else 'fallback')
        risk_text = llm_summary or f"Plan created by {planner_type} planner. Steps: {len(llm_steps)}"

        plan_data = {
            'id': plan_id,
            'goal_id': goal_id,
            'status': 'active',
            'risk_summary': risk_text,
            'created_by': f'{planner_type}_planner',
            'created_at': datetime.now().isoformat(),
            'planner_type': planner_type,
            'planner_provider': self._provider_name,
            'planner_warnings': json.dumps(warnings) if warnings else None,
            'raw_plan_hash': raw_hash,
        }
        self.memory.create_plan_record(plan_data)
        self.memory.log_goal_event(goal_id, 'plan_created',
                                   from_status=goal['status'], plan_id=plan_id,
                                   reason=f"planner={planner_type}")

        # ── Persist steps ─────────────────────────────────────────────────────
        for idx, s in enumerate(llm_steps):
            step_data = {
                'id': str(uuid.uuid4())[:8],
                'goal_id': goal_id,
                'plan_id': plan_id,
                'step_index': idx,
                'title': s.get('title', f'Step {idx+1}'),
                'description': s.get('description', ''),
                'capability_type': s.get('capability_type', 'manual'),
                'status': 'pending',
                'requires_approval': bool(s.get('requires_approval', True)),
            }
            self.memory.create_plan_step_record(step_data)
            self.memory.log_goal_event(goal_id, 'step_created', to_status='pending',
                                       plan_id=plan_id, step_id=step_data['id'])

        self.memory.update_goal_record(goal_id, {'status': 'planned'})
        self.memory.log_goal_event(goal_id, 'goal_planned', from_status=goal['status'],
                                   to_status='planned', plan_id=plan_id,
                                   reason=f"planner_type={planner_type}")

        return {
            'plan_id': plan_id,
            'steps_count': len(llm_steps),
            'planner_type': planner_type,
            'planner_provider': self._provider_name,
            'planner_warnings': warnings,
            'fallback_used': fallback_used,
        }

    # ── Replan ────────────────────────────────────────────────────────────────

    def replan(self, goal_id):
        """
        Archive existing future (pending/planned) steps, then run plan() again.
        History and completed steps are preserved.
        """
        goal = self.memory.get_goal_record(goal_id)
        if not goal:
            return {'error': 'Goal not found'}
        if goal['status'] in ('completed', 'failed'):
            return {'error': f"Cannot replan a {goal['status']} goal"}

        # Archive pending/planned steps (set to 'archived')
        plan = self.memory.get_current_plan_for_goal(goal_id)
        if plan:
            steps = self.memory.get_goal_plan_steps(goal_id, plan['id'])
            for step in steps:
                if step['status'] in ('pending', 'planned'):
                    self.memory.update_plan_step_record(step['id'], {'status': 'archived'})
                    self.memory.log_goal_event(goal_id, 'step_archived',
                                               from_status=step['status'], to_status='archived',
                                               plan_id=plan['id'], step_id=step['id'],
                                               reason='replan requested')

        # Reset goal to draft so plan() can take it from scratch
        self.memory.update_goal_record(goal_id, {
            'status': 'draft',
            'current_step_index': 0,
        })
        self.memory.log_goal_event(goal_id, 'goal_replanned',
                                   from_status=goal['status'], to_status='draft',
                                   reason='replan requested')

        return self.plan(goal_id)

    # ── Prompt building ───────────────────────────────────────────────────────

    def _build_planner_prompt(self, goal):
        objective = goal.get('objective', '')
        title = goal.get('title', 'Untitled')
        return (
            f"{PLANNER_PROMPT_SENTINEL}\n\n"
            f"You are Jarvis, a safe personal AI. Create a structured, multi-step plan "
            f"for the following user goal.\n\n"
            f"Goal title: {title}\n"
            f"Objective: {objective}\n\n"
            f"Rules:\n"
            f"- Maximum {MAX_STEPS} steps\n"
            f"- Only use capability_type from: {sorted(ALLOWED_CAPABILITY_TYPES)}\n"
            f"- requires_approval must be true for any web_plan or external action\n"
            f"- Do NOT include CAPTCHA bypass, login automation, payment automation, "
            f"stealth techniques, mass spam, or ATS exploits\n\n"
            f"Return ONLY valid JSON matching this exact schema:\n"
            f'{{\n'
            f'  "summary": "Short plan summary",\n'
            f'  "steps": [\n'
            f'    {{\n'
            f'      "title": "...", "description": "...",\n'
            f'      "capability_type": "manual|chat|web_plan|gmail_draft|calendar_proposal",\n'
            f'      "requires_approval": true, "risk_level": "low|medium|high", "inputs": {{}}\n'
            f'    }}\n'
            f'  ],\n'
            f'  "risk_summary": {{"overall": "low|medium|high", "notes": []}}\n'
            f'}}'
        )

    # ── JSON parsing ──────────────────────────────────────────────────────────

    def _parse_plan_json(self, raw: str):
        """Extract and normalize plan JSON. Returns (parsed_dict|None, warnings)."""
        warnings = []

        # Try direct parse
        text = raw.strip()
        # Extract first JSON block if surrounded by prose
        json_match = re.search(r'\{[\s\S]+\}', text)
        if not json_match:
            warnings.append("LLM output contained no JSON object — using fallback planner.")
            return None, warnings

        try:
            parsed = json.loads(json_match.group())
        except (json.JSONDecodeError, ValueError) as exc:
            warnings.append(f"LLM output JSON was malformed ({exc}) — using fallback planner.")
            return None, warnings

        # Validate required fields
        if not isinstance(parsed.get('steps'), list) or not parsed['steps']:
            warnings.append("LLM plan had no steps — using fallback planner.")
            return None, warnings

        # Normalize each step
        norm_steps = []
        for i, step in enumerate(parsed['steps']):
            if not isinstance(step, dict):
                warnings.append(f"Step {i} is not a dict, skipping.")
                continue
            cap = step.get('capability_type', 'manual')
            if cap not in ALLOWED_CAPABILITY_TYPES:
                warnings.append(
                    f"Step {i} has unknown capability_type '{cap}' → converted to 'manual'."
                )
                cap = 'manual'
                step['requires_approval'] = True
            norm_steps.append({
                'title': str(step.get('title', f'Step {i+1}'))[:120],
                'description': str(step.get('description', ''))[:500],
                'capability_type': cap,
                'requires_approval': bool(step.get('requires_approval', True)),
                'risk_level': step.get('risk_level', 'low'),
                'inputs': step.get('inputs', {}),
            })

        parsed['steps'] = norm_steps
        return parsed, warnings

    # ── Policy firewall ───────────────────────────────────────────────────────

    def _validate_plan(self, goal, steps):
        """
        Run policy checks on LLM-generated steps.

        Returns: (safe_steps, warnings_list, is_fundamental_violation)
        """
        warnings = []
        objective_lower = goal.get('objective', '').lower()

        # Fundamental plan-level violations (whole plan rejected)
        for pattern, label in UNSAFE_PATTERNS:
            combined = objective_lower + ' ' + ' '.join(
                (s.get('title', '') + ' ' + s.get('description', '')).lower()
                for s in steps
            )
            if re.search(pattern, combined, re.IGNORECASE):
                warnings.append(
                    f"Plan rejected — fundamental unsafe content detected: {label}"
                )
                return [], warnings, True

        # Step-level downgrades
        safe_steps = []
        for i, step in enumerate(steps):
            step_text = (step.get('title', '') + ' ' + step.get('description', '')).lower()
            downgraded = False
            for pattern, label in UNSAFE_STEP_PATTERNS:
                if re.search(pattern, step_text, re.IGNORECASE):
                    warnings.append(
                        f"Step {i} '{step.get('title')}' downgraded to 'manual' — {label}"
                    )
                    step = dict(step)
                    step['capability_type'] = 'manual'
                    step['requires_approval'] = True
                    step['risk_level'] = 'high'
                    downgraded = True
                    break
            safe_steps.append(step)

        return safe_steps, warnings, False

    # ── Deterministic fallback planner ────────────────────────────────────────

    def _fallback_plan(self, goal):
        """
        Generate a 2-4 step deterministic plan based on goal category.
        Never emits unsafe steps.
        """
        obj = (goal.get('objective', '') + ' ' + goal.get('title', '')).lower()
        category = 'general'

        for cat, keywords in _CATEGORY_KEYWORDS.items():
            if any(kw in obj for kw in keywords):
                category = cat
                break

        # Web objectives override with web_research if keywords found
        if any(kw in obj for kw in ('http', 'website', 'url', 'web')):
            if category == 'general':
                category = 'web_research'

        template = _FALLBACK_TEMPLATES.get(category, _FALLBACK_TEMPLATES['general'])
        steps = []
        for title, desc, cap, requires_approval in template:
            steps.append({
                'title': title,
                'description': desc,
                'capability_type': cap,
                'requires_approval': requires_approval,
                'risk_level': 'low',
                'inputs': {},
            })
        return steps
