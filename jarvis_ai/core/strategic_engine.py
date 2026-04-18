"""
Strategic Autonomy Engine.
Monitors system behavior and generates meta-goals for self-optimization.
"""
import time
from datetime import datetime

class StrategicEngine:
    def __init__(self, brain):
        self.brain = brain
        self.last_run = 0.0
        self.check_interval = 300 # 5 minutes

    def run_cycle(self, force=False):
        """Periodic check for system improvements."""
        risk_index = 0
        if hasattr(self.brain, 'governance') and self.brain.governance:
            risk_index = self.brain.governance.get_risk_index()
        
        # Risk-based frequency adjustment
        effective_interval = self.check_interval
        if risk_index > 85: # High Risk
            effective_interval *= 5 # Slow down 5x
            self.brain.logger.log("[STRATEGIC] High Risk detected. Entering Conservative Mode.", "WARNING")
        
        # Check Human Override
        override = False
        if hasattr(self.brain, 'scheduler') and self.brain.scheduler.memory_engine:
            val = self.brain.scheduler.memory_engine.get_setting('human_override_mode', 'False')
            override = val == 'True'
            
        if override:
            self.brain.logger.log("[STRATEGIC] Human Override Active. Inhibiting autonomous cycles.", "INFO")
            return

        now = time.time()
        if not force and now - self.last_run < effective_interval:
            return
        
        self.last_run = now
        self.analyze_and_optimize(risk_index)

    def analyze_and_optimize(self, risk_index=0):
        """Analyze memory analytics and generate system improvement goals."""
        if not hasattr(self.brain, 'scheduler') or not self.brain.scheduler.memory_engine:
            return
        
        analytics = self.brain.scheduler.memory_engine.get_analytics()
        
        # Throttling meta-goals
        meta_goal_count = 0
        max_meta_per_cycle = 3

        # 1. Tag Failure Rate Check
        for stat in analytics.get('tag_stats', []):
            if meta_goal_count >= max_meta_per_cycle:
                break
            if stat['success_rate'] < 60 and stat['total'] >= 3:
                self.generate_meta_goal(
                    description=f"Improve strategy for {stat['tag']}",
                    reason=f"Failure rate high ({100 - stat['success_rate']}%)"
                )
                meta_goal_count += 1

        # 2. Automation Suggestions (Repetition)
        for pattern in analytics.get('repeated_patterns', []):
            if meta_goal_count >= max_meta_per_cycle:
                break
            self.generate_meta_goal(
                description=f"Automate recurring task: {pattern['description']}",
                reason=f"Repeated {pattern['count']} times"
            )
            meta_goal_count += 1
            
        # 3. Weight Self-Tuning (Freeze if high risk)
        if risk_index < 85:
            self.tune_weights(analytics)
        else:
            self.brain.logger.log("[STRATEGIC] Weight tuning frozen due to High Risk.", "INFO")

    def generate_meta_goal(self, description, reason):
        """Insert a system improvement goal."""
        existing = self.brain.goal_engine.list_goals()
        for g in existing:
            if g['description'] == description and g['status'] not in ['completed', 'failed']:
                return

        self.brain.logger.log(f"[STRATEGIC] New Meta-Goal: {description} ({reason})", "WARNING")
        
        goal_id = self.brain.goal_engine.set_goal(
            description=description,
            priority=2,
            tags=["system_improvement"]
        )
        
        # Use planner to generate steps and update the goal
        steps = self.brain.planner.create_plan(description)
        self.brain.goal_engine.update_steps(goal_id, steps)

    def tune_weights(self, analytics):
        """Adjust scoring weights based on global metrics."""
        memory = self.brain.scheduler.memory_engine
        
        w_priority = float(memory.get_setting('weight_priority', 2.0))
        w_urgency = float(memory.get_setting('weight_urgency', 1.0))
        w_failure = float(memory.get_setting('weight_failure', 1.0))

        updated = False
        
        # Global Failure Rate -> Failure Penalty
        if analytics['overall_success_rate'] < 70:
            new_failure = round(min(w_failure + 0.1, 3.0), 2)
            if new_failure > w_failure:
                memory.set_setting('weight_failure', new_failure)
                updated = True

        # Global Success Rate High -> Priority Multiplier
        if analytics['overall_success_rate'] > 90:
            new_priority = round(min(w_priority + 0.1, 4.0), 2)
            if new_priority > w_priority:
                memory.set_setting('weight_priority', new_priority)
                updated = True

        # Placeholder for Urgency tuning (requires deadline miss analytics)
        
        if updated:
            self.brain.logger.log(f"[STRATEGIC] Weight Adjustment: P={w_priority}->{memory.get_setting('weight_priority')}, F={w_failure}->{memory.get_setting('weight_failure')}", "INFO")

    def get_health_index(self):
        """Calculate composite health metric (0-100)."""
        if not hasattr(self.brain, 'scheduler') or not self.brain.scheduler.memory_engine:
            return 100
            
        analytics = self.brain.scheduler.memory_engine.get_analytics()
        success = analytics['overall_success_rate']
        
        # Health = SuccessRate * 0.7 + (Stability Factor)
        # Stability = 100 - (pending goals / 10) ... simple proxy
        pending_count = len([g for g in self.brain.goal_engine.list_goals() if g['status'] == 'pending'])
        stability = max(0, 100 - (pending_count * 5))
        
        return round((success * 0.7) + (stability * 0.3), 1)
