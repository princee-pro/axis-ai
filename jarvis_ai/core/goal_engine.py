"""
Goal Engine.
Phase 7.2 — LLM Planner Integration & Policy-Constrained Multi-Step Planning.
"""

from datetime import datetime
import uuid
import json

# Lazy import to avoid circular dependency — imported on first use
_GoalPlanner = None

def _get_planner_class():
    global _GoalPlanner
    if _GoalPlanner is None:
        from jarvis_ai.core.goal_planner import GoalPlanner
        _GoalPlanner = GoalPlanner
    return _GoalPlanner


# ── Safety-blocked execution result reasons ───────────────────────────────────
SAFETY_BLOCK_REASONS = {
    'captcha_detected', 'login_detected', 'payment_detected',
    'file_upload_blocked', 'commit_confirmation_required',
}


class GoalEngine:
    def __init__(self, memory_engine, notification_callback=None):
        self.memory_engine = memory_engine
        self.notification_callback = notification_callback

    # ──────────────────────────────────────────────────────────────────────────
    # CRUD helpers
    # ──────────────────────────────────────────────────────────────────────────

    def create_goal(self, objective, title=None, priority='normal', requires_approval=True):
        """Create a new goal in DRAFT state."""
        goal_id = str(uuid.uuid4())[:12]
        goal_data = {
            'id': goal_id,
            'title': title or "Untitled Goal",
            'objective': objective,
            'status': 'draft',
            'priority': priority,
            'requires_approval': requires_approval,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'summary': None,
        }
        self.memory_engine.create_goal_record(goal_data)
        self.memory_engine.log_goal_event(goal_id, 'goal_created', to_status='draft')
        if self.notification_callback:
            self.notification_callback('created', goal_data)
        return goal_data

    def list_goals(self):
        """Return list of all goals from DB."""
        return self.memory_engine.get_all_goals()

    def get_goal_context(self, goal_id):
        """Return details of a specific goal, enriched with plan + steps."""
        goal = self.memory_engine.get_goal_record(goal_id)
        if not goal:
            return None
        plan = self.memory_engine.get_current_plan_for_goal(goal_id)
        if plan:
            steps = self.memory_engine.get_goal_plan_steps(goal_id, plan['id'])
            goal['current_plan'] = plan
            goal['steps'] = steps
        else:
            goal['current_plan'] = None
            goal['steps'] = []
        return goal

    def _queue_step_for_owner_review(self, goal_id, step, action_type, payload, reason):
        action_id = str(uuid.uuid4())
        ts = datetime.now().isoformat()
        self.memory_engine.create_pending_action(
            action_id=action_id,
            action_type=action_type,
            payload=payload,
            created_by="goal_engine"
        )
        self.memory_engine.update_plan_step_record(step['id'], {
            'status': 'awaiting_approval',
            'action_ref': action_id,
            'last_transition_at': ts,
            'last_transition_reason': reason,
        })
        self.memory_engine.update_goal_record(goal_id, {'status': 'awaiting_approval'})
        self.memory_engine.log_goal_event(
            goal_id,
            'action_proposed',
            from_status='pending',
            to_status='awaiting_approval',
            step_id=step['id'],
            action_ref=action_id,
            reason=reason,
        )
        return True, action_id

    def _complete_step(self, goal_id, step_id, reason, result_json=None, result_ref=None):
        ts = datetime.now().isoformat()
        updates = {
            'status': 'completed',
            'last_transition_at': ts,
            'last_transition_reason': reason,
        }
        if result_json is not None:
            updates['result_json'] = json.dumps(result_json)
        if result_ref is not None:
            updates['result_ref'] = result_ref
        self.memory_engine.update_plan_step_record(step_id, updates)
        self.memory_engine.log_goal_event(
            goal_id,
            'step_completed',
            from_status='pending',
            to_status='completed',
            step_id=step_id,
            result_ref=result_ref,
            reason=reason,
        )

    def _block_goal_for_permission(self, goal, step, permission_key, permission_name, reason):
        ts = datetime.now().isoformat()
        self.memory_engine.update_plan_step_record(step['id'], {
            'status': 'blocked',
            'error': reason,
            'last_transition_at': ts,
            'last_transition_reason': reason,
        })
        self.memory_engine.update_goal_record(goal['id'], {'status': 'blocked', 'last_error': reason})
        self.memory_engine.log_goal_event(
            goal['id'],
            'goal_blocked',
            from_status=goal['status'],
            to_status='blocked',
            reason=f"{permission_name or permission_key}: {reason}",
            step_id=step['id'],
        )

    def _get_runtime(self, brain):
        if brain is not None and hasattr(brain, "get_permission_runtime"):
            return brain.get_permission_runtime()
        return {}

    def _get_next_actionable_step(self, steps, current_step_index=0):
        idx = current_step_index if isinstance(current_step_index, int) and current_step_index >= 0 else 0
        while idx < len(steps) and steps[idx].get('status') == 'completed':
            idx += 1
        if idx >= len(steps):
            return idx, None
        return idx, steps[idx]

    def _finish_goal_if_complete(self, goal_id, goal_status, steps):
        if steps and all(step.get('status') == 'completed' for step in steps):
            self.memory_engine.update_goal_record(goal_id, {'status': 'completed', 'summary': "All steps completed."})
            self.memory_engine.log_goal_event(
                goal_id,
                'goal_completed',
                from_status=goal_status,
                to_status='completed',
                reason='All steps completed',
            )
            return True
        return False

    def _queue_owner_review_step(self, goal, step, action_type, payload, reason):
        ok, action_id = self._queue_step_for_owner_review(goal['id'], step, action_type, payload, reason)
        if ok:
            return True, f"Awaiting approval for {step.get('title') or step.get('capability_type')}"
        return False, "Failed to queue owner review"

    def _complete_and_advance(self, goal, step, reason, result_json=None, result_ref=None):
        self._complete_step(goal['id'], step['id'], reason, result_json=result_json, result_ref=result_ref)
        next_index = int(step.get('step_index', goal.get('current_step_index', 0))) + 1
        self.memory_engine.update_goal_record(goal['id'], {'current_step_index': next_index, 'status': 'active'})
        refreshed = self.get_goal_context(goal['id']) or goal
        if self._finish_goal_if_complete(goal['id'], 'active', refreshed.get('steps', [])):
            if self.notification_callback:
                self.notification_callback('completed', refreshed)
            return True, "Goal completed"
        return True, "Step advanced"

    # ──────────────────────────────────────────────────────────────────────────
    # Planning
    # ──────────────────────────────────────────────────────────────────────────

    def plan_goal(self, goal_id, brain=None):
        """
        Phase 7.2: Use GoalPlanner (LLM + policy firewall + fallback) when brain is
        available. Falls back to _builtin_plan_goal when brain is None.
        """
        goal = self.memory_engine.get_goal_record(goal_id)
        if not goal:
            return {"error": "Goal not found"}

        # ── Delegate to GoalPlanner when brain is available ───────────────────
        if brain is not None:
            try:
                planner = _get_planner_class()(brain)
                result = planner.plan(goal_id)
                if 'error' not in result:
                    return result
            except Exception as exc:
                print(f"[GOAL ENGINE] GoalPlanner failed: {exc}, using built-in fallback.")

        # ── Built-in minimal fallback (no brain / GoalPlanner crash) ──────────
        return self._builtin_plan_goal(goal_id, goal)

    def replan_goal(self, goal_id, brain):
        """Phase 7.2: Archive pending steps, then generate a fresh plan preserving history."""
        if brain is None:
            return {'error': 'brain required for replan'}
        try:
            planner = _get_planner_class()(brain)
            return planner.replan(goal_id)
        except Exception as exc:
            return {'error': f'Replan failed: {exc}'}

    def _builtin_plan_goal(self, goal_id, goal):
        """Minimal built-in planner used when GoalPlanner is unavailable."""
        objective = goal['objective'].lower()

        is_unsafe = False
        risk_reasons = []
        if 'captcha' in objective or 'bypass' in objective:
            is_unsafe = True
            risk_reasons.append("CAPTCHA bypass requested")
        if 'apply' in objective and 'job' in objective and 'automatically' in objective:
            is_unsafe = True
            risk_reasons.append("ATS exploit detected")

        plan_id = str(uuid.uuid4())[:12]
        plan_data = {
            'id': plan_id,
            'goal_id': goal_id,
            'status': 'draft' if is_unsafe else 'active',
            'risk_summary': ', '.join(risk_reasons) if is_unsafe else None,
            'created_by': 'builtin_fallback',
            'created_at': datetime.now().isoformat(),
            'planner_type': 'fallback',
            'planner_provider': 'builtin',
            'planner_warnings': None,
            'raw_plan_hash': None,
        }
        self.memory_engine.create_plan_record(plan_data)
        self.memory_engine.log_goal_event(goal_id, 'plan_created', plan_id=plan_id)

        if is_unsafe:
            reason = ', '.join(risk_reasons)
            self.memory_engine.update_goal_record(
                goal_id, {'status': 'blocked', 'last_error': 'Unsafe objective: ' + reason}
            )
            self.memory_engine.log_goal_event(
                goal_id, 'goal_blocked', from_status='draft', to_status='blocked',
                reason=reason, plan_id=plan_id
            )
            if self.notification_callback:
                self.notification_callback('failed', goal)
            return {'error': reason, 'plan_id': plan_id}

        steps = []
        if any(kw in objective for kw in ('http', 'website', 'web', 'url')):
            steps.append({
                'id': str(uuid.uuid4())[:8],
                'goal_id': goal_id, 'plan_id': plan_id, 'step_index': 0,
                'title': 'Execute Web Automation', 'description': goal['objective'],
                'capability_type': 'web_plan', 'status': 'pending',
                'requires_approval': bool(goal['requires_approval']),
            })
        else:
            steps.append({
                'id': str(uuid.uuid4())[:8],
                'goal_id': goal_id, 'plan_id': plan_id, 'step_index': 0,
                'title': 'Analyze Objective', 'description': goal['objective'],
                'capability_type': 'manual', 'status': 'pending',
                'requires_approval': False,
            })

        for step in steps:
            self.memory_engine.create_plan_step_record(step)
            self.memory_engine.log_goal_event(
                goal_id, 'step_created', to_status='pending',
                plan_id=plan_id, step_id=step['id']
            )

        self.memory_engine.update_goal_record(goal_id, {'status': 'planned'})
        self.memory_engine.log_goal_event(
            goal_id, 'goal_planned', from_status='draft', to_status='planned', plan_id=plan_id
        )
        return {'plan_id': plan_id, 'steps_count': len(steps),
                'planner_type': 'fallback', 'planner_provider': 'builtin',
                'planner_warnings': [], 'fallback_used': True}

    # ──────────────────────────────────────────────────────────────────────────
    # Reconciliation  (Phase 7.1 core)
    # ──────────────────────────────────────────────────────────────────────────

    def reconcile_goal(self, goal_id):
        """
        Inspect all steps for goal_id, cross-reference linked pending_actions,
        and update step + goal statuses accordingly.

        Status flow per step:
          pending_action.status == 'executed'  → step completed
          pending_action.status == 'rejected'  → step blocked (with reason)
          pending_action.status == 'failed'    → step failed (with reason)
          pending_action.status == 'approved'  → step still awaiting_approval (approved, not yet run)
          pending_action.status == 'partial'   → step blocked with partial result
          web result reason in SAFETY_BLOCK_REASONS → step blocked with safety reason
        """
        goal = self.get_goal_context(goal_id)
        if not goal:
            return {"error": "Goal not found"}

        steps = goal.get('steps', [])
        plan = goal.get('current_plan')
        plan_id = plan['id'] if plan else None

        goal_has_blocked = False
        goal_has_failed = False
        goal_has_awaiting = False
        all_done = bool(steps)  # true until proven otherwise

        for step in steps:
            sid = step['id']
            old_status = step['status']

            # If already terminal, skip
            if old_status in ('completed', 'failed'):
                if old_status == 'failed':
                    goal_has_failed = True
                continue

            if old_status == 'blocked':
                goal_has_blocked = True
                all_done = False
                continue

            action_ref = step.get('action_ref')
            new_status = old_status
            reason = None
            result_ref = None
            result_json_val = None

            if action_ref:
                action = self.memory_engine.get_pending_action(action_ref)
                if action:
                    a_status = action.get('status', '')
                    notes = action.get('notes') or ''

                    if a_status == 'executed':
                        # Attach structured result from result_ref / notes JSON
                        result_ref = action.get('result_ref')
                        try:
                            result_json_val = json.loads(notes) if notes else None
                        except (json.JSONDecodeError, TypeError):
                            result_json_val = None

                        # Check for safety block in result
                        blocked_by_safety = False
                        if result_json_val and isinstance(result_json_val, dict):
                            block_reason = result_json_val.get('block_reason', '')
                            if block_reason in SAFETY_BLOCK_REASONS:
                                blocked_by_safety = True
                                new_status = 'blocked'
                                reason = f"Safety gate: {block_reason}"

                        if not blocked_by_safety:
                            exec_status = (result_json_val or {}).get('status', '')
                            if exec_status == 'partial':
                                new_status = 'blocked'
                                reason = result_json_val.get('block_reason', 'Partial execution')
                            else:
                                new_status = 'completed'
                                reason = 'Action executed successfully'

                    elif a_status == 'rejected':
                        new_status = 'blocked'
                        reason = 'Pending action was rejected'

                    elif a_status == 'failed':
                        new_status = 'failed'
                        reason = 'Pending action failed'

                    elif a_status in ('approved', 'pending'):
                        # Still waiting for execution
                        new_status = 'awaiting_approval'

            # Apply transitions
            if new_status != old_status:
                updates = {
                    'status': new_status,
                    'last_transition_at': datetime.now().isoformat(),
                    'last_transition_reason': reason,
                }
                if result_ref:
                    updates['result_ref'] = result_ref
                if result_json_val:
                    updates['result_json'] = json.dumps(result_json_val)
                if new_status in ('blocked', 'failed') and reason:
                    updates['error'] = reason

                self.memory_engine.update_plan_step_record(sid, updates)
                self.memory_engine.log_goal_event(
                    goal_id, 'step_status_changed',
                    from_status=old_status, to_status=new_status,
                    reason=reason, plan_id=plan_id, step_id=sid,
                    action_ref=action_ref, result_ref=result_ref
                )
                # Refresh step for goal-level logic
                step['status'] = new_status

            # Collect goal-level signals
            if step['status'] == 'completed':
                pass  # all_done stays True if every step is done
            elif step['status'] == 'blocked':
                goal_has_blocked = True
                all_done = False
            elif step['status'] == 'failed':
                goal_has_failed = True
                all_done = False
            elif step['status'] == 'awaiting_approval':
                goal_has_awaiting = True
                all_done = False
            elif step['status'] == 'pending':
                all_done = False

        # ── Derive overall goal status ──────────────────────────────────────
        old_goal_status = goal['status']
        new_goal_status = old_goal_status

        if goal_has_failed:
            new_goal_status = 'failed'
        elif goal_has_blocked:
            new_goal_status = 'blocked'
        elif goal_has_awaiting:
            new_goal_status = 'awaiting_approval'
        elif all_done and steps:
            new_goal_status = 'completed'
        elif old_goal_status in ('awaiting_approval', 'blocked') and not goal_has_awaiting and not goal_has_blocked:
            # After reconciliation, all blocking conditions cleared → back to active
            if any(s['status'] == 'pending' for s in steps):
                new_goal_status = 'active'

        if new_goal_status != old_goal_status:
            self.memory_engine.update_goal_record(goal_id, {'status': new_goal_status})
            self.memory_engine.log_goal_event(
                goal_id, 'reconciliation_updated',
                from_status=old_goal_status, to_status=new_goal_status,
                reason='reconcile_goal()', plan_id=plan_id
            )
            if new_goal_status == 'completed' and self.notification_callback:
                self.notification_callback('completed', goal)
            elif new_goal_status in ('failed', 'blocked') and self.notification_callback:
                self.notification_callback('failed', goal)

        # Count waiting approvals
        waiting_approvals = [s['action_ref'] for s in steps if s.get('status') == 'awaiting_approval' and s.get('action_ref')]

        return {
            "goal_id": goal_id,
            "reconciled": True,
            "old_status": old_goal_status,
            "new_status": new_goal_status,
            "waiting_approvals": waiting_approvals,
            "steps_total": len(steps),
            "steps_completed": sum(1 for s in steps if s['status'] == 'completed'),
            "steps_blocked": sum(1 for s in steps if s['status'] in ('blocked', 'failed')),
        }

    def reconcile_all_goals(self):
        """Bulk reconcile all non-terminal goals. Safe for admin/dashboard use."""
        goals = self.memory_engine.get_all_goals()
        results = []
        for g in goals:
            if g['status'] not in ('completed', 'failed', 'blocked', 'draft'):
                r = self.reconcile_goal(g['id'])
                results.append(r)
        return {"reconciled_count": len(results), "results": results}

    # ──────────────────────────────────────────────────────────────────────────
    # Resume logic  (Phase 7.1)
    # ──────────────────────────────────────────────────────────────────────────

    def edit_goal(self, goal_id, updates):
        goal = self.memory_engine.get_goal_record(goal_id)
        if not goal:
            return {"error": "Goal not found"}
        if goal['status'] in ('completed', 'failed'):
            return {"error": f"Cannot edit a {goal['status']} goal"}

        allowed = {}
        for field in ('title', 'objective', 'priority', 'summary'):
            if field in updates and updates[field] is not None:
                allowed[field] = updates[field]
        if not allowed:
            return {"error": "No editable fields provided"}

        self.memory_engine.update_goal_record(goal_id, allowed)
        self.memory_engine.log_goal_event(
            goal_id,
            'goal_edited',
            from_status=goal['status'],
            to_status=goal['status'],
            reason=f"fields={','.join(sorted(allowed.keys()))}"
        )
        updated = self.memory_engine.get_goal_record(goal_id)
        return {"goal": updated, "updated_fields": sorted(allowed.keys())}

    def pause_goal(self, goal_id, reason="Paused by owner"):
        goal = self.memory_engine.get_goal_record(goal_id)
        if not goal:
            return {"error": "Goal not found"}
        if goal['status'] not in ('planned', 'active', 'awaiting_approval'):
            return {"error": f"Cannot pause goal in status '{goal['status']}'"}

        self.memory_engine.update_goal_record(goal_id, {'status': 'paused'})
        self.memory_engine.log_goal_event(
            goal_id,
            'goal_paused',
            from_status=goal['status'],
            to_status='paused',
            reason=reason
        )
        return {"goal_id": goal_id, "paused": True, "status": "paused", "reason": reason}

    def stop_goal(self, goal_id, reason="Stopped by owner"):
        goal = self.memory_engine.get_goal_record(goal_id)
        if not goal:
            return {"error": "Goal not found"}
        if goal['status'] in ('completed', 'failed', 'stopped'):
            return {"error": f"Cannot stop goal in status '{goal['status']}'"}

        self.memory_engine.update_goal_record(goal_id, {'status': 'stopped', 'last_error': reason})
        self.memory_engine.log_goal_event(
            goal_id,
            'goal_stopped',
            from_status=goal['status'],
            to_status='stopped',
            reason=reason
        )
        return {"goal_id": goal_id, "stopped": True, "status": "stopped", "reason": reason}

    def resume_goal(self, goal_id, brain):
        """
        Reconcile first, then continue execution if safe.
        Returns a structured resume result.
        """
        rec = self.reconcile_goal(goal_id)
        if "error" in rec:
            return rec

        goal = self.get_goal_context(goal_id)
        if not goal:
            return {"error": "Goal not found"}
        status = goal['status']

        if status == 'paused':
            self.memory_engine.update_goal_record(goal_id, {'status': 'planned'})
            self.memory_engine.log_goal_event(
                goal_id,
                'goal_resumed',
                from_status='paused',
                to_status='planned',
                reason='Resume requested by owner',
            )
            goal = self.get_goal_context(goal_id)
            status = goal['status']

        if status not in ('planned', 'active', 'awaiting_approval'):
            return {
                "goal_id": goal_id,
                "resumed": False,
                "status": status,
                "reason": f"Cannot resume goal in status '{status}'",
            }

        # If still awaiting approval, surface it
        steps = goal.get('steps', [])
        waiting = [s for s in steps if s.get('status') == 'awaiting_approval']
        if waiting:
            ws = waiting[0]
            return {
                "goal_id": goal_id,
                "resumed": False,
                "status": "awaiting_approval",
                "next_step": {
                    "step_id": ws['id'],
                    "title": ws['title'],
                    "status": "awaiting_approval",
                    "action_ref": ws.get('action_ref'),
                },
                "recommended_next_action": f"Approve pending action {ws.get('action_ref')}",
                "can_resume": False,
            }

        # Find the next pending step
        idx, next_pending = self._get_next_actionable_step(steps, goal.get('current_step_index', 0))
        if idx != goal.get('current_step_index', 0):
            self.memory_engine.update_goal_record(goal_id, {'current_step_index': idx})

        if not next_pending:
            # Check if all completed
            if all(s['status'] == 'completed' for s in steps):
                self.memory_engine.update_goal_record(goal_id, {'status': 'completed'})
                self.memory_engine.log_goal_event(
                    goal_id, 'goal_completed', from_status=status, to_status='completed',
                    reason='All steps completed on resume'
                )
                if self.notification_callback:
                    self.notification_callback('completed', goal)
                return {
                    "goal_id": goal_id,
                    "resumed": True,
                    "status": "completed",
                    "recommended_next_action": None,
                    "can_resume": False,
                }
            return {
                "goal_id": goal_id,
                "resumed": False,
                "status": status,
                "reason": "No pending steps to advance",
                "can_resume": False,
            }

        # Advance the next eligible step
        ok, msg = self.advance_goal(goal_id, brain)

        # Re-fetch after advance
        goal2 = self.get_goal_context(goal_id) or goal
        summary = self.summarize_goal(goal_id) or {}
        completed_count = sum(1 for s in goal2.get('steps', []) if s['status'] == 'completed')
        next_step_after = summary.get("current_step")

        return {
            "goal_id": goal_id,
            "resumed": ok,
            "status": goal2.get('status'),
            "completed_steps": completed_count,
            "next_step": {
                "step_id": next_step_after.get('step_id') or next_step_after.get('id'),
                "title": next_step_after['title'],
                "status": next_step_after['status'],
                "action_ref": next_step_after.get('action_ref'),
            } if next_step_after else None,
            "recommended_next_action": (
                f"Approve pending action {next_step_after.get('action_ref')}"
                if next_step_after and next_step_after.get('action_ref')
                else (summary.get('recommended_next_action') if summary else ("advance" if goal2.get('status') in ('planned', 'active') else None))
            ),
            "can_resume": bool(summary.get('can_resume')),
            "message": msg,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Step execution (advance)
    # ──────────────────────────────────────────────────────────────────────────

    def advance_goal(self, goal_id, brain):
        """
        Reconcile first, then execute the next step in the current plan.
        """
        # Always reconcile before acting to ensure consistent state
        self.reconcile_goal(goal_id)

        goal = self.get_goal_context(goal_id)
        if not goal:
            return False, "Goal not found"

        if goal['status'] not in ['planned', 'active']:
            return False, f"Cannot advance goal in status '{goal['status']}'"

        steps = goal.get('steps', [])
        idx, step = self._get_next_actionable_step(steps, goal.get('current_step_index', 0))
        if idx != goal.get('current_step_index', 0):
            self.memory_engine.update_goal_record(goal_id, {'current_step_index': idx})

        if step is None:
            self.memory_engine.update_goal_record(goal_id, {'status': 'completed', 'summary': "All steps completed."})
            self.memory_engine.log_goal_event(goal_id, 'goal_completed', to_status='completed', reason='All steps done')
            if self.notification_callback:
                self.notification_callback('completed', goal)
            return True, "Goal completed"

        runtime = self._get_runtime(brain)
        if brain is not None and not brain.permissions.is_allowed("goals.execute", runtime=runtime):
            block = brain.permissions.build_permission_block(
                "goals.execute",
                "Goal execution is disabled, so Jarvis cannot continue this goal.",
                goal_id=goal['id'],
                goal_title=goal.get('title'),
                action_label=step.get('title') or 'Advance goal',
                source="goal_execute",
            )
            self._block_goal_for_permission(goal, step, "goals.execute", block.get("permission_name"), block["message"])
            return False, block["message"]

        if step['status'] == 'completed':
            self.memory_engine.update_goal_record(goal_id, {'current_step_index': idx + 1})
            return self.advance_goal(goal_id, brain)

        if step['status'] in ['blocked', 'failed']:
            new_status = 'blocked' if step['status'] == 'blocked' else 'failed'
            reason = step.get('error') or step.get('last_transition_reason') or f"Step {idx} {step['status']}"
            self.memory_engine.update_goal_record(goal_id, {'status': new_status, 'last_error': reason})
            self.memory_engine.log_goal_event(
                goal_id, 'goal_blocked', from_status='active', to_status=new_status,
                reason=reason, step_id=step['id']
            )
            if self.notification_callback:
                self.notification_callback('failed', goal)
            return False, f"Process halted: {reason}"

        if step['status'] == 'pending':
            self.memory_engine.update_goal_record(goal_id, {'status': 'active'})

            permission_key = brain.permissions.step_permission_key(step) if brain is not None else None
            if permission_key and not brain.permissions.is_allowed(permission_key, runtime=runtime):
                block = brain.permissions.build_permission_block(
                    permission_key,
                    f"Step '{step.get('title') or step.get('id')}' depends on this capability being enabled.",
                    goal_id=goal['id'],
                    goal_title=goal.get('title'),
                    action_label=step.get('title') or step.get('capability_type'),
                    source="goal_step",
                )
                self._block_goal_for_permission(goal, step, permission_key, block.get("permission_name"), block["message"])
                return False, block["message"]

            capability_type = step.get('capability_type')

            if capability_type in ('web', 'web_plan'):
                payload = {
                    "objective": step.get('description') or goal.get('objective'),
                    "steps": [],
                    "goal_id": goal_id,
                    "step_id": step['id'],
                    "title": step.get('title'),
                }

                if step.get('requires_approval'):
                    return self._queue_owner_review_step(
                        goal,
                        step,
                        'web.plan.execute',
                        payload,
                        'Approval required for governed web execution',
                    )

                if brain is not None and getattr(brain, "web_automation", None):
                    res = brain.web_automation.run_plan(payload)
                else:
                    res = {'status': 'success', 'session_id': 'mock'}

                if res.get('status') == 'success':
                    return self._complete_and_advance(
                        goal,
                        step,
                        'Web automation completed',
                        result_json=res,
                        result_ref=res.get('session_id'),
                    )

                ts = datetime.now().isoformat()
                status = 'blocked' if res.get('status') == 'blocked' else 'failed'
                reason = res.get('reason') or res.get('error') or 'Web automation failed'
                self.memory_engine.update_plan_step_record(step['id'], {
                    'status': status,
                    'error': reason,
                    'result_json': json.dumps(res),
                    'last_transition_at': ts,
                    'last_transition_reason': reason,
                })
                self.memory_engine.update_goal_record(goal_id, {'status': status, 'last_error': reason})
                self.memory_engine.log_goal_event(
                    goal_id,
                    'step_failed' if status == 'failed' else 'goal_blocked',
                    from_status='pending',
                    to_status=status,
                    step_id=step['id'],
                    reason=reason,
                )
                if self.notification_callback:
                    self.notification_callback('failed', goal)
                return False, reason

            if capability_type == 'chat':
                draft_output = (
                    f"Draft output for '{step.get('title') or 'chat step'}': "
                    f"{step.get('description') or goal.get('objective')}"
                )
                payload = {
                    "title": step.get('title'),
                    "description": draft_output,
                    "goal_id": goal_id,
                    "step_id": step['id'],
                    "capability_type": capability_type,
                }
                if step.get('requires_approval'):
                    return self._queue_owner_review_step(
                        goal,
                        step,
                        'chat.review.complete',
                        payload,
                        'Owner review required before accepting the drafted output',
                    )
                return self._complete_and_advance(
                    goal,
                    step,
                    'Drafted output prepared',
                    result_json={"status": "success", "draft_output": draft_output},
                    result_ref=f"draft:{step['id']}",
                )

            if capability_type in ('manual', 'gmail_draft', 'calendar_proposal'):
                payload = {
                    "title": step.get('title'),
                    "description": step.get('description') or goal.get('objective') or 'Owner review step',
                    "goal_id": goal_id,
                    "step_id": step['id'],
                    "capability_type": capability_type,
                }
                reason = 'Owner confirmation is required to complete this step'
                if capability_type == 'gmail_draft':
                    reason = 'Integration-specific email work is owner reviewed in the current build'
                elif capability_type == 'calendar_proposal':
                    reason = 'Calendar proposals stay owner reviewed in the current build'
                return self._queue_owner_review_step(
                    goal,
                    step,
                    'manual.review.complete',
                    payload,
                    reason,
                )

            if capability_type == 'reasoning':
                return self._complete_and_advance(goal, step, 'Reasoning step resolved')

            payload = {
                "title": step.get('title'),
                "description": step.get('description') or 'Unsupported step capability requires owner review',
                "goal_id": goal_id,
                "step_id": step['id'],
                "capability_type": capability_type,
            }
            return self._queue_owner_review_step(
                goal,
                step,
                'manual.review.complete',
                payload,
                f"Capability '{capability_type}' falls back to owner review in this build",
            )

        elif step['status'] == 'awaiting_approval':
            # Re-run reconcile to pick up any changes
            self.reconcile_goal(goal_id)
            goal = self.get_goal_context(goal_id)
            step_refreshed = next((s for s in goal.get('steps', []) if s['id'] == step['id']), step)

            if step_refreshed['status'] == 'completed':
                self.memory_engine.update_goal_record(goal_id, {'current_step_index': idx + 1, 'status': 'active'})
                return self.advance_goal(goal_id, brain)
            elif step_refreshed['status'] in ('blocked', 'failed'):
                return False, step_refreshed.get('error') or "Underlying action failed/rejected"
            else:
                return True, "Still awaiting approval/execution of queued action"

        return False, "Step in unexpected state"

    # ──────────────────────────────────────────────────────────────────────────
    # Summary  (upgraded Phase 7.1)
    # ──────────────────────────────────────────────────────────────────────────

    def summarize_goal(self, goal_id):
        """
        Returns a fully structured, mobile-ready summary of a goal's state.
        """
        goal = self.get_goal_context(goal_id)
        if not goal:
            return None

        steps = goal.get('steps', [])
        plan = goal.get('current_plan')
        total = len(steps)
        completed = sum(1 for s in steps if s['status'] == 'completed')
        blocked = sum(1 for s in steps if s['status'] in ('blocked', 'failed'))
        idx, current_step = self._get_next_actionable_step(steps, goal.get('current_step_index', 0))

        waiting_approvals = [
            {'step_id': s['id'], 'action_ref': s.get('action_ref'), 'title': s.get('title')}
            for s in steps if s.get('status') == 'awaiting_approval' and s.get('action_ref')
        ]

        current_step_info = None
        if current_step:
            current_step_info = {
                'step_id': current_step['id'],
                'title': current_step['title'],
                'status': current_step['status'],
                'action_ref': current_step.get('action_ref'),
                'result_ref': current_step.get('result_ref'),
                'blocked_reason': current_step.get('error') or current_step.get('last_transition_reason'),
            }

        # All result refs (for audit)
        result_refs = [s.get('result_ref') for s in steps if s.get('result_ref')]

        # Can resume?
        can_resume = bool(
            goal['status'] in ('planned', 'active', 'paused')
            and total > 0
            and not waiting_approvals
            and completed < total
        )

        events = self.memory_engine.get_goal_events(goal_id, limit=1)
        last_event = events[0] if events else None

        # Recommended next action
        if waiting_approvals:
            action_txt = f"Approve pending action {waiting_approvals[0]['action_ref']}"
        elif goal['status'] in ('planned', 'active'):
            action_txt = "advance"
        elif goal['status'] == 'paused':
            action_txt = "Resume or stop the paused goal after reviewing its dependencies"
        elif goal['status'] == 'completed':
            action_txt = None
        elif goal['status'] in ('blocked', 'failed'):
            action_txt = "Inspect blocked_reason and resolve or retry"
        elif goal['status'] == 'stopped':
            action_txt = "Edit or replan the goal before starting a replacement run"
        else:
            action_txt = None

        step_status_counts = {
            "pending": sum(1 for s in steps if s['status'] == 'pending'),
            "awaiting_approval": len(waiting_approvals),
            "completed": completed,
            "blocked": sum(1 for s in steps if s['status'] == 'blocked'),
            "failed": sum(1 for s in steps if s['status'] == 'failed'),
        }

        return {
            "goal_id": goal['id'],
            "title": goal.get('title'),
            "status": goal['status'],
            "progress": f"{completed}/{total}",
            "completed_steps": completed,
            "total_steps": total,
            "blocked_steps": blocked,
            "blocked_reason": goal.get('last_error'),
            "current_step": current_step_info,
            "waiting_approvals": waiting_approvals,
            "result_refs": result_refs,
            "last_event": {
                "event_type": last_event['event_type'],
                "from_status": last_event.get('from_status'),
                "to_status": last_event.get('to_status'),
                "reason": last_event.get('reason'),
                "created_at": last_event.get('created_at'),
            } if last_event else None,
            "can_resume": can_resume,
            "recommended_next_action": action_txt,
            "step_status_counts": step_status_counts,
            "execution_state": {
                "status": goal['status'],
                "is_terminal": goal['status'] in ('completed', 'failed', 'stopped'),
                "is_blocked": goal['status'] == 'blocked',
                "is_paused": goal['status'] == 'paused',
                "waiting_for_approval": bool(waiting_approvals),
            },
            "next_step_guidance": action_txt or "No further action is currently required.",
            # ── Phase 7.2 provenance ──────────────────────────────────────
            "planner_type": plan.get('planner_type') if plan else None,
            "planner_provider": plan.get('planner_provider') if plan else None,
            "planner_warnings": (
                json.loads(plan['planner_warnings'])
                if plan and plan.get('planner_warnings') else []
            ),
            "fallback_used": (
                (plan.get('planner_type') == 'fallback') if plan else True
            ),
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Event history
    # ──────────────────────────────────────────────────────────────────────────

    def get_goal_events(self, goal_id, limit=100):
        """Return structured event history for a goal."""
        return self.memory_engine.get_goal_events(goal_id, limit=limit)

    # ──────────────────────────────────────────────────────────────────────────
    # Legacy shims
    # ──────────────────────────────────────────────────────────────────────────

    def get_goal_by_id(self, goal_id):
        return self.get_goal_context(goal_id)

    def update_steps(self, goal_id, steps):
        pass

    def complete_goal(self, goal_id):
        self.memory_engine.update_goal_record(goal_id, {'status': 'completed'})

    def update_goal_status(self, goal_id, status):
        self.memory_engine.update_goal_record(goal_id, {'status': status})
