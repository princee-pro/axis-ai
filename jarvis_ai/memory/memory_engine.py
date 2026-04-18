"""
Memory Engine.
Handles persistent storage of goal execution history and learning analytics using Supabase.
"""
import os
import json
import hashlib
import uuid
import secrets
from datetime import datetime, timedelta
import threading

# — Token hashing backend —
# Prefer bcrypt (strong adaptive hash). Fallback: sha256(salt + token) with per-device salt.
try:
    import bcrypt as _bcrypt
    _BCRYPT_AVAILABLE = True
except ImportError:
    _BCRYPT_AVAILABLE = False

from jarvis_ai.db.supabase_client import get_supabase
import time

def db_retry(max_retries=3, backoff=0.5):
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_err = None
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    if "10035" in str(e) or "connection" in str(e).lower():
                        print(f"[MEMORY] DB Retry {i+1}/{max_retries} due to: {e}")
                        time.sleep(backoff * (i + 1))
                        continue
                    raise e
            raise last_err
        return wrapper
    return decorator

class MemoryEngine:
    def _execute(self, query):
        @db_retry()
        def _run():
            return query.execute()
        return _run()

    def __init__(self, db_path=None):
        self._lock = threading.Lock()
        # Initialize early to test credentials (optional)
        try:
            get_supabase()
        except Exception as e:
            print(f"[MEMORY] INIT Failed to connect to Supabase: {e}")
        print("[MEMORY] Initialized Supabase Memory Engine.")

    def close(self):
        """No transient resources to close with Supabase client."""
        pass

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def get_setting(self, key, default=None):
        with self._lock:
            try:
                res = self._execute(get_supabase().table("system_settings").select("value").eq("key", key))
                return res.data[0]["value"] if res.data else default
            except Exception as e:
                print(f"[MEMORY] DB Error get_setting: {e}")
                return default

    def set_setting(self, key, value):
        with self._lock:
            try:
                self._execute(get_supabase().table("system_settings").upsert({"key": key, "value": str(value)}))
            except Exception as e:
                print(f"[MEMORY] DB Error set_setting: {e}")

    def get_json_setting(self, key, default=None):
        raw = self.get_setting(key)
        if raw in (None, ""):
            return default
        try:
            return json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return default

    def set_json_setting(self, key, value):
        self.set_setting(key, json.dumps(value))

    def record_execution(self, goal_data, success=True, duration=0, deadline_missed=False):
        tags = ",".join(goal_data.get('tags', []))
        created_at = goal_data.get('created_at', datetime.now().isoformat())
        completed_at = datetime.now().isoformat()
        decision_context = json.dumps(goal_data.get('decision_trace', {}))
        risk_at_execution = goal_data.get('risk_at_execution', 0.0)
        weights_at_execution = json.dumps(goal_data.get('weights', {}))
        try:
            self._execute(get_supabase().table("goal_history").insert({
                "goal_id": goal_data.get('id'), "description": goal_data.get('description'), 
                "tags": tags, "created_at": created_at, "completed_at": completed_at, 
                "duration_seconds": duration, "success": True if success else False, 
                "retry_count": goal_data.get('retry_count', 0), 
                "deadline_missed": True if deadline_missed else False, 
                "decision_context": decision_context, "risk_at_execution": risk_at_execution, 
                "weights_at_execution": weights_at_execution
            }))
        except Exception as e:
            print(f"[MEMORY] DB Error record_execution: {e}")

    def record_advisory(self, proposal_type, content, meta_goal=None, gov_status='pending', gov_reason='', tokens=0, cost=0.0):
        try:
            self._execute(get_supabase().table("llm_advisory_log").insert({
                "timestamp": datetime.now().isoformat(), "proposal_type": proposal_type, 
                "content": content, "suggested_meta_goal": json.dumps(meta_goal) if meta_goal else None, 
                "governance_status": gov_status, "governance_reason": gov_reason, 
                "tokens_used": tokens, "cost_usd": cost, "execution_flag": 'LLM-origin'
            }))
        except Exception as e:
            print(f"[MEMORY] DB Error record_advisory: {e}")

    # For analytics, getting all data in Supabase might be large but we mimic the local call.
    def get_analytics(self):
        try:
            res = self._execute(get_supabase().table("goal_history").select("*"))
            rows = res.data
            total = len(rows)
            successful = sum(1 for r in rows if r.get('success'))
            success_rate = (successful / total * 100) if total > 0 else 0
            successful_rows = [r for r in rows if r.get('success')]
            avg_duration = sum(r.get('duration_seconds', 0) for r in successful_rows) / len(successful_rows) if successful_rows else 0
            
            tag_stats = {}
            for row in rows:
                if row.get('tags'):
                    for tag in str(row['tags']).split(','):
                        tag = tag.strip()
                        if not tag: continue
                        if tag not in tag_stats: tag_stats[tag] = {'total': 0, 'success': 0}
                        tag_stats[tag]['total'] += 1
                        if row.get('success'): tag_stats[tag]['success'] += 1
            formatted_tag_stats = [{'tag': t, 'total': s['total'], 'success_rate': round(s['success']/s['total']*100, 2)} for t, s in tag_stats.items()]
            
            fourteen_days_ago = (datetime.now() - timedelta(days=14)).isoformat()
            recent_rows = [r for r in rows if r.get('completed_at') and r['completed_at'] >= fourteen_days_ago]
            desc_counts = {}
            for r in recent_rows:
                desc = r.get('description')
                if desc:
                    desc_counts[desc] = desc_counts.get(desc, 0) + 1
            repeated = [{'description': d, 'count': c} for d, c in desc_counts.items() if c >= 3]

            return {'overall_success_rate': round(success_rate, 2), 'total_goals': total, 'avg_duration': round(avg_duration, 2), 'tag_stats': formatted_tag_stats, 'repeated_patterns': repeated}
        except Exception as e:
            print(f"[MEMORY] DB Error get_analytics: {e}")
            return {'overall_success_rate': 0, 'total_goals': 0, 'avg_duration': 0, 'tag_stats': [], 'repeated_patterns': []}

    def get_pilot_metrics(self):
        try:
            res = self._execute(get_supabase().table("goal_history").select("*"))
            rows = res.data
            total_count = len(rows)
            if total_count == 0:
                return {'mttc': 0, 'deadline_adherence': 0, 'retry_rate': 0, 'adoption_rate': 0}
            
            avg_duration = sum(r.get('duration_seconds', 0) or 0 for r in rows) / total_count
            deadline_met = sum(1 for r in rows if r.get('deadline_missed') == False)
            deadline_adherence = (deadline_met / total_count) * 100
            total_retries = sum(r.get('retry_count', 0) or 0 for r in rows)
            retry_rate = (total_retries / total_count) * 100
            meta_count = sum(1 for r in rows if r.get('tags') and 'system_improvement' in r['tags'])
            adoption_rate = (meta_count / total_count) * 100
            return {'mttc': round(avg_duration, 2), 'deadline_adherence': round(deadline_adherence, 2), 'retry_rate': round(retry_rate, 2), 'adoption_rate': round(adoption_rate, 2)}
        except Exception as e:
            print(f"[MEMORY] DB Error get_pilot_metrics: {e}")
            return {'mttc': 0, 'deadline_adherence': 0, 'retry_rate': 0, 'adoption_rate': 0}

    def search_long_term_memory(self, query, limit=5):
        with self._lock:
            try:
                res = self._execute(get_supabase().table("long_term_memory").select("id, text, tags, source, importance").ilike("text", f"%{query}%").limit(limit))
                # To closely emulate the OR condition for `tags LIKE pattern`:
                res2 = self._execute(get_supabase().table("long_term_memory").select("id, text, tags, source, importance").ilike("tags", f"%{query}%").limit(limit))
                
                # Merge and disambiguate
                results_dict = {r["id"]: r for r in res.data}
                for r in res2.data:
                    results_dict[r["id"]] = r
                merged = list(results_dict.values())
                merged.sort(key=lambda x: x["id"], reverse=True) # match ORDER BY id DESC limits
                return merged[:limit]
            except Exception as e:
                print(f"[MEMORY] DB Error search_long_term_memory: {e}")
                return []

    def list_long_term_memories(self, limit=100):
        try:
            res = self._execute(get_supabase().table("long_term_memory").select("id, text, tags, source, importance, created_at").order("id", desc=True).limit(limit))
            return res.data
        except Exception as e:
            print(f"[MEMORY] DB Error list_long_term_memories: {e}")
            return []

    def delete_long_term_memory(self, memory_id):
        try:
            self._execute(get_supabase().table("long_term_memory").delete().eq("id", memory_id))
            return True
        except Exception as e:
            print(f"[MEMORY] DB Error delete_long_term_memory: {e}")
            return False

    def add_message(self, conversation_id, role, content, actions=None, routing=None):
        actions_json = None
        if isinstance(actions, list) and actions:
            try:
                actions_json = actions # Supabase JSONB expects dict/list
            except (TypeError, ValueError):
                actions_json = None
        routing_json = None
        if isinstance(routing, dict) and routing:
            try:
                routing_json = routing
            except (TypeError, ValueError):
                routing_json = None
                
        try:
            # Check conversation_id existence
            c_res = self._execute(get_supabase().table("conversations").select("id").eq("id", conversation_id))
            if not c_res.data:
                self._execute(get_supabase().table("conversations").insert({"id": conversation_id, "created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat()}))
            else:
                self._execute(get_supabase().table("conversations").update({"updated_at": datetime.now().isoformat()}).eq("id", conversation_id))

            self._execute(get_supabase().table("messages").insert({
                "conversation_id": conversation_id, "role": role, "content": content,
                "timestamp": datetime.now().isoformat(), "actions_json": actions_json, "routing_json": routing_json
            }))
        except Exception as e:
            print(f"[MEMORY] DB Error add_message: {e}")

    def get_messages(self, conversation_id, limit=50):
        try:
            res = self._execute(get_supabase().table("messages").select("role, content, timestamp, actions_json, routing_json").eq("conversation_id", conversation_id).order("timestamp").limit(limit))
            messages = []
            for row in res.data:
                item = {
                    "role": row.get("role"),
                    "content": row.get("content"),
                    "timestamp": row.get("timestamp"),
                    "actions": row.get("actions_json") or [],
                    "routing": row.get("routing_json") or {},
                }
                messages.append(item)
            return messages
        except Exception as e:
            print(f"[MEMORY] DB Error get_messages: {e}")
            return []

    def set_summary(self, conversation_id, summary_text, version=1):
        try:
            self._execute(get_supabase().table("summaries").upsert({
                "conversation_id": conversation_id, "summary": summary_text,
                "created_at": datetime.now().isoformat(), "message_count": version
            }))
        except Exception as e:
            print(f"[MEMORY] DB Error set_summary: {e}")

    def get_summary(self, conversation_id):
        try:
            res = self._execute(get_supabase().table("summaries").select("summary, message_count").eq("conversation_id", conversation_id))
            return {"summary_text": res.data[0]["summary"], "version": res.data[0]["message_count"]} if res.data else None
        except Exception as e:
            print(f"[MEMORY] DB Error get_summary: {e}")
            return None

    def save_long_term_memory(self, text, tags="", source="chat", importance="normal"):
        try:
            self._execute(get_supabase().table("long_term_memory").insert({
                "text": text, "tags": tags, "source": source, "importance": importance,
                "created_at": datetime.now().isoformat()
            }))
            return True
        except Exception as e:
            print(f"[MEMORY] DB Error save_long_term_memory: {e}")
            return False

    def create_pending_action(self, action_id, action_type, payload, created_by="system"):
        try:
            self._execute(get_supabase().table("pending_actions").insert({
                "id": action_id, "type": action_type, "payload": payload,
                "status": "pending", "created_at": datetime.now().isoformat(), "created_by": created_by
            }))
        except Exception as e:
            print(f"[MEMORY] DB Error create_pending_action: {e}")

    def list_pending_actions(self, status='pending'):
        try:
            res = self._execute(get_supabase().table("pending_actions").select("*").eq("status", status).order("created_at", desc=True))
            return res.data
        except Exception as e:
            print(f"[MEMORY] DB Error list_pending_actions: {e}")
            return []

    def count_pending_actions(self, status='pending'):
        try:
            if status == 'actionable':
                res1 = self._execute(get_supabase().table("pending_actions").select("id").eq("status", "pending"))
                res2 = self._execute(get_supabase().table("pending_actions").select("id").eq("status", "approved"))
                return len(res1.data) + len(res2.data)
            elif status == 'all':
                res = self._execute(get_supabase().table("pending_actions").select("id"))
                return len(res.data)
            else:
                res = self._execute(get_supabase().table("pending_actions").select("id").eq("status", status))
                return len(res.data)
        except Exception as e:
            print(f"[MEMORY] DB Error count_pending_actions: {e}")
            return 0

    def get_pending_action(self, action_id):
        try:
            res = self._execute(get_supabase().table("pending_actions").select("*").eq("id", action_id))
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[MEMORY] DB Error get_pending_action: {e}")
            return None

    def update_action_status(self, action_id, status, notes=None, result_ref=None):
        updates = {"status": status}
        if status == 'approved':
            updates["approved_at"] = datetime.now().isoformat()
        elif status in ['executed', 'failed', 'partial', 'rejected']:
            updates["executed_at"] = datetime.now().isoformat()
        if notes is not None:
            updates["notes"] = notes
        if result_ref is not None:
            updates["result_ref"] = result_ref
        try:
             self._execute(get_supabase().table("pending_actions").update(updates).eq("id", action_id))
             return True
        except Exception as e:
             print(f"[MEMORY] DB Error update_action_status: {e}")
             return False

    def get_pending_action_status_counts(self):
        try:
            res = self._execute(get_supabase().table("pending_actions").select("status"))
            counts = {
                "pending": 0, "approved": 0, "executed": 0, "rejected": 0, "failed": 0, "partial": 0,
            }
            for r in res.data:
                st = r.get("status")
                if st in counts:
                    counts[st] += 1
            counts["actionable"] = counts.get("pending", 0) + counts.get("approved", 0)
            counts["recent_activity"] = counts.get("executed", 0) + counts.get("rejected", 0) + counts.get("failed", 0) + counts.get("partial", 0)
            return counts
        except Exception as e:
            print(f"[MEMORY] DB Error get_pending_action_status_counts: {e}")
            return {"pending":0,"approved":0,"executed":0,"rejected":0,"failed":0,"partial":0,"actionable":0,"recent_activity":0}

    # ── Phase 7 Goal Engine DB Operations ────────────────────────────────────
    
    def create_permission_request(self, permission_key, title, reason, goal_id=None, goal_title=None, action_label=None, source="system", requested_by="jarvis", requested_state="enabled", context=None):
        existing = self.find_pending_permission_request(permission_key=permission_key, goal_id=goal_id, action_label=action_label)
        if existing:
            return existing
        request_id = str(uuid.uuid4())[:12]
        row = {
            "id": request_id, "permission_key": permission_key, "title": title, "reason": reason, "goal_id": goal_id, "goal_title": goal_title,
            "action_label": action_label, "source": source, "requested_by": requested_by, "requested_state": requested_state,
            "status": "pending", "context_json": context or {}, "created_at": datetime.now().isoformat()
        }
        try:
            self._execute(get_supabase().table("permission_requests").insert(row))
            return row
        except Exception as e:
            print(f"[MEMORY] DB Error create_permission_request: {e}")
            return None

    def list_permission_requests(self, status=None, limit=50):
        try:
            q = get_supabase().table("permission_requests").select("*").order("created_at", desc=True).limit(limit)
            if status: q = q.eq("status", status)
            res = self._execute(q)
            results = []
            for item in res.data:
                item["context"] = item.get("context_json") or {}
                results.append(item)
            if not status:
                # roughly order by pending first if not filtered
                results.sort(key=lambda x: (0 if x.get("status") == "pending" else 1, x.get("created_at") or ""), reverse=True)
            return results
        except Exception as e:
            print(f"[MEMORY] DB Error list_permission_requests: {e}")
            return []

    def count_permission_requests(self, status="pending"):
        try:
            res = self._execute(get_supabase().table("permission_requests").select("id").eq("status", status))
            return len(res.data)
        except Exception as e:
            print(f"[MEMORY] DB Error count_permission_requests: {e}")
            return 0

    def get_permission_request(self, request_id):
        try:
            res = self._execute(get_supabase().table("permission_requests").select("*").eq("id", request_id))
            if not res.data: return None
            item = res.data[0]
            item["context"] = item.get("context_json") or {}
            return item
        except Exception as e:
            print(f"[MEMORY] DB Error get_permission_request: {e}")
            return None

    def find_pending_permission_request(self, permission_key, goal_id=None, action_label=None):
        try:
            q = get_supabase().table("permission_requests").select("*").eq("permission_key", permission_key).eq("status", "pending")
            if goal_id: q = q.eq("goal_id", goal_id)
            if action_label: q = q.eq("action_label", action_label)
            res = self._execute(q.order("created_at", desc=True).limit(1))
            if not res.data: return None
            item = res.data[0]
            item["context"] = item.get("context_json") or {}
            return item
        except Exception as e:
            print(f"[MEMORY] DB Error find_pending_permission_request: {e}")
            return None

    def resolve_permission_request(self, request_id, decision, resolution_note=None):
        if decision not in ("approved", "denied"):
            raise ValueError("Invalid permission request decision")
        try:
            self._execute(get_supabase().table("permission_requests").update({
                "status": decision, "resolved_at": datetime.now().isoformat(), "resolution_note": resolution_note
            }).eq("id", request_id))
            return self.get_permission_request(request_id)
        except Exception as e:
            print(f"[MEMORY] DB Error resolve_permission_request: {e}")
            return None

    def create_goal_record(self, goal_data):
        try:
            self._execute(get_supabase().table("goals").insert({
                "id": goal_data['id'], "title": goal_data.get('title'), "objective": goal_data['objective'],
                "status": goal_data['status'], "priority": goal_data.get('priority', 'normal'),
                "created_at": goal_data.get('created_at'), "updated_at": goal_data.get('updated_at'),
                "requires_approval": True if goal_data.get('requires_approval') else False,
                "current_step_index": goal_data.get('current_step_index', 0), "summary": goal_data.get('summary')
            }))
        except Exception as e:
            print(f"[MEMORY] DB Error create_goal_record: {e}")

    def update_goal_record(self, goal_id, updates):
        if 'requires_approval' in updates: updates['requires_approval'] = True if updates['requires_approval'] else False
        updates["updated_at"] = datetime.now().isoformat()
        try:
            self._execute(get_supabase().table("goals").update(updates).eq("id", goal_id))
        except Exception as e:
            print(f"[MEMORY] DB Error update_goal_record: {e}")

    def get_goal_record(self, goal_id):
        try:
            res = self._execute(get_supabase().table("goals").select("*").eq("id", goal_id))
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[MEMORY] DB Error get_goal_record: {e}")
            return None

    def get_all_goals(self):
        try:
            res = self._execute(get_supabase().table("goals").select("*").order("created_at", desc=True))
            return res.data
        except Exception as e:
            print(f"[MEMORY] DB Error get_all_goals: {e}")
            return []

    def create_plan_record(self, plan_data):
        try:
            self._execute(get_supabase().table("goal_plans").insert({
                "id": plan_data['id'], "goal_id": plan_data['goal_id'], "status": plan_data['status'],
                "risk_summary": plan_data.get('risk_summary'), "created_by": plan_data.get('created_by'),
                "created_at": plan_data.get('created_at'), "planner_type": plan_data.get('planner_type'),
                "planner_provider": plan_data.get('planner_provider'), "planner_warnings": plan_data.get('planner_warnings'),
                "raw_plan_hash": plan_data.get('raw_plan_hash')
            }))
        except Exception as e:
            print(f"[MEMORY] DB Error create_plan_record: {e}")

    def update_plan_record(self, plan_id, updates):
        try:
            self._execute(get_supabase().table("goal_plans").update(updates).eq("id", plan_id))
        except Exception as e:
            print(f"[MEMORY] DB Error update_plan_record: {e}")

    def get_plan_record(self, plan_id):
        try:
            res = self._execute(get_supabase().table("goal_plans").select("*").eq("id", plan_id))
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[MEMORY] DB Error get_plan_record: {e}")
            return None
        
    def get_current_plan_for_goal(self, goal_id):
        try:
            res = self._execute(get_supabase().table("goal_plans").select("*").eq("goal_id", goal_id).order("created_at", desc=True).limit(1))
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[MEMORY] DB Error get_current_plan_for_goal: {e}")
            return None

    def create_plan_step_record(self, step_data):
        try:
            self._execute(get_supabase().table("goal_plan_steps").insert({
                "id": step_data['id'], "goal_id": step_data['goal_id'], "plan_id": step_data['plan_id'],
                "step_index": step_data['step_index'], "title": step_data.get('title'),
                "description": step_data.get('description'), "capability_type": step_data.get('capability_type'),
                "status": step_data['status'], "requires_approval": True if step_data.get('requires_approval') else False,
                "action_ref": step_data.get('action_ref'), "result_ref": step_data.get('result_ref'), "error": step_data.get('error')
            }))
        except Exception as e:
            print(f"[MEMORY] DB Error create_plan_step_record: {e}")

    def update_plan_step_record(self, step_id, updates):
        if 'requires_approval' in updates: updates['requires_approval'] = True if updates['requires_approval'] else False
        try:
            self._execute(get_supabase().table("goal_plan_steps").update(updates).eq("id", step_id))
        except Exception as e:
            print(f"[MEMORY] DB Error update_plan_step_record: {e}")
        
    def get_plan_step_record(self, step_id):
        try:
            res = self._execute(get_supabase().table("goal_plan_steps").select("*").eq("id", step_id))
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[MEMORY] DB Error get_plan_step_record: {e}")
            return None

    def get_step_by_action_ref(self, action_ref):
        try:
            res = self._execute(get_supabase().table("goal_plan_steps").select("*").eq("action_ref", action_ref).limit(1))
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[MEMORY] DB Error get_step_by_action_ref: {e}")
            return None

    def log_goal_event(self, goal_id, event_type, from_status=None, to_status=None,
                       reason=None, plan_id=None, step_id=None, action_ref=None, result_ref=None):
        try:
            self._execute(get_supabase().table("goal_events").insert({
                "goal_id": goal_id, "plan_id": plan_id, "step_id": step_id, "event_type": event_type,
                "from_status": from_status, "to_status": to_status, "reason": reason, "action_ref": action_ref,
                "result_ref": result_ref, "created_at": datetime.now().isoformat()
            }))
        except Exception as e:
            print(f"[MEMORY] DB Error log_goal_event: {e}")

    def get_goal_events(self, goal_id, limit=100):
        try:
            res = self._execute(get_supabase().table("goal_events").select("*").eq("goal_id", goal_id).order("created_at", desc=True).limit(limit))
            return res.data
        except Exception as e:
            print(f"[MEMORY] DB Error get_goal_events: {e}")
            return []

    def get_goal_plan_steps(self, goal_id, plan_id=None):
        try:
            q = get_supabase().table("goal_plan_steps").select("*").eq("goal_id", goal_id).order("step_index")
            if plan_id: q = q.eq("plan_id", plan_id)
            res = self._execute(q)
            return res.data
        except Exception as e:
            print(f"[MEMORY] DB Error get_goal_plan_steps: {e}")
            return []

    # ── Token hashing helpers ────────────────────────────────────────────────
    def _make_token_hash(self, token):
        if _BCRYPT_AVAILABLE:
            salt = _bcrypt.gensalt()
            hashed = _bcrypt.hashpw(token.encode(), salt).decode()
            return hashed, salt.decode()
        else:
            salt = secrets.token_hex(16)
            hashed = hashlib.sha256((salt + token).encode()).hexdigest()
            return hashed, salt

    def _verify_token_hash(self, token, stored_hash, stored_salt):
        if stored_hash is None:
            return False
        if stored_hash.startswith(("$2b$", "$2a$", "$2y$")):
            try:
                return _BCRYPT_AVAILABLE and _bcrypt.checkpw(token.encode(), stored_hash.encode())
            except Exception:
                return False
        if stored_salt:
            expected = hashlib.sha256((stored_salt + token).encode()).hexdigest()
            return secrets.compare_digest(expected, stored_hash)
        expected = hashlib.sha256(token.encode()).hexdigest()
        return secrets.compare_digest(expected, stored_hash)

    # ── Device registry ──────────────────────────────────────────────────────
    def register_device(self, name, role):
        device_id = str(uuid.uuid4())
        token = secrets.token_hex(32)
        token_hash, token_salt = self._make_token_hash(token)
        try:
            self._execute(get_supabase().table("devices").insert({
                "device_id" if "device_id" else "id": device_id, # "id" per User schema script
                "id": device_id,
                "name": name, "role": role, "token_hash": token_hash,
                "created_at": datetime.now().isoformat(), "is_active": True, "metadata": {"token_salt": token_salt}
            }))
        except Exception as e:
            print(f"[MEMORY] DB Error register_device: {e}")
        return device_id, token

    def authenticate_device_token(self, token):
        if not token: return None
        try:
            res = self._execute(get_supabase().table("devices").select("*").eq("is_active", True))
            for device in res.data:
                stored_salt = device.get('metadata', {}).get("token_salt") if device.get('metadata') else None
                if self._verify_token_hash(token, device.get('token_hash'), stored_salt):
                    self._execute(get_supabase().table("devices").update({"last_seen": datetime.now().isoformat()}).eq("id", device['id']))
                    return device
            return None
        except Exception as e:
            print(f"[MEMORY] DB Error authenticate_device_token: {e}")
            return None

    def list_devices(self):
        try:
            res = self._execute(get_supabase().table("devices").select("id, name, role, created_at, last_seen, is_active, metadata"))
            return res.data
        except Exception as e:
            print(f"[MEMORY] DB Error list_devices: {e}")
            return []

    def revoke_device(self, device_id):
        try:
            self._execute(get_supabase().table("devices").update({"is_active": False}).eq("id", device_id))
            return True
        except Exception as e:
            print(f"[MEMORY] DB Error revoke_device: {e}")
            return False

    def rotate_device_token(self, device_id):
        new_token = secrets.token_hex(32)
        token_hash, token_salt = self._make_token_hash(new_token)
        try:
            res = self._execute(get_supabase().table("devices").update({"token_hash": token_hash, "metadata": {"token_salt": token_salt}}).eq("id", device_id).eq("is_active", True))
            return new_token if res.data else None
        except Exception as e:
            print(f"[MEMORY] DB Error rotate_device_token: {e}")
            return None

    def create_pairing_code(self, role, device_name):
        import random, string
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        expires_at = (datetime.now() + timedelta(minutes=10)).isoformat()
        try:
            # According to User schema script:
            self._execute(get_supabase().table("pairing_codes").insert({"code": code, "expires_at": expires_at, "used": False}))
        except Exception as e:
            print(f"[MEMORY] DB Error create_pairing_code: {e}")
        return code

    def get_pairing_code(self, code):
        try:
            res = self._execute(get_supabase().table("pairing_codes").select("*").eq("code", code).eq("used", False))
            if res.data:
                record = res.data[0]
                expires_at = datetime.fromisoformat(record['expires_at'].replace("Z", "+00:00"))
                if expires_at.tzinfo:
                    expires_at = expires_at.replace(tzinfo=None) # Strip tz to compare with naive now()
                if expires_at > datetime.now():
                    return record
            return None
        except Exception as e:
            print(f"[MEMORY] DB Error get_pairing_code: {e}")
            return None

    def use_pairing_code(self, code):
        try:
            self._execute(get_supabase().table("pairing_codes").update({"used": True}).eq("code", code))
            return True
        except Exception as e:
            print(f"[MEMORY] DB Error use_pairing_code: {e}")
            return False

    def log_activity(self, actor_type, device_id, endpoint, method, status_code, action_summary=None, error=None, ip=None, agent=None, user_agent=None):
        ua = user_agent or agent
        safe_summary = (action_summary or '')[:256] or None
        safe_error   = (str(error) or '')[:256] or None
        try:
            # Supabase schema has no 'action_summary' or 'error' but has 'metadata', inserting those in activity_log metadata if table doesn't have it, wait.
            # Using basic table from user schema "CREATE TABLE activity_log (id BIGSERIAL, timestamp, endpoint, method, status_code, ip, user_agent, actor_type, device_id)"
            self._execute(get_supabase().table("activity_log").insert({
                "timestamp": datetime.now().isoformat(), "actor_type": actor_type, "device_id": device_id,
                "endpoint": endpoint, "method": method, "status_code": status_code,
                "ip": ip, "user_agent": ua
            }))
        except Exception as e:
            print(f"[MEMORY] DB Error log_activity: {e}")

    def get_recent_activity(self, limit=50, device_id=None):
        limit = max(1, min(200, limit))
        try:
            q = get_supabase().table("activity_log").select("*").order("timestamp", desc=True).limit(limit)
            if device_id: q = q.eq("device_id", device_id)
            res = self._execute(q)
            return res.data
        except Exception as e:
            print(f"[MEMORY] DB Error get_recent_activity: {e}")
            return []

    # ── Phase 7.3 Control Plane Helpers ───────────────────────────────────────
    def get_control_counts(self):
        counts = {
            "goals_total": 0, "goals_active": 0, "goals_awaiting_approval": 0,
            "goals_blocked": 0, "goals_completed": 0, "goals_paused": 0,
            "goals_stopped": 0, "pending_actions": 0, "permission_requests_pending": 0
        }
        try:
            res_goals = self._execute(get_supabase().table("goals").select("status"))
            for r in res_goals.data:
                st = r.get("status")
                counts["goals_total"] += 1
                if st == 'active': counts["goals_active"] += 1
                elif st == 'awaiting_approval': counts["goals_awaiting_approval"] += 1
                elif st == 'blocked': counts["goals_blocked"] += 1
                elif st == 'completed': counts["goals_completed"] += 1
                elif st == 'paused': counts["goals_paused"] += 1
                elif st == 'stopped': counts["goals_stopped"] += 1

            res_pa = self._execute(get_supabase().table("pending_actions").select("id").eq("status", "pending"))
            counts["pending_actions"] = len(res_pa.data)
            counts["permission_requests_pending"] = self.count_permission_requests(status='pending')
        except Exception as e:
            print(f"[MEMORY] DB Error get_control_counts: {e}")
        return counts

    def get_pending_approvals_with_linkage(self, limit=50, status='actionable', goal_id=None, action_type=None, action_id=None):
        try:
            # We must join pending_actions with goal_plan_steps, goal_plans, and goals.
            # In Supabase client, JOINs are done via embedded resource querying if foreign keys exist.
            # If not, we fetch actions, then fetch related.
            q = get_supabase().table("pending_actions").select("*").order("created_at", desc=True).limit(limit)
            if status == 'actionable': q = q.in_("status", ["pending", "approved"])
            elif status and status != 'all': q = q.eq("status", status)
            if action_type: q = q.eq("type", action_type)
            if action_id: q = q.eq("id", action_id)
            res = self._execute(q)

            # We fetch all goals manually for simplified mock join. This is a hacky workaround due to no raw SQL in Supabase REST.
            actions = res.data
            steps_res = self._execute(get_supabase().table("goal_plan_steps").select("*"))
            plans_res = self._execute(get_supabase().table("goal_plans").select("*"))
            goals_res = self._execute(get_supabase().table("goals").select("*"))
            
            steps = {s["id"]: s for s in steps_res.data}
            steps_by_ref = {s["action_ref"]: s for s in steps_res.data if s.get("action_ref")}
            for s in steps_res.data:
                if s.get("result_ref"): steps_by_ref[s["result_ref"]] = s
            plans = {p["id"]: p for p in plans_res.data}
            goals = {g["id"]: g for g in goals_res.data}

            results = []
            for row in actions:
                s = steps_by_ref.get(row["id"], {})
                p = plans.get(s.get("plan_id"), {})
                g = goals.get(p.get("goal_id", row.get("goal_id")), {})

                if goal_id and g.get("id") != goal_id: continue

                action_details = row.get('payload') or {}
                results.append({
                    "action_id": row['id'], "action_type": row['type'], "action_status": row['status'],
                    "goal_id": g.get("id"), "plan_id": p.get("id"), "step_id": s.get("id"),
                    "goal_title": g.get("title"), "preview": s.get('title') or f"Action {row['type']}",
                    "created_at": row.get('created_at'), "approved_at": row.get('updated_at'), 
                    "executed_at": row.get('updated_at'), "created_by": row.get('device_id'),
                    "notes": row.get('type'), "result_ref": None, "step_title": s.get("title"),
                    "last_transition_at": row.get('updated_at') or row.get('created_at'),
                    "action_details": action_details
                })
            return results
        except Exception as e:
            print(f"[MEMORY] DB Error get_pending_approvals_with_linkage: {e}")
            return []

    def get_blocked_items(self, limit=50):
        try:
            g_res = self._execute(get_supabase().table("goals").select("*").eq("status", "blocked").order("updated_at", desc=True).limit(limit))
            items = []
            for r in g_res.data:
                items.append({
                    "item_type": "goal", "goal_id": r['id'], "step_id": None, "action_id": None,
                    "goal_title": r['title'], "status": "blocked", "blocked_reason": "Unknown reason",
                    "last_transition_at": r.get('updated_at'), "recommended_resolution": "Review and resume or cancel goal"
                })
                
            s_res = self._execute(get_supabase().table("goal_plan_steps").select("*").in_("status", ["blocked", "failed"]).limit(limit))
            for r in s_res.data:
                items.append({
                    "item_type": "step", "goal_id": r["goal_id"], "step_id": r["id"], "action_id": None,
                    "goal_title": "Goal", "step_title": r.get("title"), "status": "blocked",
                    "blocked_reason": r.get("error") or "Unknown error",
                    "last_transition_at": r.get("updated_at") or "",
                    "recommended_resolution": "Inspect the step dependency"
                })
            items.sort(key=lambda row: row.get("last_transition_at") or "", reverse=True)
            return items[:limit]
        except Exception as e:
            print(f"[MEMORY] DB Error get_blocked_items: {e}")
            return []

    def get_recent_results(self, limit=50):
        try:
            return [] # Mock for now
        except Exception:
            return []

    def count_recent_results(self):
        return 0
