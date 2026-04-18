"""
Goal Scheduler Module.
Implements smart scoring and selection for autonomous goal execution.
"""

from datetime import datetime, timedelta
from jarvis_ai.memory.memory_engine import MemoryEngine

class GoalScheduler:
    """
    Smart goal scheduler with scoring-based selection.
    Score = (Priority × 2) + Urgency + Dependency_Pressure - Failure_Penalty + Learning_Adjustment
    """
    
    def __init__(self, logger=None, db_path=None):
        self.logger = logger
        self.governance = None # Set by Brain
        try:
            self.memory_engine = MemoryEngine(db_path)
        except Exception as e:
            self._log(f"Failed to initialize MemoryEngine: {e}", "ERROR")
            self.memory_engine = None
    
    def _log(self, message, level="INFO"):
        """Log message if logger available."""
        if self.logger:
            self.logger.log(message, level)
    
    def calculate_urgency(self, deadline):
        """
        Calculate urgency score based on deadline proximity.
        
        Returns:
            0: No deadline
            1: >7 days
            3: 3-7 days
            5: 1-3 days
            8: <1 day
            10: Overdue
        """
        if not deadline:
            return 0
        
        if isinstance(deadline, str):
            deadline = datetime.fromisoformat(deadline)
        
        now = datetime.now()
        if deadline < now:
            return 10  # Overdue
        
        time_left = deadline - now
        days_left = time_left.total_seconds() / 86400
        
        if days_left > 7:
            return 1
        elif days_left > 3:
            return 3
        elif days_left > 1:
            return 5
        else:
            return 8
    
    def calculate_dependency_pressure(self, goal, all_goals):
        """
        Calculate pressure from dependent goals.
        Returns count of goals waiting on this one.
        """
        goal_id = goal['id']
        dependents = goal.get('dependents', [])
        
        # Count how many pending goals depend on this one
        pressure = len([d for d in dependents if self._is_goal_pending(d, all_goals)])
        return pressure
    
    def _is_goal_pending(self, goal_id, all_goals):
        """Check if goal is pending."""
        for g in all_goals:
            if g['id'] == goal_id and g['status'] == 'pending':
                return True
        return False
    
    def calculate_failure_penalty(self, goal):
        """
        Calculate penalty from failures.
        Penalty = retry_count × 2 (max 6)
        """
        retry_count = goal.get('retry_count', 0)
        penalty = min(retry_count * 2, 6)
        return penalty
    
    def calculate_score(self, goal, all_goals):
        """
        Calculate total score for a goal with dynamic weights.
        Score = (Priority × Wp) + (Urgency × Wu) + (Pressure × Wd) - (Penalty × Wf) + LearningAdjustment
        """
        # Fetch dynamic weights
        wp = float(self.memory_engine.get_setting('weight_priority', 2.0)) if self.memory_engine else 2.0
        wu = float(self.memory_engine.get_setting('weight_urgency', 1.0)) if self.memory_engine else 1.0
        wd = float(self.memory_engine.get_setting('weight_dependency', 1.0)) if self.memory_engine else 1.0
        wf = float(self.memory_engine.get_setting('weight_failure', 1.0)) if self.memory_engine else 1.0
        
        priority = goal.get('priority', 1)
        urgency_raw = self.calculate_urgency(goal.get('deadline'))
        pressure_raw = self.calculate_dependency_pressure(goal, all_goals)
        penalty_raw = self.calculate_failure_penalty(goal)
        
        priority_score = priority * wp
        urgency_weighted = urgency_raw * wu
        dependency_pressure = pressure_raw * wd
        failure_penalty = penalty_raw * wf
        
        base_score = priority_score + urgency_weighted + dependency_pressure - failure_penalty
        
        # Learning Adjustment
        learning_adjustment = 0
        if self.memory_engine:
            learning_adjustment = float(self.memory_engine.get_learning_adjustment(goal.get('tags', [])))
        
        final_score = max(0.1, base_score + learning_adjustment)
        
        # 2. Governance Oversight
        coherence_modifier = 1.0
        conflicts = []
        if self.governance:
            coherence_modifier, conflicts = self.governance.evaluate_goal(goal, all_goals)
            
        final_executable_score = round(final_score * coherence_modifier, 2)
        
        # Pilot Mode Decision Trace
        decision_trace = {
            "BaseScore": round(base_score, 2),
            "Components": {
                "Priority": round(priority_score, 2),
                "Urgency": round(urgency_weighted, 2),
                "Pressure": round(dependency_pressure, 2),
                "Penalty": round(failure_penalty, 2)
            },
            "LearningAdjustment": learning_adjustment,
            "CoherenceModifier": coherence_modifier,
            "Conflicts": conflicts,
            "FinalScore": final_executable_score,
            "RiskIndex": self.governance.get_risk_index() if self.governance else 0,
            "Timestamp": datetime.now().isoformat()
        }
        
        # Update goal for transparency and audit trail
        goal['decision_trace'] = decision_trace
        goal['risk_at_execution'] = decision_trace['RiskIndex']
        goal['weights'] = {'wp': wp, 'wu': wu, 'wd': wd, 'wf': wf}
        goal['score'] = final_executable_score
        
        # Expose governance fields for verification visibility
        goal['conflicts'] = conflicts
        goal['coherence_modifier'] = coherence_modifier
        
        # Log for trace visibility
        self._log(f"[PILOT] Goal {goal['id']} Scoring Trace: Base={decision_trace['BaseScore']} Coherence={coherence_modifier} Final={final_executable_score}", "INFO")
        
        return final_executable_score
    
    def get_ready_goals(self, goals):
        """
        Filter goals that are ready to run.
        Ready = pending status AND all dependencies satisfied AND not in cooldown.
        """
        ready = []
        
        for goal in goals:
            if goal['status'] != 'pending':
                continue
            
            # Check cooldown (retry backoff)
            if self._in_cooldown(goal):
                continue
            
            # Check dependencies satisfied
            if not self._dependencies_satisfied(goal, goals):
                continue
            
            ready.append(goal)
        
        return ready
    
    def _get_adaptive_backoff(self, goal):
        """Calculate backoff based on success rate of tags."""
        retry_count = goal.get('retry_count', 0)
        tags = goal.get('tags', [])
        
        multiplier = 1.0
        if self.memory_engine:
            analytics = self.memory_engine.get_analytics()
            tag_stats = {s['tag']: s for s in analytics['tag_stats']}
            for tag in tags:
                if tag in tag_stats:
                    success_rate = tag_stats[tag]['success_rate']
                    if success_rate < 50:
                        multiplier *= 2.0  # Double backoff for unreliable tags
                    elif success_rate > 90:
                        multiplier *= 0.5  # Halve backoff for reliable tags
        
        base_delay = 2 * multiplier
        return base_delay * (2 ** retry_count)

    def _in_cooldown(self, goal):
        """Check if goal is in retry cooldown."""
        last_failure = goal.get('last_failure')
        if not last_failure:
            return False
        
        if isinstance(last_failure, str):
            last_failure = datetime.fromisoformat(last_failure)
        
        retry_count = goal.get('retry_count', 0)
        
        # Chronic failure check
        retry_threshold = int(self.memory_engine.get_setting('retry_threshold', 5)) if self.memory_engine else 5
        if retry_count >= retry_threshold:
            return True # Escalated to Strategic Engine
            
        cooldown_duration = self._get_adaptive_backoff(goal)
        elapsed = (datetime.now() - last_failure).total_seconds()
        
        return elapsed < cooldown_duration
    
    def _dependencies_satisfied(self, goal, all_goals):
        """Check if all dependencies are completed."""
        dependencies = goal.get('dependencies', [])
        
        if not dependencies:
            return True
        
        goal_status_map = {g['id']: g['status'] for g in all_goals}
        
        for dep_id in dependencies:
            if dep_id not in goal_status_map:
                return False  # Dependency doesn't exist
            
            if goal_status_map[dep_id] != 'completed':
                return False  # Dependency not complete
        
        return True
    
    def select_next_goal(self, goals):
        """
        Select the best goal to execute based on scores.
        Returns goal with highest score, or None.
        """
        ready_goals = self.get_ready_goals(goals)
        
        if not ready_goals:
            return None
        
        # Calculate scores
        scored_goals = []
        for goal in ready_goals:
            score = self.calculate_score(goal, goals)
            scored_goals.append((score, goal))
        
        # Sort by score descending
        scored_goals.sort(key=lambda x: -x[0])
        
        best_score, best_goal = scored_goals[0]
        
        self._log(f"Selected goal {best_goal['id']} with score {best_score}")
        
        return best_goal
    
    def check_circular_dependencies(self, goal_id, new_dependency, all_goals):
        """
        Check if adding a dependency would create a cycle.
        Uses DFS to detect cycles.
        
        Returns:
            True if circular dependency detected
            False if safe to add
        """
        # Build adjacency list for existing dependencies
        graph = {}
        for g in all_goals:
            graph[g['id']] = g.get('dependencies', []).copy()
        
        # Add the proposed new dependency
        if goal_id not in graph:
            graph[goal_id] = []
        graph[goal_id].append(new_dependency)
        
        # DFS to detect cycle
        visited = set()
        rec_stack = set()
        
        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        # Check from the goal we're modifying
        return has_cycle(goal_id)
    
    def get_overdue_goals(self, goals):
        """Get list of goals that are overdue."""
        now = datetime.now()
        overdue = []
        
        for goal in goals:
            if goal['status'] != 'pending':
                continue
            
            deadline = goal.get('deadline')
            if not deadline:
                continue
            
            if isinstance(deadline, str):
                deadline = datetime.fromisoformat(deadline)
            
            if deadline < now:
                overdue.append(goal)
        
        return overdue
