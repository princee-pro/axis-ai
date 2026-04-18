"""
Autonomy Manager.
Controls the autonomous execution loop with smart scheduling.
"""

import time
import threading
from datetime import datetime
from jarvis_ai.core.scheduler import GoalScheduler

class AutonomyManager:
    def __init__(self, brain):
        self.brain = brain
        self.is_running = False
        self.autonomous_loop_active = False
        self.loop_thread = None
        self.scheduler = brain.scheduler if hasattr(brain, 'scheduler') else GoalScheduler(logger=brain.logger if hasattr(brain, 'logger') else None)
        self.cycle_lock = threading.Lock() # Prevents overlapping scheduling cycles

    def run_goal(self, goal_id, mode='mock'):
        """
        Execute a goal autonomously.
        Args:
            goal_id (int): ID of the goal.
            mode (str): 'mock' or 'real'.
        """
        # Set Tool Modes
        if hasattr(self.brain.system_tool, 'set_mode'):
            self.brain.system_tool.set_mode(mode)
        if hasattr(self.brain.web_tool, 'set_mode'):
            self.brain.web_tool.set_mode(mode)

        goal = self.brain.goal_engine.get_goal_context(goal_id)
        if not goal:
            return f"Goal {goal_id} not found."

        if not goal['steps']:
            return f"Goal {goal_id} has no steps. Please plan it first."

        self.brain.logger.log(f"Starting autonomous execution for Goal {goal_id}: '{goal['description']}'", goal_id=goal_id)
        
        goal['status'] = 'in-progress'
        self.is_running = True
        start_time = time.time()
        logs = []
        success = True
        
        try:
            for i, step in enumerate(goal['steps']):
                if not self.is_running:
                    self.brain.logger.log("Execution stopped by user.", goal_id=goal_id)
                    logs.append("Execution stopped by user.")
                    success = False
                    break
                
                # Check condition
                if not self.evaluate_condition(step.get('condition') if isinstance(step, dict) else None, goal, i):
                    self.brain.logger.log(f"Step {i+1}/{len(goal['steps'])}: Skipped (condition not met)", "INFO", goal_id=goal_id)
                    self.brain.goal_engine.update_step_status(goal_id, i, 'skipped')
                    logs.append(f"Step {i+1}: Skipped (condition not met)")
                    continue
                    
                # Update step status to running
                self.brain.goal_engine.update_step_status(goal_id, i, 'running')
                
                # Get action
                action = step.get('action') if isinstance(step, dict) else step
                
                # Log execution
                self.brain.logger.log(f"Executing Step {i+1}/{len(goal['steps'])}: {action}", goal_id=goal_id)
                logs.append(f"Step {i+1}: {action}")
                
                # Progress Update
                progress = int(((i + 1) / len(goal['steps'])) * 100)
                self.brain.goal_engine.update_progress(goal_id, progress)
                
                # Ethics Check (Placeholder)
                if not self.validate_action(action):
                    self.brain.logger.log(f"Step {i+1} flagged by Ethics Controller. Skipping.", "WARNING", goal_id=goal_id)
                    self.brain.goal_engine.update_step_status(goal_id, i, 'failed', 'ethics_check_failed')
                    logs.append(f"Step {i+1}: Flagged by Ethics Controller.")
                    continue

                # Execute Tool based on step description
                step_success = self.execute_step(action, goal_id)
                
                # Update step status
                status = 'success' if step_success else 'failed'
                self.brain.goal_engine.update_step_status(goal_id, i, status, {'success': step_success})
                logs.append(f"Step {i+1} result: {status}")
                if not step_success:
                    success = False

            if self.is_running and success:
                # Complete goal and check for chaining
                next_goal_id = self.brain.goal_engine.complete_goal(goal_id)
                self.brain.logger.log(f"Goal {goal_id} execution finished. Status: Completed.", goal_id=goal_id)
                logs.append("Goal completed.")
                
                # If chained, trigger next goal
                if next_goal_id:
                    self.brain.logger.log(f"Triggering chained goal: {next_goal_id}", goal_id=goal_id)
                    time.sleep(0.5)
                    self.run_goal(next_goal_id, mode=mode)
            elif not success:
                logs.append("Goal failed.")
        
        except Exception as e:
            err_msg = f"Critical failure during goal execution: {e}"
            self.brain.logger.log(err_msg, "ERROR", goal_id=goal_id)
            logs.append(err_msg)
            success = False
        finally:
            self.is_running = False
            duration = time.time() - start_time
            # Record in MemoryEngine if connected via scheduler
            if hasattr(self.brain, 'scheduler') and self.brain.scheduler.memory_engine:
                 self.brain.scheduler.memory_engine.record_execution(goal, success=success, duration=duration)
            
        return "\n".join(logs)
    
    def execute_step(self, action, goal_id):
        """
        Execute a single step action.
        """
        action_lower = action.lower()
        try:
            # Check for API calls (Existing logic)
            if action.startswith("API:") or "api:" in action_lower:
                api_command = action.split(":", 1)[1].strip() if ":" in action else action
                return self.execute_api_call(api_command, goal_id)
            
            if "use systemtool" in action_lower:
                if "create file" in action_lower:
                    filename = action.split("file")[-1].strip()
                    result = self.brain.system_tool.create_file(filename)
                    return "Error" not in result
                elif "write file" in action_lower:
                    parts = action.split("with content")
                    filename = parts[0].split("file")[-1].strip()
                    content = parts[1].strip().strip("'")
                    result = self.brain.system_tool.write_file(filename, content)
                    return "Error" not in result

            elif "use webtool" in action_lower:
                if "open url" in action_lower:
                    url = action.split("url")[-1].strip()
                    result = self.brain.web_tool.open_url(url)
                    return "Error" not in result
                elif "search for" in action_lower:
                    query = action.split("search for")[-1].strip().strip("'")
                    result = self.brain.web_tool.search(query)
                    return "Error" not in result

            # Default: mock success
            return True
        except Exception as e:
            self.brain.logger.log(f"Tool error: {e}", "ERROR", goal_id=goal_id)
            return False

    def execute_api_call(self, command, goal_id):
        """Placeholder for API execution logic."""
        self.brain.logger.log(f"Simulating API call: {command}", goal_id=goal_id)
        return True

    def evaluate_condition(self, condition, goal, step_index):
        if condition is None: return True
        return False # Simple default

    def validate_action(self, action):
        return True

    def start_autonomous_loop(self, mode='mock', interval=5):
        if self.autonomous_loop_active: return "Already running."
        self.autonomous_loop_active = True
        self.loop_thread = threading.Thread(target=self._autonomous_loop, args=(mode, interval))
        self.loop_thread.daemon = True
        self.loop_thread.start()
        return "Started."

    def _autonomous_loop(self, mode, interval):
        while self.autonomous_loop_active:
            # 2. Scheduler Cycle Lock
            if not self.cycle_lock.acquire(blocking=False):
                self.brain.logger.log("[AUTONOMY] Scheduling cycle overlap detected. Skipping this cycle.", "WARNING")
                time.sleep(1) # Short wait before next check
                continue

            try:
                # 1. LLM Advisory Cycle (Advisory Mode)
                if hasattr(self.brain, 'advisory') and self.brain.advisory:
                    advisor_proposal = self.brain.advisory.run_advisory_cycle()
                    if advisor_proposal and advisor_proposal.get('suggested_meta_goal'):
                        # Insert meta-goal into goal engine (already safe/validated by governance)
                        meta = advisor_proposal['suggested_meta_goal']
                        # Ensure LLM-origin tag for auditability
                        if "LLM-origin" not in meta.get('tags', []):
                            meta['tags'] = meta.get('tags', []) + ["LLM-origin"]
                        
                        self.brain.goal_engine.set_goal(
                            meta['description'],
                            priority=meta.get('priority', 1),
                            tags=meta.get('tags', []),
                            steps=meta.get('steps', [])
                        )

                # 2. Strategic self-optimization check
                if hasattr(self.brain, 'strategic'):
                    self.brain.strategic.run_cycle()
                    
                all_goals = self.brain.goal_engine.list_goals()
                best_goal = self.scheduler.select_next_goal(all_goals)
                if best_goal:
                    self.run_goal(best_goal['id'], mode=mode)
                else:
                    time.sleep(interval)
            finally:
                self.cycle_lock.release()

    def stop_autonomous_loop(self):
        self.autonomous_loop_active = False
        return "Stopped."
