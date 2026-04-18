"""
Governance & Alignment Engine.
Evaluates goal coherence, detects conflicts, and maintains the system risk index.
"""
import time
from datetime import datetime

class GovernanceEngine:
    def __init__(self, brain):
        self.brain = brain
        self.last_run = 0.0
        self.check_interval = 300 # 5 minutes
        self.resource_budget = {
            'cpu_weight': 0.0,
            'active_time_allocation': 0.0,
            'max_cpu': 1.0, # Soft limit
            'max_time': 3600 # 1 hour of parallel work proxy
        }
        self.risk_thresholds = {
            'low': 30,
            'medium': 60,
            'high': 85
        }
        self.previous_risk = 0.0

    def evaluate_goal(self, goal, active_goals):
        """
        Comprehensive evaluation of a goal before/during execution.
        Returns: (coherence_modifier, conflicts, risk_contribution)
        """
        conflicts = self.detect_conflicts(goal, active_goals)
        coherence = self.calculate_coherence(goal, active_goals, conflicts)
        
        # User goals cannot be suppressed, only warned
        is_user_goal = "system_improvement" not in (goal.get('tags') or [])
        
        # Modifier logic
        modifier = coherence
        if not is_user_goal and self.get_risk_index() > self.risk_thresholds['high']:
            modifier *= 0.5 # Halve priority in high risk mode
            
        return modifier, conflicts

    def calculate_coherence(self, goal, active_goals, conflicts):
        """
        Compute CoherenceScore (0.0 - 1.0).
        Penalizes conflicts, redundancy, and high resource cost.
        """
        score = 1.0
        
        # 1. Conflict Penalty
        if conflicts:
            score *= 0.7 ** len(conflicts)
            
        # 2. Redundancy Check (Meta-goals only)
        if "system_improvement" in (goal.get('tags') or []):
            completed_goals = [g for g in self.brain.goal_engine.list_goals() if g['status'] == 'completed']
            for cg in completed_goals:
                if goal['description'] == cg['description']:
                    score *= 0.3 # High penalty for Redundant improvement
                    
        # 3. System Health Influence
        health = 100
        if hasattr(self.brain, 'strategic'):
            health = self.brain.strategic.get_health_index()
        
        if health < 50:
            score *= 0.8 # De-prioritize everything if system is unstable
            
        # 4. Resource Cost Estimate (Simulated)
        estimated_cost = self._estimate_resource_cost(goal)
        current_pressure = self.get_resource_pressure()
        if current_pressure > 0.8:
            score *= (1.0 - (float(estimated_cost) * 0.5))
            
        return float(round(max(0.1, float(score)), 2))

    def detect_conflicts(self, goal, active_goals):
        """Detect resource overlaps and tag opposition."""
        conflicts = []
        
        goal_tags = set(goal.get('tags') or [])
        goal_resources = self._extract_resources_from_plan(goal)
        
        for other in active_goals:
            if other['id'] == goal['id'] or other['status'] != 'running':
                continue
            
            # 1. Resource Conflict
            other_resources = self._extract_resources_from_plan(other)
            overlap = goal_resources.intersection(other_resources)
            if overlap:
                conflicts.append({
                    'type': 'resource_overlap',
                    'with_id': other['id'],
                    'resource': list(overlap)[0]
                })
                
            # 2. Opposing Tags
            other_tags = set(other.get('tags') or [])
            if ("optimize_speed" in goal_tags and "reduce_load" in other_tags) or \
               ("reduce_load" in goal_tags and "optimize_speed" in other_tags):
                conflicts.append({
                    'type': 'opposing_objectives',
                    'with_id': other['id'],
                    'tags': ['optimize_speed', 'reduce_load']
                })
                
        return conflicts

    def validate_llm_proposal(self, proposal):
        """
        Hard-validation of LLM-generated proposals.
        Returns: (is_allowed, reason)
        """
        proposal_type = proposal.get('type', 'general')
        content = proposal.get('content', '')
        meta_goal = proposal.get('suggested_meta_goal')

        # 1. Block prohibited keywords (Action-oriented)
        safety_blocks = ["delete", "rm -rf", "shutdown", "kill -9", "format", "eval("]
        for block in safety_blocks:
            if block in content.lower():
                return False, f"Prohibited keyword detected: {block}"

        # 2. Prevent direct weight modification proposals
        if proposal_type == "weight_optimization" or "weight_" in content.lower():
            return False, "Direct weight optimization bypass detected. Prohibited in advisory mode."

        # 3. Validate meta-goal if proposed
        if meta_goal:
            # LLM cannot propose executable shell steps or file deletions
            steps = meta_goal.get('steps', [])
            for step in steps:
                s_lower = str(step).lower()
                if "systemtool" in s_lower or "os." in s_lower or "subprocess" in s_lower:
                     return False, "Meta-goal contains prohibited executable tool calls (SystemTool)."
            
            # Must have 'LLM-origin' tag
            tags = meta_goal.get('tags', [])
            if "LLM-origin" not in tags:
                return False, "Meta-goal missing mandatory 'LLM-origin' tag."

        return True, "Proposal passed advisory governance check."

    def get_risk_index(self):
        """Composite index (0-100)."""
        if not hasattr(self.brain, 'scheduler') or not self.brain.scheduler.memory_engine:
            return 0
            
        analytics = self.brain.scheduler.memory_engine.get_analytics()
        
        # Factors:
        failure_factor = (100.0 - float(analytics['overall_success_rate'])) * 0.4
        retry_factor = float(min(float(analytics.get('total_retries', 0) * 5), 30.0)) # Max 30% from retries
        resource_factor = float(self.get_resource_pressure()) * 30.0 # Max 30% from pressure
        
        risk = failure_factor + retry_factor + resource_factor
        current_risk = float(round(min(100.0, float(risk)), 1))
        
        # Log Transitions
        prev_cat = self._get_risk_category(self.previous_risk)
        curr_cat = self._get_risk_category(current_risk)
        if prev_cat != curr_cat:
            self.brain.logger.log(f"[GOVERNANCE] Risk Transition: {prev_cat} -> {curr_cat} (Risk: {current_risk})", "WARNING")
            
        self.previous_risk = current_risk
        return current_risk

    def _get_risk_category(self, risk_val):
        if risk_val < self.risk_thresholds['low']: return 'LOW'
        if risk_val < self.risk_thresholds['medium']: return 'MEDIUM'
        if risk_val < self.risk_thresholds['high']: return 'HIGH'
        return 'CRITICAL'

    def get_resource_pressure(self):
        """Current resource load ratio (0.0 - 1.0+)."""
        active_goals = [g for g in self.brain.goal_engine.list_goals() if g['status'] == 'running']
        total_cpu = sum(float(self._estimate_resource_cost(g)) for g in active_goals)
        return float(round(total_cpu / float(self.resource_budget['max_cpu']), 2))

    def _estimate_resource_cost(self, goal):
        """Rough estimate of CPU/Time cost based on description/steps."""
        steps = goal.get('steps', [])
        if not steps:
            return 0.1
        
        # Web search is expensive, system write is cheap
        cost = 0.0
        for step in steps:
            desc = str(step).lower()
            if "webtool" in desc or "research" in desc:
                cost += 0.3
            elif "llm" in desc or "analyze" in desc:
                cost += 0.2
            else:
                cost += 0.05
                
        return min(0.5, cost) # Cap single goal at 0.5 impact

    def _extract_resources_from_plan(self, goal):
        """Identify which tools/files the goal uses."""
        resources = set()
        steps = goal.get('steps', [])
        for step in steps:
            desc = str(step)
            if "WebTool" in desc: resources.add("network")
            if "SystemTool" in desc: resources.add("filesystem")
            if "MobileTool" in desc: resources.add("mobile_bridge")
        return resources
