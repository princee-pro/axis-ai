"""
LLM Advisory Module.
Analyzes system performance and suggests strategic optimizations in a sandboxed manner.
Includes cost monitoring and budget enforcement.
"""
import os
from jarvis_ai.llm.providers.openai_provider import OpenAIProvider
from jarvis_ai.llm.providers.gemini_provider import GeminiProvider

class LLMAdvisory:
    def __init__(self, brain):
        self.brain = brain
        self.daily_budget_usd = float(brain.memory_engine.get_setting('llm_daily_budget', 5.0))
        self.error_threshold = 5
        self.cost_per_1k_tokens = 0.01
        self.provider = self._initialize_provider()

    def _initialize_provider(self):
        config = self.brain.config.get('llm', {})
        provider_name = config.get('provider', 'openai').lower()
        
        # API Keys retrieval with fallback
        openai_key = os.environ.get('OPENAI_API_KEY') or os.environ.get('LLM_API_KEY') or config.get('openai_api_key') or config.get('api_key')
        gemini_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('LLM_API_KEY') or config.get('gemini_api_key') or config.get('api_key')

        if provider_name == 'openai':
            return OpenAIProvider(
                api_key=openai_key,
                model=config.get('model', 'gpt-4-turbo'),
                timeout=config.get('timeout_seconds', 30)
            )
        elif provider_name == 'gemini':
            return GeminiProvider(
                api_key=gemini_key,
                model=config.get('model', 'gemini-pro'),
                timeout=config.get('timeout_seconds', 30)
            )
        # Advisory is legacy and separate from runtime router providers; default safely to OpenAI.
        return OpenAIProvider(
            api_key=openai_key,
            model=config.get('model', 'gpt-4-turbo'),
            timeout=config.get('timeout_seconds', 30)
        )
        
    def run_advisory_cycle(self):
        """Perform a strategic analysis and generate advice."""
        if self.brain.memory_engine.get_setting('enable_llm_advisory', 'False') != 'True':
            return None

        # 1. Check Budget & Errors
        if not self._check_safety_constraints():
            return None

        # 2. Gather Context
        analytics = self.brain.memory_engine.get_analytics()
        recent_goals = self.brain.goal_engine.list_goals()[:5] # Sample last 5
        
        # 3. LLM Analysis with safety controls
        try:
            prompt = self._build_prompt(analytics, recent_goals)
            content = self._generate_with_retries(prompt)
            proposal = json.loads(content) if content.strip().startswith('{') else self._parse_text_proposal(content)
        except Exception as e:
            self.brain.logger.log(f"[LLM-ADVISORY] Error during generation: {e}", "ERROR")
            self.record_error()
            
            return None
        
        # 4. Governance Validation
        is_allowed, reason = self.brain.governance.validate_llm_proposal(proposal)
        
        # 5. Record & Log
        tokens = 150 # Mock token count
        cost = (tokens / 1000) * self.cost_per_1k_tokens
        
        self.brain.memory_engine.record_advisory(
            proposal_type=proposal['type'],
            content=proposal['content'],
            meta_goal=proposal.get('suggested_meta_goal'),
            gov_status='approved' if is_allowed else 'blocked',
            gov_reason=reason,
            tokens=tokens,
            cost=cost
        )
        
        # Update usage metrics
        self._update_usage_metrics(tokens, cost)
        
        return proposal if is_allowed else None

    def _check_safety_constraints(self):
        """Enforce budget and error thresholds."""
        # Check Error Count
        errors = int(self.brain.memory_engine.get_setting('llm_error_count', 0))
        if errors >= self.error_threshold:
            self.brain.logger.log("[LLM-ADVISORY] Emergency Shutdown: Error threshold exceeded.", "CRITICAL")
            return False
            
        # Check Budget
        daily_budget = float(self.brain.memory_engine.get_setting('llm_daily_budget', 5.0))
        usage = float(self.brain.memory_engine.get_setting('llm_token_usage_total', 0))
        # Total cost proxy: usage * cost_factor
        total_cost = (usage / 1000) * self.cost_per_1k_tokens
        if total_cost >= daily_budget:
            self.brain.logger.log("[LLM-ADVISORY] Budget Cap Reached. Suggestions paused.", "WARNING")
            return False
            
        return True

    def _update_usage_metrics(self, tokens, cost):
        """Update persistent usage counters."""
        current_tokens = int(self.brain.memory_engine.get_setting('llm_token_usage_total', 0))
        self.brain.memory_engine.set_setting('llm_token_usage_total', current_tokens + tokens)

    def _generate_simulated_proposal(self, analytics, recent_goals):
        """Generate a sample proposal based on system state."""
        success_rate = analytics['overall_success_rate']
        
        if success_rate < 80:
            return {
                'type': 'optimization',
                'content': "Frequent failures detected in web-based tasks. Suggesting a comprehensive retry audit.",
                'suggested_meta_goal': {
                    'description': "Audit failure patterns for WebTool operations",
                    'priority': 4,
                    'tags': ["system_improvement", "LLM-origin"],
                    'steps': ["Analyze recent logs for connectivity errors", "Propose timeout adjustments"]
                }
            }
        else:
            return {
                'type': 'strategy',
                'content': "System performance is optimal. Suggesting proactive knowledge exploration.",
                'suggested_meta_goal': None
            }

    def _build_prompt(self, analytics, recent_goals):
        return f"Analyze system state: Success Rate {analytics['overall_success_rate']}%.\nRecent Goals: {recent_goals}\nSuggest one strategic meta-goal or optimization in JSON format: {{'type': '...', 'content': '...', 'suggested_meta_goal': {{...}}}}"

    def _generate_with_retries(self, prompt, max_retries=3):
        config = self.brain.config.get('llm', {})
        max_retries = config.get('max_retries', max_retries)
        
        for i in range(max_retries + 1):
            try:
                # Truncate prompt if too large (Safety Guard)
                prompt_truncated = prompt[:10000] # Simple 10k char limit
                return self.provider.generate(prompt_truncated)
            except Exception as e:
                if i == max_retries:
                    raise e
                wait = (2 ** i) # Exponential backoff
                self.brain.logger.log(f"[LLM-ADVISORY] Retry {i+1}/{max_retries} after {wait}s due to error: {e}", "WARNING")
                time.sleep(wait)

    def _parse_text_proposal(self, text):
        # Fallback parser if LLM returns non-JSON
        return {'type': 'strategic_note', 'content': text, 'suggested_meta_goal': None}

    def record_error(self):
        """Increment error counter."""
        errors = int(self.brain.memory_engine.get_setting('llm_error_count', 0))
        self.brain.memory_engine.set_setting('llm_error_count', errors + 1)
