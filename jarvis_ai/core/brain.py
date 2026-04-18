"""
Core reasoning engine and LLM interface (The Brain).
Handles communication with the Language Model and basic context management.
"""

from jarvis_ai.memory.short_term import ShortTermMemory
from jarvis_ai.memory.long_term import LongTermMemory
from jarvis_ai.core.goal_engine import GoalEngine
from jarvis_ai.agents.planner import PlannerAgent
from jarvis_ai.core.autonomy import AutonomyManager
from jarvis_ai.tools.system_tool import SystemTool
from jarvis_ai.tools.web_tool import WebTool
from jarvis_ai.tools.mobile_tool import MobileTool
from jarvis_ai.core.logger import Logger
from jarvis_ai.integrations.voice_interface import VoiceInterface
from jarvis_ai.core.api_integration import APIIntegration
from jarvis_ai.core.notifications import NotificationManager
from jarvis_ai.integrations.calendar_integration import CalendarIntegration
from jarvis_ai.core.scheduler import GoalScheduler
from jarvis_ai.core.strategic_engine import StrategicEngine
from jarvis_ai.core.governance_engine import GovernanceEngine
from jarvis_ai.memory.memory_engine import MemoryEngine
from jarvis_ai.core.llm_advisory import LLMAdvisory
from jarvis_ai.core.version import APP_VERSION
from jarvis_ai.core.permissions import PermissionService
from jarvis_ai.integrations.web_automation import WebAutomationEngine
import uuid
import json
import re
from datetime import datetime

GOOGLE_AVAILABLE = False
try:
    from jarvis_ai.integrations.google.auth import HAS_LIBS as GOOGLE_LIBS_INSTALLED
    if GOOGLE_LIBS_INSTALLED:
        from jarvis_ai.integrations.google.auth import GoogleAuth
        from jarvis_ai.integrations.google.gmail_client import GmailClient
        from jarvis_ai.integrations.google.calendar_client import CalendarClient
        GOOGLE_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    GOOGLE_AVAILABLE = False
from jarvis_ai.core.conversation.session_manager import SessionManager

class Brain:
    def __init__(self, config, llm_advisory_mode=False):
        """
        Initialize the Brain with configuration and memory.
        """
        self.version = APP_VERSION
        self.config = config
        self.llm_provider = config.get('llm', {}).get('provider', 'groq')
        self.llm_advisory_mode = llm_advisory_mode
        self.logger = Logger()
        self.memory = ShortTermMemory()
        self.long_term_memory = LongTermMemory()
        
        # Unified Memory Engine for DB and Locking
        db_path = config.get('memory', {}).get('db_path', None)
        self.memory_engine = MemoryEngine(db_path)
        
        # Initialize Conversational Session Manager
        self.sessions = SessionManager(self)
        
        # Initialize Scheduler with shared memory engine
        self.scheduler = GoalScheduler(logger=self.logger, db_path=db_path)
        self.scheduler.memory_engine = self.memory_engine
        
        # Initialize Notifications first
        self.notifications = NotificationManager(logger=self.logger)
        self.notifications.start()
        
        # Initialize GoalEngine
        self.goal_engine = GoalEngine(memory_engine=self.memory_engine, notification_callback=self._on_goal_event)
        
        self.planner = PlannerAgent(self)
        self.autonomy = AutonomyManager(self)
        self.strategic = StrategicEngine(self)
        self.governance = GovernanceEngine(self)
        self.advisory = LLMAdvisory(self)
        self.permissions = PermissionService(self.config, self.memory_engine)
        
        # Link governance back to scheduler for score modification
        self.scheduler.governance = self.governance

        # Activating LLM Advisory Mode if requested
        if self.llm_advisory_mode:
            self.memory_engine.set_setting('enable_llm_advisory', 'True')
            self.logger.log("[BRAIN] LLM Advisory Mode activated directly via constructor.", "INFO")
        
        # Initialize Tools
        self.system_tool = SystemTool()
        self.web_tool = WebTool()
        self.mobile_tool = MobileTool()
        
        # Initialize Voice and API modules
        self.voice = VoiceInterface(self.config)
        self.api = APIIntegration(logger=self.logger)
        
        # Initialize Productivity Integrations
        self.web_automation = WebAutomationEngine(self.config)
        self.google_degraded_reason = None
        
        google_config = config.get('google', {})
        if GOOGLE_AVAILABLE and google_config.get('enabled', True):
            try:
                from jarvis_ai.integrations.google.inbox_insight import InboxInsight
                self.google_auth = GoogleAuth(config)
                # Attempt to get credentials which might trigger refresh/flow
                # We wrap clients too as their constructors might build services
                self.gmail = GmailClient(self.google_auth)
                self.calendar = CalendarClient(self.google_auth)
                self.inbox_insight = InboxInsight(self)
                self.logger.log("[BRAIN] Google integrations initialized successfully.", "INFO")
            except Exception as e:
                self.google_degraded_reason = str(e)
                self.google_auth = self.gmail = self.calendar = self.inbox_insight = None
                self.logger.log(f"[BRAIN] Google integration DEGRADED: {e}", "WARNING")
        else:
            self.google_auth = self.gmail = self.calendar = self.inbox_insight = None
            if not GOOGLE_AVAILABLE:
                self.google_degraded_reason = "dependencies_missing"
                self.logger.log("[BRAIN] Google dependencies missing. Integrations disabled.", "WARNING")
            else:
                self.google_degraded_reason = "disabled_by_config"
                self.logger.log("[BRAIN] Google integration disabled via config.", "INFO")
        
        self.logger.log(f"Brain initialized with provider: {self.llm_provider}")

    def close(self):
        """Best-effort shutdown for test cleanup and local runtimes."""
        try:
            if getattr(self, "notifications", None):
                self.notifications.stop()
        finally:
            if getattr(self, "memory_engine", None):
                self.memory_engine.close()

    def chat(self, conversation_id, user_message, dashboard_context=None):
        """
        Core conversational entry point.
        """
        result = self.chat_with_metadata(
            conversation_id,
            user_message,
            dashboard_context=dashboard_context,
        )
        return result.get("reply", "")

    def chat_with_metadata(self, conversation_id, user_message, dashboard_context=None):
        """
        Conversational entry point with routing metadata for dashboard clients.
        """
        self.logger.log(f"[CHAT] Received message for session {conversation_id}", "INFO")
        
        # 1. Update session with user message
        self.sessions.add_message(conversation_id, "user", user_message)
        
        # 1.1 Handle Explicit Memory Policy (Task 1)
        # Scan for triggers: "remember this:" or "save this memory:"
        triggers = ["remember this:", "save this memory:"]
        policy = self.memory_engine.get_setting('memory_write_policy', 'explicit')
        
        trigger_found = False
        message_to_remember = None
        lower_message = user_message.lower()
        for t in triggers:
            idx = lower_message.find(t.lower())
            if idx != -1:
                trigger_found = True
                # Extract content after trigger
                content_after = user_message[idx + len(t):].strip()
                if content_after:
                    message_to_remember = content_after
                break
        
        if trigger_found or policy == "auto":
            text_to_save = message_to_remember or user_message
            self.logger.log(f"[MEMORY] Saving long-term memory (Policy: {policy}, Trigger: {trigger_found})", "INFO")
            self.memory_engine.save_long_term_memory(text_to_save, tags="manual" if trigger_found else "auto")

        routed = self._route_grounded_dashboard_command(
            conversation_id,
            user_message,
            trigger_found=trigger_found,
            message_to_remember=message_to_remember,
            dashboard_context=dashboard_context,
        )

        try:
            if routed is None:
                # 2. Build context only when we need the advisory/provider path.
                context = self.sessions.get_full_context(conversation_id, user_message)
                
                conversation_messages = []
                for m in context:
                    conversation_messages.append({"role": m["role"], "content": m["content"]})
                    
                system_prompt = f"dashboard_context:\n{self._build_dashboard_context_prompt(dashboard_context)}\nsystem_state:\n{self._build_live_state_prompt()}"
                
                from jarvis_ai.llm.router import chat as llm_chat
                llm_result = llm_chat(
                    messages=conversation_messages,
                    model_id=None,  
                    system=system_prompt,
                    fallback=True
                )
                response_text = llm_result["response"]

                if "GOAL:" in response_text:
                    self.logger.log("[CHAT] LLM suggested a goal. routing to governance...", "WARNING")
                    suggested_goal = response_text.split("GOAL:")[1].strip()
                    is_allowed, reason = self.governance.validate_llm_proposal({"type": "goal", "content": suggested_goal})
                    if not is_allowed:
                        response_text += f"\n\n[SYSTEM NOTE: The suggested goal '{suggested_goal}' was blocked by Governance: {reason}]"

                if self._response_needs_grounded_fallback(response_text):
                    routed = self._build_grounded_fallback_response(user_message)
                else:
                    routed = self._make_chat_result(
                        reply=response_text,
                        intent="general_chat",
                        source="llm_advisory",
                        source_label="LLM advisory with live state prompt",
                        context={"provider": llm_result["provider"], "model_id": llm_result["model_id"]},
                        grounded=False
                    )

            routed = self._attach_chat_actions(routed, dashboard_context=dashboard_context)
            response_text = routed["reply"]
            self.sessions.add_message(
                conversation_id,
                "assistant",
                response_text,
                actions=routed.get("actions"),
                routing=routed.get("routing"),
            )
            return routed
        except Exception as e:
            self.logger.log(f"[CHAT] Error in chat loop: {e}", "ERROR")
            fallback = self._make_chat_result(
                reply="I hit an error while routing that request. The safest next step is to inspect the live dashboard state directly or ask for a system status summary.",
                intent="error_fallback",
                source="chat_error",
                source_label="Safe error fallback",
                context={"error": str(e)}
            )
            fallback = self._attach_chat_actions(fallback, dashboard_context=dashboard_context)
            self.sessions.add_message(
                conversation_id,
                "assistant",
                fallback["reply"],
                actions=fallback.get("actions"),
                routing=fallback.get("routing"),
            )
            return fallback

    def _make_chat_result(self, reply, intent, source, source_label, context=None, grounded=True):
        return {
            "reply": reply,
            "routing": {
                "intent": intent,
                "source": source,
                "source_label": source_label,
                "grounded": grounded,
                "context": context or {}
            }
        }

    def _goal_exists(self, goal_id):
        if not goal_id:
            return False
        try:
            from jarvis_ai.db.supabase_client import get_supabase
            res = get_supabase().table("goals").select("id").eq("id", goal_id).limit(1).execute()
            return bool(res.data)
        except Exception:
            return False

    def _approval_exists(self, approval_id):
        if not approval_id:
            return False
        try:
            from jarvis_ai.db.supabase_client import get_supabase
            res = get_supabase().table("pending_actions").select("id").eq("id", approval_id).limit(1).execute()
            return bool(res.data)
        except Exception:
            return False

    def _permission_exists(self, permission_key):
        if not permission_key:
            return False
        return self.permissions.get_permission(permission_key, runtime=self.get_permission_runtime()) is not None

    def _normalize_chat_actions(self, actions):
        normalized = []
        seen = set()

        for action in actions or []:
            if not isinstance(action, dict):
                continue

            label = str(action.get("label") or "").strip()
            target = str(action.get("target") or "").strip()
            if not label or not target:
                continue

            item = {
                "label": label,
                "target": target,
            }

            goal_id = action.get("goal_id")
            if goal_id and self._goal_exists(goal_id):
                item["goal_id"] = goal_id

            approval_id = action.get("approval_id")
            if approval_id and self._approval_exists(approval_id):
                item["approval_id"] = approval_id

            filter_hint = str(action.get("filter") or "").strip().lower()
            if filter_hint:
                item["filter"] = filter_hint

            section_hint = str(action.get("section") or "").strip().lower()
            if section_hint:
                item["section"] = section_hint

            highlight = action.get("highlight")
            if target == "goals":
                highlight_goal = highlight or item.get("goal_id")
                if highlight_goal and self._goal_exists(highlight_goal):
                    item["highlight"] = highlight_goal
            elif target == "approvals":
                highlight_approval = highlight or item.get("approval_id")
                if highlight_approval and self._approval_exists(highlight_approval):
                    item["highlight"] = highlight_approval
            elif target == "permissions":
                if highlight and self._permission_exists(highlight):
                    item["highlight"] = highlight
            elif highlight:
                item["highlight"] = str(highlight)

            dedupe_key = (
                item["label"],
                item["target"],
                item.get("goal_id"),
                item.get("approval_id"),
                item.get("filter"),
                item.get("section"),
                item.get("highlight"),
            )
            if dedupe_key in seen:
                continue

            seen.add(dedupe_key)
            normalized.append(item)
            if len(normalized) >= 3:
                break

        return normalized

    def _append_chat_action(
        self,
        actions,
        label,
        target,
        goal_id=None,
        approval_id=None,
        filter=None,
        section=None,
        highlight=None,
    ):
        if len(actions) >= 3:
            return
        action = {"label": label, "target": target}
        if goal_id:
            action["goal_id"] = goal_id
        if approval_id:
            action["approval_id"] = approval_id
        if filter:
            action["filter"] = filter
        if section:
            action["section"] = section
        if highlight:
            action["highlight"] = highlight
        actions.append(action)

    def _build_chat_actions(self, intent, context=None, dashboard_context=None):
        intent = str(intent or "")
        context = context if isinstance(context, dict) else {}
        dashboard = self._coerce_dashboard_context(dashboard_context)
        actions = []

        if intent in (
            "permission_blocked_goal_creation",
            "permission_blocked_approvals",
            "permission_blocked_recommendations",
            "permission_blocked_status",
            "permission_blocked_recent_changes",
            "permission_blocked_results",
            "permission_blocked_goals_view",
            "disabled_permissions_summary",
            "access_overview",
        ):
            permission_key = context.get("permission_key")
            self._append_chat_action(
                actions,
                "Open Permissions & Access",
                "permissions",
                filter="disabled" if intent == "disabled_permissions_summary" else None,
                highlight=permission_key,
            )

        elif intent == "goal_block_reason":
            blocked_item = context.get("blocked_item") or {}
            goal_id = blocked_item.get("goal_id")
            if goal_id:
                self._append_chat_action(
                    actions,
                    "View Blocked Goal",
                    "goals",
                    goal_id=goal_id,
                    filter="blocked",
                    highlight=goal_id,
                )
            else:
                self._append_chat_action(actions, "Review Blocked Goals", "goals", filter="blocked")

            related_permissions = context.get("related_permissions") or []
            if related_permissions:
                primary_permission = related_permissions[0] if isinstance(related_permissions[0], dict) else {}
                self._append_chat_action(
                    actions,
                    "Open Permissions & Access",
                    "permissions",
                    filter="disabled",
                    highlight=primary_permission.get("key"),
                )

            goal_summary = context.get("goal_summary") or {}
            waiting_approvals = goal_summary.get("waiting_approvals") or []
            if waiting_approvals:
                first_approval = waiting_approvals[0] if isinstance(waiting_approvals[0], dict) else {}
                self._append_chat_action(
                    actions,
                    "Review Approval" if first_approval.get("action_id") else "See Pending Approvals",
                    "approvals",
                    approval_id=first_approval.get("action_id"),
                    filter="pending",
                    highlight=first_approval.get("action_id"),
                )

        elif intent == "blocked_goals_summary":
            items = context.get("items") or []
            first_goal_id = items[0].get("goal_id") if items else None
            if context.get("blocked_count") == 1 and first_goal_id:
                self._append_chat_action(
                    actions,
                    "View Blocked Goal",
                    "goals",
                    goal_id=first_goal_id,
                    filter="blocked",
                    highlight=first_goal_id,
                )
            else:
                self._append_chat_action(actions, "Review Blocked Goals", "goals", filter="blocked")

        elif intent == "pending_approvals_summary":
            items = context.get("items") or []
            first_approval_id = items[0].get("action_id") if items else None
            if context.get("approvals_count") == 1 and first_approval_id:
                self._append_chat_action(
                    actions,
                    "Review Approval",
                    "approvals",
                    approval_id=first_approval_id,
                    filter="pending",
                    highlight=first_approval_id,
                )
            else:
                self._append_chat_action(actions, "See Pending Approvals", "approvals", filter="pending")

        elif intent == "create_goal":
            self._append_chat_action(
                actions,
                "Open Goal" if context.get("goal_id") else "Open Goals",
                "goals",
                goal_id=context.get("goal_id"),
                highlight=context.get("goal_id"),
            )

        elif intent in ("goals_overview",):
            self._append_chat_action(actions, "Open Goals", "goals")

        elif intent == "recommended_next_actions":
            recommendations = context.get("recommendations") or []
            top = recommendations[0] if recommendations else {}
            if top.get("goal_id"):
                self._append_chat_action(
                    actions,
                    "Open Goals",
                    "goals",
                    goal_id=top.get("goal_id"),
                    highlight=top.get("goal_id"),
                )
            else:
                self._append_chat_action(actions, "Open Goals", "goals")

        elif intent == "current_capabilities":
            page_id = context.get("page_id")
            section_hint = "capability-guide"
            if page_id == "guide":
                section_hint = "capability-guide"
            self._append_chat_action(
                actions,
                "View Capabilities & Guide",
                "capabilities",
                section=section_hint,
            )

        elif intent == "page_walkthrough":
            page_id = dashboard.get("page_id") or context.get("page_id")
            focus_goal = dashboard.get("focus_goal") or {}
            if page_id == "settings":
                self._append_chat_action(actions, "Open Settings", "settings")
            elif page_id == "permissions":
                self._append_chat_action(actions, "Open Permissions & Access", "permissions")
            elif page_id == "guide":
                self._append_chat_action(
                    actions,
                    "View Capabilities & Guide",
                    "capabilities",
                    section="capability-guide",
                )
            elif page_id == "goals":
                self._append_chat_action(
                    actions,
                    "Open Goal" if focus_goal.get("goal_id") else "Open Goals",
                    "goals",
                    goal_id=focus_goal.get("goal_id"),
                    highlight=focus_goal.get("goal_id"),
                )

        elif intent in ("system_status_summary", "today_summary", "grounded_fallback"):
            if context.get("blocked_count"):
                self._append_chat_action(actions, "Review Blocked Goals", "goals", filter="blocked")
            if context.get("approvals_count"):
                self._append_chat_action(actions, "See Pending Approvals", "approvals", filter="pending")
            if context.get("disabled_permissions_count") or context.get("pending_permission_requests"):
                self._append_chat_action(actions, "Open Permissions & Access", "permissions", filter="disabled")

        actions = self._normalize_chat_actions(actions)
        return actions

    def _attach_chat_actions(self, result, dashboard_context=None):
        if not isinstance(result, dict):
            return result

        existing_actions = result.get("actions")
        if isinstance(existing_actions, list):
            result["actions"] = self._normalize_chat_actions(existing_actions)
            return result

        routing = result.get("routing") or {}
        intent = routing.get("intent")
        context = routing.get("context") or {}
        result["actions"] = self._build_chat_actions(
            intent,
            context=context,
            dashboard_context=dashboard_context,
        )
        return result

    def _truncate_dashboard_context_value(self, value, limit=240):
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        return f"{text[: max(0, limit - 3)].rstrip()}..."

    def _coerce_dashboard_context(self, dashboard_context):
        if not isinstance(dashboard_context, dict):
            return {}

        system_state = dashboard_context.get("system_state")
        if not isinstance(system_state, dict):
            system_state = {}

        focus_goal = dashboard_context.get("focus_goal")
        if not isinstance(focus_goal, dict):
            focus_goal = {}

        page_sections = dashboard_context.get("page_sections")
        if not isinstance(page_sections, list):
            page_sections = []

        return {
            "page_id": self._truncate_dashboard_context_value(
                dashboard_context.get("page_id") or dashboard_context.get("page") or "",
                limit=60,
            ).lower(),
            "page_title": self._truncate_dashboard_context_value(
                dashboard_context.get("page_title") or dashboard_context.get("page_name") or "",
                limit=80,
            ),
            "page_purpose": self._truncate_dashboard_context_value(
                dashboard_context.get("page_purpose") or dashboard_context.get("page_description") or "",
                limit=240,
            ),
            "page_sections": [
                self._truncate_dashboard_context_value(item, limit=60)
                for item in page_sections[:6]
                if item
            ],
            "system_state": {
                "active_goals_count": system_state.get("active_goals_count"),
                "blocked_items_count": system_state.get("blocked_items_count"),
                "blocked_goals_count": system_state.get("blocked_goals_count"),
                "pending_approvals_count": system_state.get("pending_approvals_count"),
                "pending_permission_requests": system_state.get("pending_permission_requests"),
                "disabled_permissions_count": system_state.get("disabled_permissions_count"),
                "health_status": self._truncate_dashboard_context_value(system_state.get("health_status"), limit=60),
                "model": self._truncate_dashboard_context_value(system_state.get("model"), limit=60),
                "google_status": self._truncate_dashboard_context_value(system_state.get("google_status"), limit=80),
                "voice_status": self._truncate_dashboard_context_value(system_state.get("voice_status"), limit=80),
                "recommended_next_action": self._truncate_dashboard_context_value(system_state.get("recommended_next_action"), limit=200),
            },
            "focus_goal": {
                "goal_id": self._truncate_dashboard_context_value(focus_goal.get("goal_id"), limit=80),
                "title": self._truncate_dashboard_context_value(focus_goal.get("title"), limit=120),
                "status": self._truncate_dashboard_context_value(focus_goal.get("status"), limit=40),
                "blocked_reason": self._truncate_dashboard_context_value(focus_goal.get("blocked_reason"), limit=240),
                "next_step_guidance": self._truncate_dashboard_context_value(focus_goal.get("next_step_guidance"), limit=240),
                "waiting_approvals_count": focus_goal.get("waiting_approvals_count"),
            },
        }

    def _build_dashboard_context_prompt(self, dashboard_context):
        context = self._coerce_dashboard_context(dashboard_context)
        if not context:
            return "page_id=unknown"

        lines = [
            f"page_id={context.get('page_id') or 'unknown'}",
            f"page_title={context.get('page_title') or 'Unknown page'}",
        ]
        if context.get("page_purpose"):
            lines.append(f"page_purpose={context['page_purpose']}")
        if context.get("page_sections"):
            lines.append(f"page_sections={', '.join(context['page_sections'])}")

        system_state = context.get("system_state") or {}
        for key in (
            "health_status",
            "model",
            "active_goals_count",
            "blocked_items_count",
            "blocked_goals_count",
            "pending_approvals_count",
            "pending_permission_requests",
            "disabled_permissions_count",
            "google_status",
            "voice_status",
            "recommended_next_action",
        ):
            value = system_state.get(key)
            if value not in (None, "", []):
                lines.append(f"{key}={value}")

        focus_goal = context.get("focus_goal") or {}
        if focus_goal.get("goal_id") or focus_goal.get("title"):
            lines.append("focus_goal=present")
            for key in ("goal_id", "title", "status", "blocked_reason", "next_step_guidance", "waiting_approvals_count"):
                value = focus_goal.get(key)
                if value not in (None, "", []):
                    lines.append(f"focus_goal_{key}={value}")

        return "\n".join(lines)

    def _route_grounded_dashboard_command(
        self,
        conversation_id,
        user_message,
        trigger_found=False,
        message_to_remember=None,
        dashboard_context=None,
    ):
        text = (user_message or "").strip()
        lowered = re.sub(r"\s+", " ", text.lower())
        runtime = self.get_permission_runtime()
        context = self._coerce_dashboard_context(dashboard_context)

        if any(phrase in lowered for phrase in (
            "walk me through this page",
            "walk through this page",
            "walk me through the page",
            "explain this page",
            "what am i looking at",
            "guide me through this page",
        )):
            return self._handle_page_walkthrough_command(context)

        if any(phrase in lowered for phrase in (
            "what can axis do right now",
            "what can axis do now",
            "what can you do right now",
            "what can you do now",
            "what can axis do on this page",
            "what can you do on this page",
        )):
            return self._handle_current_capabilities_command(context)

        if any(phrase in lowered for phrase in (
            "summarize what happened today",
            "summarise what happened today",
            "what happened today",
            "today summary",
            "today's summary",
        )):
            return self._handle_today_summary_command()

        if any(phrase in lowered for phrase in (
            "what permissions are disabled",
            "show disabled permissions",
            "which permissions are disabled",
            "disabled permissions",
        )):
            return self._handle_disabled_permissions_command()

        if any(phrase in lowered for phrase in (
            "what can jarvis currently access",
            "what can jarvis access",
            "what can axis currently access",
            "what can axis access",
            "what can you access",
            "current access",
        )):
            return self._handle_access_overview_command()

        if any(phrase in lowered for phrase in (
            "what plan am i on",
            "show my profile",
            "show my plan",
            "profiles and plans",
        )):
            return self._handle_profile_plan_command()

        if any(phrase in lowered for phrase in (
            "show axis hub",
            "what skills do you have",
            "what skills are active",
            "show skill registry",
        )):
            return self._handle_skill_registry_command()

        if "why is this goal blocked" in lowered or ("why" in lowered and "goal" in lowered and "blocked" in lowered):
            return self._handle_goal_block_reason_command(lowered, dashboard_context=context)

        goal_objective = self._extract_goal_creation_request(text)
        if goal_objective:
            if not self.permissions.is_allowed("goals.manage", runtime=runtime):
                return self._permission_block_result(
                    "goals.manage",
                    "Goal creation depends on goal management being enabled.",
                    intent="permission_blocked_goal_creation",
                    source="goal_queue",
                    source_label="Goal queue permissions",
                    action_label="Create a goal",
                )
            return self._handle_goal_creation_command(goal_objective)

        if "approval" in lowered or "approvals" in lowered or "waiting for approval" in lowered:
            if not self.permissions.is_allowed("approvals.manage", runtime=runtime):
                return self._permission_block_result(
                    "approvals.manage",
                    "Approval summaries depend on approvals management being enabled.",
                    intent="permission_blocked_approvals",
                    source="control_approvals",
                    source_label="Approval permissions",
                    action_label="Summarize pending approvals",
                )
            return self._handle_pending_approvals_command()

        if "blocked" in lowered:
            return self._handle_blocked_goals_command()

        if any(phrase in lowered for phrase in (
            "what should i do next",
            "what do i do next",
            "recommended next action",
            "recommended action",
            "next action",
            "next step"
        )):
            if not self.permissions.is_allowed("dashboard.access", runtime=runtime):
                return self._permission_block_result(
                    "dashboard.access",
                    "Live recommendations depend on dashboard access being enabled.",
                    intent="permission_blocked_recommendations",
                    source="control_summary",
                    source_label="Dashboard permissions",
                    action_label="Summarize next actions",
                )
            return self._handle_recommended_next_action_command()

        if any(phrase in lowered for phrase in (
            "system status",
            "status summary",
            "summarize my system status",
            "summarise my system status",
            "how is the system",
            "summarize status",
            "summarise status"
        )):
            if not self.permissions.is_allowed("dashboard.access", runtime=runtime):
                return self._permission_block_result(
                    "dashboard.access",
                    "System status summaries depend on dashboard access being enabled.",
                    intent="permission_blocked_status",
                    source="control_summary_readiness",
                    source_label="Dashboard permissions",
                    action_label="Summarize system status",
                )
            return self._handle_system_status_command()

        if any(phrase in lowered for phrase in (
            "what changed recently",
            "what changed",
            "recent changes",
            "recent activity",
            "latest activity"
        )):
            if not self.permissions.is_allowed("goals.view", runtime=runtime):
                return self._permission_block_result(
                    "goals.view",
                    "Recent change summaries depend on goal visibility being enabled.",
                    intent="permission_blocked_recent_changes",
                    source="goal_events",
                    source_label="Goal visibility permissions",
                    action_label="Show recent changes",
                )
            return self._handle_recent_changes_command()

        if any(phrase in lowered for phrase in (
            "recent results",
            "show results",
            "show my results",
            "summarize results",
            "summarise results"
        )):
            if not self.permissions.is_allowed("dashboard.access", runtime=runtime):
                return self._permission_block_result(
                    "dashboard.access",
                    "Result summaries depend on dashboard access being enabled.",
                    intent="permission_blocked_results",
                    source="control_results",
                    source_label="Dashboard permissions",
                    action_label="Summarize recent results",
                )
            return self._handle_recent_results_command()

        if any(phrase in lowered for phrase in (
            "show my goals",
            "list my goals",
            "summarize my goals",
            "summarise my goals",
            "show goals"
        )):
            if not self.permissions.is_allowed("goals.view", runtime=runtime):
                return self._permission_block_result(
                    "goals.view",
                    "Goal overview commands depend on goal visibility being enabled.",
                    intent="permission_blocked_goals_view",
                    source="goal_queue",
                    source_label="Goal visibility permissions",
                    action_label="Show goals",
                )
            return self._handle_goals_overview_command()

        if trigger_found and message_to_remember:
            return self._make_chat_result(
                reply=f"I saved that to long-term memory: '{message_to_remember}'.",
                intent="memory_save_ack",
                source="long_term_memory",
                source_label="Long-term memory",
                context={"saved_text": message_to_remember}
            )

        return None

    def _handle_page_walkthrough_command(self, dashboard_context):
        context = self._coerce_dashboard_context(dashboard_context)
        page_id = context.get("page_id") or "dashboard"
        page_title = context.get("page_title") or page_id.replace("-", " ").title()
        page_purpose = context.get("page_purpose")
        page_sections = context.get("page_sections") or []
        system_state = context.get("system_state") or {}
        focus_goal = context.get("focus_goal") or {}

        page_guidance = {
            "overview": (
                "This is the command deck for live system health, active work, approvals, blockers, and recommended next moves.",
                "Use this page when you want the fastest read on where Axis needs owner attention."
            ),
            "goals": (
                "This page is for creating goals, scanning the queue, and controlling a selected goal without leaving the governed execution flow.",
                "Start with the queue, then inspect the focused goal for steps, blockers, approvals, and recent movement."
            ),
            "approvals": (
                "This page is the owner review queue for sensitive work before execution.",
                "Use it to approve, reject, or execute actions while keeping the existing trust model intact."
            ),
            "axis-hub": (
                "This page shows the ecosystem view: skill surfaces, growth lanes, and what parts of Axis are live versus still forming.",
                "Use it to understand capability maturity and where the product is heading without overstating readiness."
            ),
            "guide": (
                "This page explains what is live, partial, degraded, mocked, or still planned.",
                "Use it when you want an honest walkthrough of the current system instead of marketing language."
            ),
            "permissions": (
                "This page is the trust console for permission state, pending requests, and desktop-owner controls.",
                "Use it to unblock capability gates or confirm why Axis is intentionally constrained."
            ),
            "security": (
                "This page summarizes the current security posture, audit visibility, and trust boundaries.",
                "Use it to review how the system is protected today and where compliance claims intentionally stop."
            ),
            "settings": (
                "This page holds safe, owner-facing workspace controls rather than deep backend configuration.",
                "Use it to adjust the live foundation settings that shape the shell, voice behavior, and approval posture."
            ),
            "profiles": (
                "This page explains the current workspace profile, plan posture, and future-fit guidance.",
                "Use it to align Axis to the owner context without pretending billing or enterprise features are already live."
            ),
        }

        intro, next_step = page_guidance.get(
            page_id,
            (
                "This page is part of the Axis dashboard and is meant to surface only the context needed for that workflow.",
                "Use the page title and visible cards as the quickest map for what to do next."
            ),
        )

        lines = [f"You're on {page_title}. {intro}"]
        if page_purpose:
            lines.append(page_purpose)
        lines.append(next_step)

        if system_state:
            lines.append(
                "Right now I can see "
                f"{system_state.get('active_goals_count') or 0} active goal(s), "
                f"{system_state.get('pending_approvals_count') or 0} approval item(s), "
                f"{system_state.get('blocked_items_count') or system_state.get('blocked_goals_count') or 0} blocked item(s), "
                f"and {system_state.get('disabled_permissions_count') or 0} disabled permission(s)."
            )
        if page_sections:
            lines.append(f"I would start with: {', '.join(page_sections[:3])}.")
        if focus_goal.get("goal_id") or focus_goal.get("title"):
            goal_label = self._short_goal_label(focus_goal.get("title"), focus_goal.get("goal_id"))
            goal_status = focus_goal.get("status") or "unknown"
            lines.append(f"The current focus goal is {goal_label} and it is {goal_status}.")
            if focus_goal.get("blocked_reason"):
                lines.append(f"Current friction: {focus_goal['blocked_reason']}")
            elif focus_goal.get("next_step_guidance"):
                lines.append(f"Next move on that goal: {focus_goal['next_step_guidance']}")

        return self._make_chat_result(
            reply="\n".join(lines),
            intent="page_walkthrough",
            source="dashboard_context",
            source_label="Dashboard page context",
            context=context,
        )

    def _handle_current_capabilities_command(self, dashboard_context):
        context = self._coerce_dashboard_context(dashboard_context)
        page_id = context.get("page_id") or "overview"
        page_title = context.get("page_title") or page_id.replace("-", " ").title()
        permissions_snapshot = self.get_permissions_snapshot()
        runtime = self.get_permission_runtime()

        active = [item for item in permissions_snapshot["permissions"] if item["effective_status"] == "active"]
        limited = [
            item for item in permissions_snapshot["permissions"]
            if item["effective_status"] in ("limited", "planned", "unavailable")
        ]
        important_live = [item["name"] for item in active[:6]]
        limited_names = [item["name"] for item in limited[:4]]

        page_actions = {
            "overview": "From this page I can summarize live state, point you to the next priority, and open the right workflow.",
            "goals": "On Goals I can help you create a goal, inspect a focused goal, explain blockers, and suggest the safest next control action.",
            "approvals": "On Approvals I can explain what is waiting, what is approved, and what should be executed next.",
            "permissions": "On Permissions & Access I can explain which gates are active, limited, unavailable, or waiting for owner review.",
            "guide": "On Capabilities & Guide I can translate realism states into plain language and explain what is actually live.",
            "axis-hub": "On Axis Hub I can map which skill surfaces are live, partial, planned, or simulated.",
            "security": "On Security & Compliance I can summarize trust posture and call out where the system is intentionally conservative.",
            "settings": "On Settings I can explain which controls are editable now versus system-managed.",
            "profiles": "On Profiles & Plans I can explain which workspace posture is active and whether an upgrade would change anything meaningful.",
        }

        lines = [
            f"Axis currently has {len(active)} active permission-backed capability path(s).",
            f"Most relevant live surfaces right now: {', '.join(important_live) if important_live else 'none listed yet'}.",
        ]
        if limited_names:
            lines.append(
                f"Limited, planned, or unavailable surfaces still exist: {', '.join(limited_names)}."
            )
        lines.append(page_actions.get(page_id, f"On {page_title} I can stay grounded in the live dashboard state and explain what matters on this page."))
        if runtime.get("mock_llm"):
            lines.append("The current model route is mock mode, so I stay grounded and honest rather than pretending hidden intelligence exists.")
        if runtime.get("google_enabled") and not runtime.get("google_gmail_available"):
            lines.append("Google connectors are configured but currently degraded, so I can explain them honestly without treating them as fully live.")

        return self._make_chat_result(
            reply="\n".join(lines),
            intent="current_capabilities",
            source="permissions",
            source_label="Permissions and runtime snapshot",
            context={
                "page_id": page_id,
                "active_permissions": active[:10],
                "limited_permissions": limited[:10],
                "runtime": runtime,
            },
        )

    def _handle_today_summary_command(self):
        events = self._get_recent_goal_events_with_titles(limit=24)
        results = self.memory_engine.get_recent_results(limit=8)
        today = datetime.now().date()

        def _same_day(timestamp):
            if not timestamp:
                return False
            try:
                return datetime.fromisoformat(str(timestamp)).date() == today
            except ValueError:
                return str(timestamp).startswith(today.isoformat())

        today_events = [event for event in events if _same_day(event.get("created_at"))]
        today_results = [result for result in results if _same_day(result.get("timestamp") or result.get("created_at"))]
        approvals_count = self.memory_engine.count_pending_actions(status='actionable')
        blocked_count = self.memory_engine.get_control_counts().get("goals_blocked", 0)

        if not today_events and not today_results:
            if events:
                latest = events[0]
                goal_label = self._short_goal_label(latest.get("goal_title"), latest.get("goal_id"))
                reply = (
                    "I do not see any new goal events or result artifacts stamped today. "
                    f"The latest recorded change was {latest.get('event_type')} on {goal_label} at {latest.get('created_at')}."
                )
            else:
                reply = "I do not see any recorded goal events or result artifacts for today yet."
        else:
            lines = [f"Here is the Axis activity snapshot for today ({today.isoformat()}):"]
            for event in today_events[:5]:
                goal_label = self._short_goal_label(event.get("goal_title"), event.get("goal_id"))
                transition = (
                    f"{event.get('from_status') or 'unknown'} -> {event.get('to_status') or 'unknown'}"
                    if event.get("from_status") or event.get("to_status")
                    else (event.get("reason") or "state recorded")
                )
                lines.append(f"- {goal_label}: {event.get('event_type')} ({transition}) at {event.get('created_at')}.")
            if today_results:
                lines.append(f"{len(today_results)} result artifact(s) were also recorded today.")
            lines.append(f"Queue pressure right now: {approvals_count} approval item(s) and {blocked_count} blocked goal(s).")
            reply = "\n".join(lines)

        return self._make_chat_result(
            reply=reply,
            intent="today_summary",
            source="goal_events",
            source_label="Today's goal and result activity",
            context={
                "today": today.isoformat(),
                "events": today_events[:8],
                "results": today_results[:8],
                "approvals_count": approvals_count,
                "blocked_count": blocked_count,
            },
        )

    def _extract_goal_creation_request(self, user_message):
        match = re.search(r"\b(?:create|add|make)\s+(?:a\s+)?goal(?:\s+(?:for|to))?\s*[:\-]?\s+(.+)$", user_message.strip(), re.IGNORECASE)
        if not match:
            return None
        objective = match.group(1).strip().rstrip(".!?")
        return objective or None

    def _derive_goal_title(self, objective):
        words = re.findall(r"[A-Za-z0-9']+", objective)
        if not words:
            return "Untitled Goal"
        title_words = words[:6]
        return " ".join(word.capitalize() for word in title_words)

    def _short_goal_label(self, goal_title, goal_id):
        if goal_title:
            return goal_title
        if goal_id:
            return f"Goal {goal_id[:8]}"
        return "Unlinked item"

    def _match_related_permissions(self, reason_text, permissions=None):
        normalized_reason = (reason_text or "").lower()
        if not normalized_reason:
            return []

        ignored_tokens = {
            "access",
            "management",
            "control",
            "input",
            "output",
            "system",
            "local",
            "desktop",
            "owner",
            "actions",
            "capability",
            "capabilities",
            "integration",
            "integrations",
        }

        candidates = permissions
        if candidates is None:
            candidates = self.get_permissions_snapshot()["permissions"]

        related = []
        for item in candidates:
            if item["effective_status"] == "active":
                continue
            name_tokens = re.findall(r"[a-z0-9]+", item["name"].lower())
            key_tokens = re.findall(r"[a-z0-9]+", item["key"].lower())
            searchable_tokens = [
                token for token in (name_tokens[:2] + key_tokens[-2:])
                if len(token) > 2 and token not in ignored_tokens
            ]
            if any(token in normalized_reason for token in searchable_tokens):
                related.append(item)
        return related

    def get_permission_runtime(self):
        voice_caps = self.voice.get_capabilities() if getattr(self, "voice", None) else {}
        return {
            "web_automation_enabled": self.config.get("capabilities", {}).get("web_automation", {}).get("enabled", False),
            "voice_enabled": bool(voice_caps.get("voice_enabled") or voice_caps.get("enabled") or voice_caps.get("stt_available")),
            "voice_stt_provider": voice_caps.get("stt_provider"),
            "voice_tts_provider": voice_caps.get("tts_provider"),
            "notifications_enabled": bool(getattr(self, "notifications", None)),
            "google_enabled": self.config.get("google", {}).get("enabled", False),
            "google_gmail_available": bool(getattr(self, "gmail", None)),
            "google_calendar_available": bool(getattr(self, "calendar", None)),
            "mock_llm": False,
        }

    def get_permissions_snapshot(self, auth_context=None, user_agent=""):
        runtime = self.get_permission_runtime()
        summary = self.permissions.summarize_permissions(
            runtime=runtime,
            auth_context=auth_context,
            user_agent=user_agent,
        )
        return {
            "summary": summary,
            "permissions": self.permissions.list_permissions(
                runtime=runtime,
                auth_context=auth_context,
                user_agent=user_agent,
            ),
            "requests": self.memory_engine.list_permission_requests(limit=25),
            "session_class": self.permissions.get_session_class(auth_context=auth_context, user_agent=user_agent),
            "can_manage": self.permissions.can_manage_permissions(auth_context=auth_context, user_agent=user_agent),
        }

    def get_capabilities_guide(self):
        return self.permissions.get_capabilities_guide(runtime=self.get_permission_runtime())

    def _default_axis_profile(self):
        return {
            "id": "primary",
            "display_name": "Primary Axis Workspace",
            "profile_type": "developer",
            "plan_id": "foundation_free",
            "workspace_mode": "owner_controlled",
            "status": "active",
        }

    def _axis_profile_types(self):
        return [
            {
                "id": "student",
                "name": "Student",
                "summary": "Structured study, research, and guided planning with transparent controls.",
                "best_for": "Learning, research, and academic planning",
            },
            {
                "id": "developer",
                "name": "Developer",
                "summary": "A local-first workflow for shipping tasks, reviews, and governed automation.",
                "best_for": "Coding, debugging, controlled execution, and trust-heavy work",
            },
            {
                "id": "personal",
                "name": "Personal User",
                "summary": "A calm workspace for personal planning, reminders, and controlled assistance.",
                "best_for": "Personal organization and day-to-day AI support",
            },
            {
                "id": "data_scientist",
                "name": "Data Scientist",
                "summary": "A workspace oriented around experiments, documentation, and reproducible decisions.",
                "best_for": "Analysis, experiment notes, and governed execution",
            },
            {
                "id": "team",
                "name": "Team",
                "summary": "Shared operational workflows, approvals, and future multi-user governance.",
                "best_for": "Coordinated reviews and shared operating procedures",
            },
            {
                "id": "company",
                "name": "Company",
                "summary": "An operations shell for business workflows with stronger policy and audit expectations.",
                "best_for": "Company-wide operating procedures and approvals",
            },
            {
                "id": "enterprise",
                "name": "Enterprise",
                "summary": "A future enterprise-ready posture with policy, compliance, and environment controls.",
                "best_for": "Enterprise governance and compliance expansion",
            },
        ]

    def _axis_plan_catalog(self):
        return [
            {
                "id": "foundation_free",
                "name": "Foundation Free",
                "tier": "Free",
                "status": "active",
                "summary": "Core local workspace with goals, approvals, trust center, guide pages, and help.",
                "honest_fit": "Enough for local owner workflows, trust management, and grounded command routing.",
                "best_for": "Personal users, students, and early developer workspaces",
            },
            {
                "id": "builder",
                "name": "Builder",
                "tier": "Pro",
                "status": "partial",
                "summary": "Recommended when automation depth, skill growth, and operating scale increase.",
                "honest_fit": "Useful future path for heavier automation and richer integrations.",
                "best_for": "Developers and data scientists growing beyond a single local workspace",
            },
            {
                "id": "team",
                "name": "Team",
                "tier": "Team",
                "status": "planned",
                "summary": "Shared profiles, collaboration surfaces, and stronger multi-user controls.",
                "honest_fit": "Not a billing feature yet. The structure is being prepared honestly.",
                "best_for": "Small teams that need governed shared workflows",
            },
            {
                "id": "enterprise",
                "name": "Enterprise",
                "tier": "Enterprise",
                "status": "enterprise_planned",
                "summary": "Enterprise posture, policy packs, environment controls, and compliance expansion.",
                "honest_fit": "Not implemented as a real enterprise offering in this pass.",
                "best_for": "Organizations with formal security and compliance requirements",
            },
        ]

    def _axis_feature_matrix(self):
        return [
            {
                "feature": "Goals, approvals, blocked queue, and results",
                "availability": {
                    "foundation_free": "included",
                    "builder": "included",
                    "team": "included",
                    "enterprise": "included",
                },
            },
            {
                "feature": "Permissions & Access trust center",
                "availability": {
                    "foundation_free": "included",
                    "builder": "included",
                    "team": "included",
                    "enterprise": "included",
                },
            },
            {
                "feature": "Axis Help Center and system guide",
                "availability": {
                    "foundation_free": "included",
                    "builder": "included",
                    "team": "included",
                    "enterprise": "included",
                },
            },
            {
                "feature": "Governed web automation",
                "availability": {
                    "foundation_free": "guided",
                    "builder": "included",
                    "team": "included",
                    "enterprise": "included",
                },
            },
            {
                "feature": "Advanced shared policy controls",
                "availability": {
                    "foundation_free": "planned",
                    "builder": "planned",
                    "team": "partial",
                    "enterprise": "included",
                },
            },
            {
                "feature": "Enterprise posture packs and compliance exports",
                "availability": {
                    "foundation_free": "enterprise_planned",
                    "builder": "enterprise_planned",
                    "team": "planned",
                    "enterprise": "partial",
                },
            },
        ]

    def _axis_settings_catalog(self):
        return [
            {
                "group": "Appearance & Shell",
                "key": "appearance.theme_mode",
                "name": "Theme mode",
                "type": "select",
                "default": "axis_dark",
                "status": "live",
                "editable": False,
                "options": ["axis_dark"],
                "description": "Axis currently ships with a single premium dark workspace theme.",
            },
            {
                "group": "Notifications",
                "key": "notifications.owner_digest",
                "name": "Owner digest reminders",
                "type": "boolean",
                "default": True,
                "status": "live",
                "editable": True,
                "description": "Keep lightweight reminder surfaces enabled across the workspace.",
            },
            {
                "group": "Voice Preferences",
                "key": "voice.prefer_browser_speech",
                "name": "Prefer browser speech recognition",
                "type": "boolean",
                "default": True,
                "status": "live",
                "editable": True,
                "description": "Use browser-native speech recognition before backend fallback when available.",
            },
            {
                "group": "Voice Preferences",
                "key": "voice.reply_mode",
                "name": "Voice reply mode",
                "type": "select",
                "default": "text_and_audio",
                "status": "live",
                "editable": True,
                "options": ["text_and_audio", "text_only"],
                "description": "Decide whether Axis prepares both transcript replies and audio follow-up output.",
            },
            {
                "group": "Goal Behavior",
                "key": "goals.default_requires_approval",
                "name": "Default new goals to owner approval",
                "type": "boolean",
                "default": True,
                "status": "live",
                "editable": True,
                "description": "Bias the workspace toward approval-first execution realism.",
            },
            {
                "group": "Automation Preferences",
                "key": "automation.execution_posture",
                "name": "Automation posture",
                "type": "select",
                "default": "approval_first",
                "status": "live",
                "editable": False,
                "options": ["approval_first"],
                "description": "High-impact execution remains approval-first in this foundation pass.",
            },
            {
                "group": "Trust & Security Defaults",
                "key": "trust.high_risk_ack_required",
                "name": "High-risk acknowledgement required",
                "type": "boolean",
                "default": True,
                "status": "live",
                "editable": False,
                "description": "High-risk permission changes require an explicit acknowledgement before they can be enabled.",
            },
            {
                "group": "Trust & Security Defaults",
                "key": "trust.permission_request_mode",
                "name": "Permission request posture",
                "type": "select",
                "default": "owner_review",
                "status": "live",
                "editable": False,
                "options": ["owner_review"],
                "description": "Blocked capabilities surface owner-facing permission requests instead of auto-enabling trust.",
            },
            {
                "group": "Integrations",
                "key": "integrations.google_workspace",
                "name": "Google workspace integration",
                "type": "select",
                "default": "not_configured",
                "status": "not_configured",
                "editable": False,
                "options": ["not_configured"],
                "description": "Integration posture is shown honestly, but integration setup is not the focus of this pass.",
            },
            {
                "group": "Experimental",
                "key": "experimental.axis_hub_preview",
                "name": "Axis Hub preview",
                "type": "boolean",
                "default": True,
                "status": "live",
                "editable": False,
                "description": "Expose the ecosystem-level shell and skills foundation while future subsystems are still being built.",
            },
        ]

    def _axis_profile_state(self):
        profile = self.memory_engine.get_json_setting("axis.profile", self._default_axis_profile()) or {}
        merged = {**self._default_axis_profile(), **profile}
        valid_profile_types = {item["id"] for item in self._axis_profile_types()}
        valid_plans = {item["id"] for item in self._axis_plan_catalog()}
        if merged["profile_type"] not in valid_profile_types:
            merged["profile_type"] = self._default_axis_profile()["profile_type"]
        if merged["plan_id"] not in valid_plans:
            merged["plan_id"] = self._default_axis_profile()["plan_id"]
        return merged

    def _axis_setting_values(self):
        values = self.memory_engine.get_json_setting("axis.settings", {}) or {}
        normalized = {}
        for item in self._axis_settings_catalog():
            normalized[item["key"]] = values.get(item["key"], item["default"])
        return normalized

    def update_axis_profile(self, *, display_name=None, profile_type=None, plan_id=None):
        profile = self._axis_profile_state()
        valid_profile_types = {item["id"] for item in self._axis_profile_types()}
        valid_plans = {item["id"] for item in self._axis_plan_catalog()}

        if display_name is not None:
            cleaned = str(display_name).strip()
            if not cleaned:
                raise ValueError("Display name cannot be empty")
            profile["display_name"] = cleaned[:80]
        if profile_type is not None:
            if profile_type not in valid_profile_types:
                raise ValueError("Invalid profile type")
            profile["profile_type"] = profile_type
        if plan_id is not None:
            if plan_id not in valid_plans:
                raise ValueError("Invalid plan")
            profile["plan_id"] = plan_id

        self.memory_engine.set_json_setting("axis.profile", profile)
        return self.get_profiles_and_plans_snapshot()

    def update_axis_setting(self, setting_key, value):
        catalog = {item["key"]: item for item in self._axis_settings_catalog()}
        item = catalog.get(setting_key)
        if not item:
            raise KeyError(setting_key)
        if not item.get("editable"):
            raise ValueError("Setting is not editable in this pass")

        if item["type"] == "boolean":
            if not isinstance(value, bool):
                raise ValueError("Boolean value required")
        elif item["type"] == "select":
            if value not in item.get("options", []):
                raise ValueError("Invalid setting option")
        else:
            raise ValueError("Unsupported setting type")

        settings = self._axis_setting_values()
        settings[setting_key] = value
        self.memory_engine.set_json_setting("axis.settings", settings)
        return self.get_settings_snapshot()

    def _plan_lookup(self, plan_id):
        return next((plan for plan in self._axis_plan_catalog() if plan["id"] == plan_id), None)

    def get_profiles_and_plans_snapshot(self):
        profile = self._axis_profile_state()
        plans = self._axis_plan_catalog()
        active_plan = self._plan_lookup(profile["plan_id"]) or plans[0]
        counts = self.memory_engine.get_control_counts()
        permissions_summary = self.permissions.summarize_permissions(runtime=self.get_permission_runtime())

        feature_matrix = []
        for row in self._axis_feature_matrix():
            active_status = row["availability"].get(active_plan["id"], "planned")
            feature_matrix.append({
                "feature": row["feature"],
                "active_status": active_status,
                "availability": row["availability"],
            })

        if active_plan["id"] == "foundation_free" and counts.get("goals_total", 0) <= 12 and permissions_summary.get("counts", {}).get("high_risk_enabled", 0) <= 2:
            upgrade_guidance = {
                "status": "honest_free_fit",
                "title": "Current free path looks sufficient",
                "copy": "Your current governed goals, approvals, trust center, and help workflows fit comfortably inside the Foundation Free posture right now.",
            }
        elif active_plan["id"] == "foundation_free":
            upgrade_guidance = {
                "status": "upgrade_recommended",
                "title": "Upgrade may become useful soon",
                "copy": "Axis can keep running locally on Foundation Free, but expanding automation depth or broader workspace governance would justify a Builder-style plan later.",
            }
        else:
            upgrade_guidance = {
                "status": "aligned",
                "title": "Current profile and plan are aligned",
                "copy": f"{active_plan['name']} is a good fit for the current {profile['profile_type'].replace('_', ' ')} workspace posture.",
            }

        return {
            "active_profile": {
                **profile,
                "profile_label": next(
                    (item["name"] for item in self._axis_profile_types() if item["id"] == profile["profile_type"]),
                    profile["profile_type"].replace("_", " ").title(),
                ),
            },
            "active_plan": active_plan,
            "profile_types": self._axis_profile_types(),
            "plans": [
                {
                    **plan,
                    "selected": plan["id"] == active_plan["id"],
                }
                for plan in plans
            ],
            "feature_matrix": feature_matrix,
            "upgrade_guidance": upgrade_guidance,
            "summary": {
                "profiles_configured": 1,
                "current_plan": active_plan["name"],
                "workspace_type": profile["profile_type"].replace("_", " "),
            },
        }

    def get_settings_snapshot(self):
        values = self._axis_setting_values()
        groups = {}
        counts = {}
        for item in self._axis_settings_catalog():
            status = item["status"]
            counts[status] = counts.get(status, 0) + 1
            groups.setdefault(item["group"], []).append({
                **item,
                "value": values.get(item["key"], item["default"]),
            })
        return {
            "groups": groups,
            "summary": counts,
            "session_note": "Editable settings are intentionally limited to safe foundation controls in this pass.",
        }

    def _axis_skill_catalog(self):
        runtime = self.get_permission_runtime()
        permissions = {item["key"]: item for item in self.get_permissions_snapshot()["permissions"]}
        live_snapshot = self.get_live_control_snapshot(approvals_limit=3, blocked_limit=3, results_limit=3, events_limit=3, goals_limit=3, rec_limit=3)
        voice_caps = live_snapshot.get("voice") or {}
        voice_state = "live"
        if voice_caps.get("stt_provider") == "mock" or voice_caps.get("tts_provider") == "mock":
            voice_state = "partial"
        web_state = "partial" if runtime.get("web_automation_enabled") else "planned"
        google_state = "partial" if runtime.get("google_enabled") else "planned"

        catalog = [
            {
                "id": "goal_orchestration",
                "name": "Goal orchestration",
                "group": "Core Workspace",
                "state": "live",
                "summary": "Structured goals, planning, execution state, and controlled next-step guidance.",
                "dependencies": ["GoalEngine", "Approvals", "Results"],
                "permission_dependencies": ["goals.manage", "goals.execute", "goals.control"],
                "usage_signal": f"{live_snapshot['counts'].get('goals_total', 0)} goal(s) are in the database.",
                "training_state": "Owner-directed refinement only",
            },
            {
                "id": "approval_governance",
                "name": "Approval governance",
                "group": "Trust & Execution",
                "state": "live",
                "summary": "Pending actions are reviewed, approved, denied, and executed through explicit owner control.",
                "dependencies": ["PendingActions", "Goal lineage"],
                "permission_dependencies": ["approvals.manage"],
                "usage_signal": f"{self.memory_engine.count_pending_actions(status='actionable')} actionable approval item(s).",
                "training_state": "No autonomous execution bypass",
            },
            {
                "id": "trust_policy_routing",
                "name": "Trust policy routing",
                "group": "Trust & Execution",
                "state": "live",
                "summary": "Permission-aware routes explain blocked work and surface owner-facing requests.",
                "dependencies": ["PermissionService", "Permission requests"],
                "permission_dependencies": ["dashboard.access"],
                "usage_signal": f"{self.memory_engine.count_permission_requests(status='pending')} pending permission request(s).",
                "training_state": "Governed trust policy, not self-adjusting",
            },
            {
                "id": "voice_command_router",
                "name": "Voice and command routing",
                "group": "Interaction Layer",
                "state": voice_state,
                "summary": "Voice and text fallback route through grounded command handling with explicit safety context.",
                "dependencies": ["VoiceInterface", "Grounded command router"],
                "permission_dependencies": ["voice.input", "voice.output"],
                "usage_signal": f"STT {voice_caps.get('stt_provider', 'unknown')} | TTS {voice_caps.get('tts_provider', 'unknown')}.",
                "training_state": "Provider-backed, no autonomous adaptation",
            },
            {
                "id": "governed_web_execution",
                "name": "Governed web execution",
                "group": "Execution Surfaces",
                "state": web_state,
                "summary": "Web actions remain approval-gated and intentionally bounded.",
                "dependencies": ["WebAutomationEngine", "Approval queue"],
                "permission_dependencies": ["browser.web_access", "browser.web_automation"],
                "usage_signal": "Available only through governed planning and execution routes.",
                "training_state": "Execution realism only, not autonomous browsing growth",
            },
            {
                "id": "guide_and_docs",
                "name": "Documentation and explainability",
                "group": "Knowledge Surface",
                "state": "live",
                "summary": "Capabilities, realism state, and workflow documentation are exposed inside the product shell.",
                "dependencies": ["Capabilities guide", "Help center"],
                "permission_dependencies": ["dashboard.access"],
                "usage_signal": "Guide pages and help context are always available to the owner.",
                "training_state": "Manual product knowledge curation",
            },
            {
                "id": "google_workspace_connectors",
                "name": "Workspace connectors",
                "group": "Integrations",
                "state": google_state,
                "summary": "External connectors are shown honestly as live, degraded, or not configured.",
                "dependencies": ["GmailClient", "CalendarClient"],
                "permission_dependencies": ["integration.gmail", "integration.calendar"],
                "usage_signal": live_snapshot.get("google", {}).get("status", "degraded"),
                "training_state": "Connector readiness only",
            },
            {
                "id": "profiles_and_plan_advisor",
                "name": "Profiles and plan advisor",
                "group": "Workspace Growth",
                "state": "live",
                "summary": "Profile and plan context explain which workspace posture Axis is currently optimized for.",
                "dependencies": ["Workspace profile", "Plan matrix"],
                "permission_dependencies": ["dashboard.access"],
                "usage_signal": self.get_profiles_and_plans_snapshot()["active_plan"]["name"],
                "training_state": "Advisory only, no billing",
            },
            {
                "id": "skill_development_lane",
                "name": "Skill development lane",
                "group": "Workspace Growth",
                "state": "planned",
                "summary": "A future registry for owner-directed skill building, testing, and release readiness.",
                "dependencies": ["Axis Hub", "Future skill runners"],
                "permission_dependencies": ["experimental.capabilities"],
                "usage_signal": "Foundation page only in this pass.",
                "training_state": "Not an active self-improvement loop",
            },
            {
                "id": "continual_learning_visibility",
                "name": "Continual learning visibility",
                "group": "Workspace Growth",
                "state": "simulated",
                "summary": "Axis can explain how the workspace may grow, but it does not autonomously self-train in this pass.",
                "dependencies": ["Axis Hub", "Owner guidance"],
                "permission_dependencies": [],
                "usage_signal": "Truthful roadmap visibility only.",
                "training_state": "No unsafe self-training enabled",
            },
        ]

        for item in catalog:
            dependency_states = [
                permissions.get(key, {}).get("effective_status", "unknown")
                for key in item["permission_dependencies"]
            ]
            item["availability"] = (
                "disabled"
                if any(state == "disabled" for state in dependency_states)
                else ("planned" if item["state"] in ("planned", "simulated", "experimental") else "active")
            )
        return catalog

    def get_axis_hub_snapshot(self):
        skills = self._axis_skill_catalog()
        summary = {}
        availability = {}
        for item in skills:
            summary[item["state"]] = summary.get(item["state"], 0) + 1
            availability[item["availability"]] = availability.get(item["availability"], 0) + 1

        live_snapshot = self.get_live_control_snapshot(approvals_limit=3, blocked_limit=3, results_limit=3, events_limit=3, goals_limit=3, rec_limit=3)
        return {
            "summary": summary,
            "availability": availability,
            "skills": skills,
            "activity": {
                "active_goals": live_snapshot["counts"].get("goals_active", 0),
                "pending_approvals": self.memory_engine.count_pending_actions(status="actionable"),
                "blocked_items": len(live_snapshot.get("blocked", [])),
                "recent_events": len(live_snapshot.get("events", [])),
                "pending_permission_requests": self.memory_engine.count_permission_requests(status="pending"),
            },
            "training_visibility": [
                {
                    "title": "No autonomous self-training",
                    "status": "active",
                    "summary": "Axis does not rewrite its own execution logic or elevate privileges without explicit owner work.",
                },
                {
                    "title": "Owner-directed skill growth",
                    "status": "partial",
                    "summary": "Skills are explained, categorized, and tracked, but future deeper skill runners remain a roadmap item.",
                },
                {
                    "title": "Experiment tracking",
                    "status": "planned",
                    "summary": "Axis Hub is ready to host richer experiment and skill-development workflows later.",
                },
            ],
        }

    def get_security_compliance_snapshot(self, auth_context=None, user_agent=""):
        runtime = self.get_permission_runtime()
        permissions_snapshot = self.get_permissions_snapshot(auth_context=auth_context, user_agent=user_agent)
        remote_enabled = bool(self.config.get("server", {}).get("remote_enabled"))
        google_status = "degraded"
        if runtime.get("google_enabled") and runtime.get("google_gmail_available") and runtime.get("google_calendar_available"):
            google_status = "active"
        elif not runtime.get("google_enabled"):
            google_status = "not_configured"

        cards = [
            {
                "title": "Permission enforcement",
                "status": "active",
                "summary": "System permissions are enforced in backend routes and goal execution paths.",
                "detail": "Blocked work creates readable permission-block responses and permission requests instead of silently bypassing trust.",
            },
            {
                "title": "Owner trust boundary",
                "status": "active",
                "summary": "High-risk trust changes remain desktop-owner controlled.",
                "detail": f"Current session class: {self.permissions.get_session_class(auth_context=auth_context, user_agent=user_agent)}.",
            },
            {
                "title": "Environment posture",
                "status": "experimental" if remote_enabled else "local_only",
                "summary": "Axis is currently optimized for a local-first trusted runtime.",
                "detail": "Remote exposure requires a deliberate reverse-proxy posture and is not treated as enterprise-ready in this pass.",
            },
            {
                "title": "Audit visibility",
                "status": "active",
                "summary": "Request activity and goal events are persisted for inspection.",
                "detail": "The workspace keeps structured approval, goal, and activity trails for owner review.",
            },
            {
                "title": "Data-at-rest encryption",
                "status": "not_configured",
                "summary": "This local SQLite-backed workspace does not claim built-in encrypted storage.",
                "detail": "Storage hardening and enterprise key management are future security-expansion work.",
            },
            {
                "title": "Compliance posture",
                "status": "enterprise_planned",
                "summary": "Axis can explain trust boundaries today, but it does not claim enterprise compliance certifications.",
                "detail": "Enterprise policy packs, audit exports, and compliance narratives are product-foundation work only in this pass.",
            },
            {
                "title": "External integration posture",
                "status": google_status,
                "summary": "External connectors are represented honestly instead of being treated as silently live.",
                "detail": "Connector readiness depends on explicit configuration, permissions, and runtime health.",
            },
        ]

        summary = {}
        for card in cards:
            summary[card["status"]] = summary.get(card["status"], 0) + 1

        return {
            "summary": summary,
            "cards": cards,
            "trust_overview": {
                "disabled_permissions": permissions_snapshot["summary"]["counts"].get("disabled", 0),
                "high_risk_enabled": permissions_snapshot["summary"]["counts"].get("high_risk_enabled", 0),
                "pending_permission_requests": self.memory_engine.count_permission_requests(status="pending"),
            },
        }

    def _goal_skill_matches(self, context):
        if not context:
            return []
        objective = f"{context.get('title', '')} {context.get('objective', '')}".lower()
        steps = context.get("steps") or []
        capabilities = {str(step.get("capability_type", "")).lower() for step in steps}
        matches = []
        for skill in self._axis_skill_catalog():
            text = f"{skill['name']} {skill['summary']} {' '.join(skill['permission_dependencies'])}".lower()
            if any(token in objective for token in ("goal", "plan", "approval")) and skill["id"] in ("goal_orchestration", "approval_governance", "trust_policy_routing"):
                matches.append(skill)
                continue
            if any(cap and cap in text for cap in capabilities if cap):
                matches.append(skill)
                continue
            if "voice" in objective and skill["id"] == "voice_command_router":
                matches.append(skill)
                continue
            if "web" in objective and skill["id"] == "governed_web_execution":
                matches.append(skill)
                continue
        unique = []
        seen = set()
        for item in matches:
            if item["id"] not in seen:
                unique.append({
                    "id": item["id"],
                    "name": item["name"],
                    "state": item["state"],
                    "availability": item["availability"],
                })
                seen.add(item["id"])
        return unique[:5]

    def _goal_profile_plan_summary(self, context, dependencies):
        profile_snapshot = self.get_profiles_and_plans_snapshot()
        active_profile = profile_snapshot["active_profile"]
        active_plan = profile_snapshot["active_plan"]
        blocked_dependencies = [item for item in dependencies if item["effective_status"] != "active"]
        steps = context.get("steps") or []
        touches_web = any("web" in str(step.get("capability_type", "")).lower() for step in steps) or "web" in str(context.get("objective", "")).lower()

        if blocked_dependencies:
            status = "permission_required"
            summary_text = "Trust settings are the current blocker, not the active plan."
            explanation = "Resolve the listed permission dependency first. Profiles and plans do not bypass permission controls."
        elif touches_web and active_plan["id"] == "foundation_free":
            status = "guided"
            summary_text = "Current plan can run this governed workflow, but heavier automation growth may eventually justify Builder guidance."
            explanation = "This goal still fits the current local workspace. The plan signal is advisory, not a hard gate."
        else:
            status = "included"
            summary_text = f"{active_plan['name']} currently covers this governed goal workflow."
            explanation = "Profiles and plans are explanatory in this pass. They do not override approval or permission controls."

        return {
            "status": status,
            "profile_label": active_profile["profile_label"],
            "plan_name": active_plan["name"],
            "summary": summary_text,
            "explanation": explanation,
        }

    def get_axis_help_snapshot(self, page_id="overview", goal_id=None, auth_context=None, user_agent=""):
        live_snapshot = self.get_live_control_snapshot(approvals_limit=3, blocked_limit=4, results_limit=3, events_limit=3, goals_limit=3, rec_limit=4)
        profiles = self.get_profiles_and_plans_snapshot()
        settings = self.get_settings_snapshot()
        permissions_snapshot = self.get_permissions_snapshot(auth_context=auth_context, user_agent=user_agent)
        active_profile = profiles["active_profile"]
        active_plan = profiles["active_plan"]
        goal_summary = self.get_goal_summary(goal_id) if goal_id else None
        goal_context = self.goal_engine.get_goal_context(goal_id) if goal_id else None
        page_titles = {
            "overview": "Overview",
            "goals": "Goals",
            "approvals": "Approvals",
            "blocked": "Blocked",
            "results": "Results",
            "voice": "Voice",
            "permissions": "Permissions & Access",
            "guide": "Capabilities & Guide",
            "axis-hub": "Axis Hub",
            "security": "Security & Compliance",
            "settings": "Settings",
            "profiles": "Profiles & Plans",
        }
        page_title = page_titles.get(page_id, "Workspace")

        page_copy = {
            "overview": "Overview is the landing surface for trust signals, queues, recent changes, and next-step recommendations.",
            "goals": "Goals is the structured workspace for inspecting, editing, pausing, resuming, and replanning governed execution.",
            "approvals": "Approvals shows exactly what is pending, approved, denied, or already executed before work moves forward.",
            "blocked": "Blocked collects goals and steps that need trust, approval, or intervention before they can continue.",
            "results": "Results shows completed artifacts and outcome references without exposing raw system payloads in the primary view.",
            "voice": "Voice routes spoken or typed commands through the same governed command path and surfaces the grounding source.",
            "permissions": "Permissions & Access is the trust center for deciding what Axis can access or control.",
            "guide": "Capabilities & Guide explains what is live, partial, mocked, degraded, planned, or experimental.",
            "axis-hub": "Axis Hub explains how skills, maturity, and future growth are organized without pretending unsafe self-improvement exists.",
            "security": "Security & Compliance explains the current local-first trust model, audit posture, and enterprise roadmap honestly.",
            "settings": "Settings keeps current real preferences and future configuration space organized in one place.",
            "profiles": "Profiles & Plans explains which kind of user this workspace is optimized for and what the current plan means.",
        }.get(page_id, "Axis Help Center provides page-aware guidance and trustworthy next steps.")

        blockers = []
        suggested_actions = []

        if goal_summary and goal_context:
            if goal_summary.get("blocked_dependencies"):
                blockers.append({
                    "title": "Permission dependency is blocking this goal",
                    "copy": ", ".join(item["name"] for item in goal_summary["blocked_dependencies"][:3]),
                    "page": "permissions",
                    "button": "Open Permissions & Access",
                })
            if goal_summary.get("status") == "awaiting_approval":
                blockers.append({
                    "title": "Owner approval is still required",
                    "copy": "Approve or deny the linked action before this goal can move again.",
                    "page": "approvals",
                    "button": "Review Approvals",
                })
            if goal_summary.get("status") == "blocked" and goal_summary.get("blocked_reason"):
                blockers.append({
                    "title": "Goal is blocked",
                    "copy": goal_summary["blocked_reason"],
                    "page": "blocked",
                    "button": "Open Blocked",
                })
            suggested_actions.append({
                "label": "Inspect selected goal",
                "goal_id": goal_id,
                "summary": goal_summary.get("recommended_next_action") if isinstance(goal_summary.get("recommended_next_action"), str) else goal_summary.get("recommended_next_action", {}).get("recommended_action", "Review the goal detail."),
            })

        for item in live_snapshot.get("recommendations", [])[:3]:
            suggested_actions.append({
                "label": item.get("goal_title") or "Open workflow",
                "goal_id": item.get("goal_id"),
                "page": None if item.get("goal_id") else "overview",
                "summary": item.get("recommended_action"),
            })

        if permissions_snapshot["summary"]["counts"].get("disabled", 0):
            suggested_actions.append({
                "label": "Review trust posture",
                "page": "permissions",
                "summary": f"{permissions_snapshot['summary']['counts'].get('disabled', 0)} permission(s) are disabled right now.",
            })

        suggested_actions = suggested_actions[:4]

        if active_plan["id"] == "foundation_free":
            plan_guidance = "Current guided local workflows still fit inside the Foundation Free posture. Upgrade only when you genuinely need more depth."
        else:
            plan_guidance = f"The current workspace is aligned to {active_plan['name']}. Axis will still explain blocked capabilities honestly instead of masking them behind plan language."

        return {
            "assistant_name": "Axis Help Center",
            "status": "active",
            "page_title": page_title,
            "page_copy": page_copy,
            "trust_summary": {
                "pending_permission_requests": self.memory_engine.count_permission_requests(status="pending"),
                "disabled_permissions": permissions_snapshot["summary"]["counts"].get("disabled", 0),
                "blocked_items": len(live_snapshot.get("blocked", [])),
            },
            "workspace_summary": {
                "profile": active_profile["profile_label"],
                "plan": active_plan["name"],
                "session_class": self.permissions.get_session_class(auth_context=auth_context, user_agent=user_agent),
            },
            "blockers": blockers,
            "suggested_actions": suggested_actions,
            "profile_guidance": {
                "title": f"{active_profile['profile_label']} profile on {active_plan['name']}",
                "copy": plan_guidance,
            },
            "settings_guidance": {
                "editable_live_settings": sum(
                    1
                    for items in settings["groups"].values()
                    for item in items
                    if item["status"] == "live" and item.get("editable")
                ),
                "copy": settings["session_note"],
            },
        }

    def _permission_block_result(self, permission_key, reason, *, intent, source, source_label, goal_id=None, goal_title=None, action_label=None):
        block = self.permissions.build_permission_block(
            permission_key,
            reason,
            goal_id=goal_id,
            goal_title=goal_title,
            action_label=action_label,
            source=source,
        )
        return self._make_chat_result(
            reply=block["message"],
            intent=intent,
            source=source,
            source_label=source_label,
            context=block,
        )

    def _get_recent_goal_events_with_titles(self, limit=5):
        try:
            from jarvis_ai.db.supabase_client import get_supabase
            res = get_supabase().table("goal_events").select("*").order("created_at", desc=True).limit(limit).execute()
            if not res.data:
                return []
            events = res.data
            goal_ids = [e['goal_id'] for e in events if e.get('goal_id')]
            if goal_ids:
                goal_res = get_supabase().table("goals").select("id, title").in_("id", list(set(goal_ids))).execute()
                goal_dict = {g['id']: g.get('title') for g in goal_res.data} if goal_res.data else {}
                for e in events:
                    if e.get('goal_id') in goal_dict:
                        e['goal_title'] = goal_dict[e['goal_id']]
            return events
        except Exception:
            return []

    def get_live_control_snapshot(self, approvals_limit=5, blocked_limit=5, results_limit=5, events_limit=5, goals_limit=5, rec_limit=5):
        counts = self.memory_engine.get_control_counts()
        approvals = self.memory_engine.get_pending_approvals_with_linkage(limit=approvals_limit, status='actionable')
        blocked = self.memory_engine.get_blocked_items(limit=blocked_limit)
        results = self.memory_engine.get_recent_results(limit=results_limit)
        goals = self.goal_engine.list_goals()[:goals_limit]
        recommendations = self.get_recommended_next_actions(limit=rec_limit)
        events = self._get_recent_goal_events_with_titles(limit=events_limit)
        permissions_summary = self.permissions.summarize_permissions(runtime=self.get_permission_runtime())
        permissions = self.get_permissions_snapshot()["permissions"]
        permission_requests = self.memory_engine.list_permission_requests(status='pending', limit=5)

        enriched_blocked = []
        for item in blocked:
            related_permissions = self._match_related_permissions(item.get("blocked_reason"), permissions=permissions)
            related_permission_keys = {entry["key"] for entry in related_permissions}
            related_requests = [
                req for req in permission_requests
                if req.get("permission_key") in related_permission_keys
            ]
            enriched_blocked.append({
                **item,
                "permission_blocked": bool(related_permissions),
                "related_permissions": related_permissions[:5],
                "pending_permission_requests": related_requests[:3],
            })

        google_status = "available" if getattr(self, "gmail", None) and getattr(self, "calendar", None) else "degraded"
        google_reason = None
        if google_status != "available":
            google_reason = self.google_degraded_reason or "token_missing_or_not_connected"

        return {
            "counts": counts,
            "approvals": approvals,
            "blocked": enriched_blocked,
            "results": results,
            "goals": goals,
            "recommendations": recommendations,
            "events": events,
            "google": {
                "status": google_status,
                "reason": google_reason
            },
            "voice": self.voice.get_capabilities() if getattr(self, "voice", None) else None,
            "permissions": permissions_summary,
            "permission_requests": permission_requests,
        }

    def _build_live_state_prompt(self):
        snapshot = self.get_live_control_snapshot(approvals_limit=3, blocked_limit=3, results_limit=3, events_limit=3, goals_limit=3, rec_limit=3)
        counts = snapshot["counts"]
        latest_event = snapshot["events"][0] if snapshot["events"] else None
        latest_goal = self._short_goal_label(latest_event.get("goal_title"), latest_event.get("goal_id")) if latest_event else "none"
        latest_action = snapshot["recommendations"][0]["recommended_action"] if snapshot["recommendations"] else "Add a new goal to get started"
        return (
            f"active_goals={counts.get('goals_active', 0)}\n"
            f"awaiting_approval_goals={counts.get('goals_awaiting_approval', 0)}\n"
            f"blocked_goals={counts.get('goals_blocked', 0)}\n"
            f"completed_goals={counts.get('goals_completed', 0)}\n"
            f"pending_actions={counts.get('pending_actions', 0)}\n"
            f"google_status={snapshot['google']['status']}\n"
            f"latest_event_goal={latest_goal}\n"
            f"latest_recommendation={latest_action}"
        )

    def _response_needs_grounded_fallback(self, response_text):
        if not response_text:
            return True
        generic_markers = (
            "system performance is optimal",
            "suggesting proactive knowledge exploration",
            "i'm sorry, i encountered an error",
            "i heard you say"
        )
        return any(marker in response_text.lower() for marker in generic_markers)

    def _handle_goal_creation_command(self, objective):
        title = self._derive_goal_title(objective)
        goal = self.goal_engine.create_goal(objective, title=title, priority='normal', requires_approval=True)
        snapshot = self.get_live_control_snapshot(approvals_limit=3, blocked_limit=3, results_limit=3, events_limit=3, goals_limit=3, rec_limit=3)
        approvals_count = self.memory_engine.count_pending_actions(status='actionable')
        reply = (
            f"I created a new draft goal in Axis: '{goal['title']}' (ID {goal['id']}). "
            "It is in the real goal queue now and nothing has executed yet. "
            f"Current live context: {approvals_count} actionable approval item(s) and {snapshot['counts'].get('goals_blocked', 0)} blocked goal(s)."
        )
        return self._make_chat_result(
            reply=reply,
            intent="create_goal",
            source="goal_engine.create_goal",
            source_label="Goal queue",
            context={
                "goal_id": goal["id"],
                "goal_title": goal["title"],
                "status": goal["status"],
                "approvals_count": approvals_count
            }
        )

    def _handle_pending_approvals_command(self):
        approvals = self.memory_engine.get_pending_approvals_with_linkage(limit=8, status='actionable')
        approvals_count = self.memory_engine.count_pending_actions(status='actionable')
        pending_count = self.memory_engine.count_pending_actions(status='pending')
        approved_count = self.memory_engine.count_pending_actions(status='approved')

        if approvals_count == 0:
            reply = "Nothing is waiting for approval right now. Pending approvals: 0, approved-and-ready actions: 0."
        else:
            lines = [
                f"You have {approvals_count} actionable approval item(s): {pending_count} still pending review and {approved_count} already approved, ready to execute."
            ]
            for item in approvals[:5]:
                goal_label = self._short_goal_label(item.get("goal_title"), item.get("goal_id"))
                status_text = "pending review" if item.get("action_status") == "pending" else "approved and ready to execute"
                lines.append(f"- {goal_label}: {item.get('action_type', 'unknown')} is {status_text}.")
            reply = "\n".join(lines)

        return self._make_chat_result(
            reply=reply,
            intent="pending_approvals_summary",
            source="control_approvals",
            source_label="Pending approvals queue",
            context={
                "approvals_count": approvals_count,
                "pending_count": pending_count,
                "approved_count": approved_count,
                "items": [
                    {
                        "action_id": item.get("action_id"),
                        "goal_title": item.get("goal_title"),
                        "action_type": item.get("action_type"),
                        "action_status": item.get("action_status")
                    }
                    for item in approvals[:5]
                ]
            }
        )

    def _handle_blocked_goals_command(self):
        blocked = self.memory_engine.get_blocked_items(limit=8)
        blocked_count = self.memory_engine.get_control_counts().get("goals_blocked", 0)

        if blocked_count == 0:
            reply = "No blocked goals are recorded right now."
        else:
            lines = [f"There {'is' if blocked_count == 1 else 'are'} {blocked_count} blocked item(s) right now."]
            for item in blocked[:5]:
                goal_label = self._short_goal_label(item.get("goal_title"), item.get("goal_id"))
                lines.append(f"- {goal_label}: {item.get('blocked_reason') or 'Unknown reason'}.")
            reply = "\n".join(lines)

        return self._make_chat_result(
            reply=reply,
            intent="blocked_goals_summary",
            source="control_blocked",
            source_label="Blocked goals list",
            context={
                "blocked_count": blocked_count,
                "items": [
                    {
                        "goal_id": item.get("goal_id"),
                        "goal_title": item.get("goal_title"),
                        "blocked_reason": item.get("blocked_reason"),
                        "recommended_resolution": item.get("recommended_resolution")
                    }
                    for item in blocked[:5]
                ]
            }
        )

    def _handle_recommended_next_action_command(self):
        recommendations = self.get_recommended_next_actions(limit=5)
        if not recommendations:
            reply = "I do not have a recommended next action yet. Creating a new goal is the safest next step."
        else:
            lines = ["Based on the live system state, here is what I would do next:"]
            for idx, rec in enumerate(recommendations[:3], start=1):
                goal_label = rec.get("goal_title") or self._short_goal_label(None, rec.get("goal_id"))
                lines.append(f"{idx}. {goal_label}: {rec.get('recommended_action')}")
            reply = "\n".join(lines)

        return self._make_chat_result(
            reply=reply,
            intent="recommended_next_actions",
            source="control_summary",
            source_label="Recommended next actions",
            context={
                "recommendations": recommendations[:5]
            }
        )

    def _handle_system_status_command(self):
        snapshot = self.get_live_control_snapshot(approvals_limit=3, blocked_limit=3, results_limit=3, events_limit=3, goals_limit=3, rec_limit=3)
        counts = snapshot["counts"]
        approvals_count = self.memory_engine.count_pending_actions(status='actionable')
        blocked_count = counts.get('goals_blocked', 0)
        results_count = self.memory_engine.count_recent_results()
        latest_event = snapshot["events"][0] if snapshot["events"] else None
        latest_recommendation = snapshot["recommendations"][0]["recommended_action"] if snapshot["recommendations"] else "Add a new goal to get started"
        voice_caps = snapshot.get("voice") or {}
        disabled_permissions = snapshot.get("permissions", {}).get("counts", {}).get("disabled", 0)
        pending_permission_requests = self.memory_engine.count_permission_requests(status='pending')

        lines = [
            f"Axis is online locally. Current state: {counts.get('goals_active', 0)} active goal(s), {approvals_count} actionable approval item(s), {blocked_count} blocked item(s), and {results_count} recent result artifact(s).",
            f"Google is {snapshot['google']['status']}{f' ({snapshot['google']['reason']})' if snapshot['google'].get('reason') else ''}. Voice is using {voice_caps.get('stt_provider', 'unknown')} STT and {voice_caps.get('tts_provider', 'unknown')} TTS.",
            f"Permissions posture: {disabled_permissions} disabled permission(s) and {pending_permission_requests} pending permission request(s).",
            f"Recommended next action: {latest_recommendation}."
        ]

        if latest_event:
            goal_label = self._short_goal_label(latest_event.get("goal_title"), latest_event.get("goal_id"))
            lines.append(
                f"Latest change: {goal_label} recorded {latest_event.get('event_type')} at {latest_event.get('created_at')}."
            )

        return self._make_chat_result(
            reply="\n".join(lines),
            intent="system_status_summary",
            source="control_summary_readiness",
            source_label="Control summary and live state",
            context={
                "counts": counts,
                "approvals_count": approvals_count,
                "blocked_count": blocked_count,
                "results_count": results_count,
                "google": snapshot["google"],
                "voice": {
                    "stt_provider": voice_caps.get("stt_provider"),
                    "tts_provider": voice_caps.get("tts_provider")
                },
                "disabled_permissions_count": disabled_permissions,
                "pending_permission_requests": pending_permission_requests,
                "latest_event": latest_event,
                "top_recommendation": latest_recommendation
            }
        )

    def _handle_recent_changes_command(self):
        events = self._get_recent_goal_events_with_titles(limit=6)
        if not events:
            reply = "No recent goal events are recorded yet."
        else:
            lines = ["Here are the most recent changes I can see in the real goal/event log:"]
            for event in events[:5]:
                goal_label = self._short_goal_label(event.get("goal_title"), event.get("goal_id"))
                transition = (
                    f"{event.get('from_status') or 'unknown'} -> {event.get('to_status') or 'unknown'}"
                    if event.get("from_status") or event.get("to_status")
                    else (event.get("reason") or "state recorded")
                )
                lines.append(f"- {goal_label}: {event.get('event_type')} ({transition}) at {event.get('created_at')}.")
            reply = "\n".join(lines)

        return self._make_chat_result(
            reply=reply,
            intent="recent_changes_summary",
            source="goal_events",
            source_label="Recent goal events",
            context={"events": events[:5]}
        )

    def _handle_recent_results_command(self):
        results = self.memory_engine.get_recent_results(limit=5)
        results_count = self.memory_engine.count_recent_results()
        if results_count == 0:
            reply = "There are no recent result artifacts recorded right now."
        else:
            lines = [f"I can see {results_count} recent result artifact(s):"]
            for result in results[:5]:
                goal_label = self._short_goal_label(result.get("goal_title"), result.get("goal_id"))
                lines.append(f"- {goal_label}: {result.get('summary')} ({result.get('status')})")
            reply = "\n".join(lines)

        return self._make_chat_result(
            reply=reply,
            intent="recent_results_summary",
            source="control_results",
            source_label="Recent results ledger",
            context={
                "results_count": results_count,
                "results": results[:5]
            }
        )

    def _handle_goals_overview_command(self):
        goals = self.goal_engine.list_goals()[:8]
        if not goals:
            reply = "There are no goals in the queue right now."
        else:
            lines = [f"There are {len(self.goal_engine.list_goals())} goal(s) in the queue. Here are the most recent ones:"]
            for goal in goals[:5]:
                lines.append(f"- {goal.get('title') or 'Untitled Goal'}: {goal.get('status')} (priority {goal.get('priority', 'normal')})")
            reply = "\n".join(lines)

        return self._make_chat_result(
            reply=reply,
            intent="goals_overview",
            source="goal_queue",
            source_label="Goal queue",
            context={"goals": goals[:5]}
        )

    def _handle_disabled_permissions_command(self):
        snapshot = self.get_permissions_snapshot()
        disabled = [item for item in snapshot["permissions"] if item["effective_status"] == "disabled"]
        if not disabled:
            reply = "No permissions are fully disabled right now. Some capabilities may still be limited, planned, or unavailable."
        else:
            lines = [f"{len(disabled)} permission(s) are currently disabled:"]
            for item in disabled[:6]:
                lines.append(f"- {item['name']}: {item['description']}")
            reply = "\n".join(lines)
        return self._make_chat_result(
            reply=reply,
            intent="disabled_permissions_summary",
            source="permissions",
            source_label="Permissions & Access",
            context={
                "disabled_permissions": disabled[:10],
                "permission_key": disabled[0]["key"] if len(disabled) == 1 else None,
                "counts": snapshot["summary"]["counts"],
            }
        )

    def _handle_access_overview_command(self):
        snapshot = self.get_permissions_snapshot()
        active = [item for item in snapshot["permissions"] if item["effective_status"] == "active"]
        limited = [item for item in snapshot["permissions"] if item["effective_status"] == "limited"]
        lines = [
            f"Axis currently has {len(active)} active permission(s), {len(limited)} limited capability slot(s), and {snapshot['summary']['counts'].get('disabled', 0)} disabled permission(s)."
        ]
        if active:
            lines.append("Active access:")
            for item in active[:6]:
                lines.append(f"- {item['name']} ({item['risk_level']} risk)")
        if limited:
            lines.append("Limited or not-yet-fully-live surfaces:")
            for item in limited[:4]:
                lines.append(f"- {item['name']}: {item['availability_reason'] or item['description']}")
        return self._make_chat_result(
            reply="\n".join(lines),
            intent="access_overview",
            source="permissions",
            source_label="Permissions & Access",
            context={
                "active_permissions": active[:10],
                "limited_permissions": limited[:10],
                "counts": snapshot["summary"]["counts"],
            }
        )

    def _handle_profile_plan_command(self):
        snapshot = self.get_profiles_and_plans_snapshot()
        active_profile = snapshot["active_profile"]
        active_plan = snapshot["active_plan"]
        guidance = snapshot["upgrade_guidance"]
        reply = "\n".join([
            f"Axis is currently running as a {active_profile['profile_label']} workspace on the {active_plan['name']} plan.",
            active_plan["summary"],
            guidance["copy"],
        ])
        return self._make_chat_result(
            reply=reply,
            intent="profile_plan_summary",
            source="profiles_and_plans",
            source_label="Profiles & Plans",
            context={
                "active_profile": active_profile,
                "active_plan": active_plan,
                "upgrade_guidance": guidance,
            }
        )

    def _handle_skill_registry_command(self):
        snapshot = self.get_axis_hub_snapshot()
        live_skills = [item for item in snapshot["skills"] if item["state"] == "live"]
        disabled_skills = [item for item in snapshot["skills"] if item["availability"] == "disabled"]
        lines = [
            f"Axis Hub currently tracks {len(snapshot['skills'])} skill surface(s): {snapshot['summary'].get('live', 0)} live, {snapshot['summary'].get('partial', 0)} partial, {snapshot['summary'].get('planned', 0)} planned, and {snapshot['summary'].get('simulated', 0)} simulated.",
        ]
        if live_skills:
            lines.append("Live skills:")
            for item in live_skills[:4]:
                lines.append(f"- {item['name']}: {item['summary']}")
        if disabled_skills:
            lines.append("Trust-disabled skills:")
            for item in disabled_skills[:3]:
                lines.append(f"- {item['name']}")
        return self._make_chat_result(
            reply="\n".join(lines),
            intent="axis_hub_summary",
            source="axis_hub",
            source_label="Axis Hub",
            context={
                "skills": snapshot["skills"][:10],
                "summary": snapshot["summary"],
                "availability": snapshot["availability"],
            }
        )

    def _handle_goal_block_reason_command(self, lowered_text, dashboard_context=None):
        blocked = self.memory_engine.get_blocked_items(limit=8)
        selected = None
        context = self._coerce_dashboard_context(dashboard_context)
        focus_goal = context.get("focus_goal") or {}
        focus_goal_id = focus_goal.get("goal_id")
        if focus_goal_id:
            selected = next(
                (
                    item for item in blocked
                    if item.get("goal_id") and (
                        item["goal_id"] == focus_goal_id or item["goal_id"].startswith(focus_goal_id)
                    )
                ),
                None,
            )
        goal_id_match = re.search(r"\bgoal\s+([a-z0-9]{4,12})\b", lowered_text)
        if goal_id_match and not selected:
            token = goal_id_match.group(1)
            selected = next(
                (
                    item for item in blocked
                    if item.get("goal_id") and (
                        item["goal_id"] == token or item["goal_id"].startswith(token)
                    )
                ),
                None,
            )
        if not selected and focus_goal_id and (focus_goal.get("blocked_reason") or focus_goal.get("status") == "blocked"):
            summary = self.get_goal_summary(focus_goal_id)
            selected = {
                "item_type": "goal",
                "goal_id": focus_goal_id,
                "goal_title": focus_goal.get("title"),
                "blocked_reason": focus_goal.get("blocked_reason") or (summary or {}).get("blocked_reason"),
                "recommended_resolution": (summary or {}).get("next_step_guidance") or "Inspect the goal and resolve the dependency.",
            }
        if not selected:
            selected = next((item for item in blocked if item.get("item_type") == "goal"), None) or (blocked[0] if blocked else None)
        if not selected:
            reply = "I do not see any blocked goal in the current state."
            return self._make_chat_result(
                reply=reply,
                intent="goal_block_reason",
                source="control_blocked",
                source_label="Blocked goals list",
                context={"blocked": []}
            )

        permissions = self.get_permissions_snapshot()["permissions"]
        permission_hits = self._match_related_permissions(selected.get("blocked_reason"), permissions=permissions)
        selected_summary = self.get_goal_summary(selected.get("goal_id")) if selected.get("goal_id") else None

        goal_label = self._short_goal_label(selected.get("goal_title"), selected.get("goal_id"))
        lines = [
            f"{goal_label} is blocked because: {selected.get('blocked_reason') or 'No reason was recorded.'}",
            f"Recommended next move: {selected.get('recommended_resolution') or 'Inspect the goal and resolve the dependency.'}",
        ]
        pending_approvals = len((selected_summary or {}).get("waiting_approvals") or [])
        if pending_approvals:
            lines.append(f"There are also {pending_approvals} approval item(s) linked to this goal right now.")
        if permission_hits:
            lines.append("Related disabled or limited permissions:")
            for item in permission_hits[:3]:
                lines.append(f"- {item['name']}: {item['effective_status']}")
        return self._make_chat_result(
            reply="\n".join(lines),
            intent="goal_block_reason",
            source="control_blocked",
            source_label="Blocked goals list",
            context={
                "blocked_item": selected,
                "goal_summary": selected_summary,
                "related_permissions": permission_hits[:5],
            }
        )

    def _build_grounded_fallback_response(self, user_message):
        snapshot = self.get_live_control_snapshot(approvals_limit=3, blocked_limit=3, results_limit=3, events_limit=3, goals_limit=3, rec_limit=3)
        counts = snapshot["counts"]
        approvals_count = self.memory_engine.count_pending_actions(status='actionable')
        blocked_count = counts.get('goals_blocked', 0)
        results_count = self.memory_engine.count_recent_results()
        recommendation = snapshot["recommendations"][0]["recommended_action"] if snapshot["recommendations"] else "Add a new goal to get started"
        reply = (
            f"I could not confidently route '{user_message}' to a specific safe Axis workspace command. "
            f"Live state right now: {counts.get('goals_active', 0)} active goal(s), {approvals_count} actionable approval item(s), "
            f"{blocked_count} blocked item(s), and {results_count} recent result artifact(s). "
            f"Best next action from the current system state: {recommendation}. "
            "You can ask me to summarize approvals, blocked goals, system status, recent changes, results, or create a goal."
        )
        return self._make_chat_result(
            reply=reply,
            intent="grounded_fallback",
            source="live_state_fallback",
            source_label="Grounded live-state fallback",
            context={
                "counts": counts,
                "approvals_count": approvals_count,
                "blocked_count": blocked_count,
                "results_count": results_count,
                "top_recommendation": recommendation
            }
        )

    def propose_action(self, action_type, payload, conversation_id="system"):
        """Create a pending action for human approval."""
        action_id = str(uuid.uuid4())[:8]
        self.memory_engine.create_pending_action(action_id, action_type, payload, created_by=conversation_id)
        self.logger.log(f"[BRAIN] Action proposed: {action_type} (ID: {action_id})", "INFO")
        return action_id

    def execute_pending_action(self, action_id):
        """Execute an approved action."""
        action = self.memory_engine.get_pending_action(action_id)
        if not action:
            return False, "Action not found"
        
        if action['status'] != 'approved':
            return False, f"Action status is {action['status']}, must be 'approved'"
        
        payload = json.loads(action['payload_json'])
        try:
            permission_key = self.permissions.action_permission_key(action['type'])
            if permission_key and not self.permissions.is_allowed(permission_key, runtime=self.get_permission_runtime()):
                reason = f"The action '{action['type']}' depends on {permission_key} being enabled."
                step = self.memory_engine.get_step_by_action_ref(action_id)
                goal_id = step.get("goal_id") if step else None
                goal = self.memory_engine.get_goal_record(goal_id) if goal_id else None
                block = self.permissions.build_permission_block(
                    permission_key,
                    reason,
                    goal_id=goal_id,
                    goal_title=goal.get("title") if goal else None,
                    action_label=action['type'],
                    source="pending_action_execute",
                )
                self.memory_engine.update_action_status(action_id, 'failed', notes=block["message"])
                return False, block["message"]

            if action['type'] == 'gmail_send_draft':
                if not GOOGLE_AVAILABLE or not self.gmail:
                    return False, "Gmail integrations are not installed or available"
                # Check kill-switch
                send_enabled = self.config.get('google', {}).get('gmail', {}).get('send_enabled', False)
                if not send_enabled:
                    return False, "Gmail send is disabled in configuration (google.gmail.send_enabled: false)"
                
                res = self.gmail.send_draft(payload['draft_id'])
                notes = f"Sent: {res.get('id')}"
            elif action['type'] == 'calendar_create_event':
                if not GOOGLE_AVAILABLE or not self.calendar:
                    return False, "Calendar integrations are not installed or available"
                res = self.calendar.create_event(
                    title=payload['title'],
                    start_time=payload['start'],
                    end_time=payload.get('end'),
                    description=payload.get('description')
                )
                notes = f"Created: {res.get('id')}"
            elif action['type'] in ('manual.review.complete', 'chat.review.complete'):
                notes = payload.get('description') or payload.get('title') or "Owner-reviewed step marked complete"
                self.memory_engine.update_action_status(action_id, 'executed', notes=notes)
                return True, notes
            elif action['type'] == 'web.plan.execute':
                # No Google needed here, but we check web_automation capability
                res = self.web_automation.run_plan(payload)
                session_id = res.get('session_id')
                if res.get('status') == 'success':
                    notes = f"Web plan executed. Session: {session_id}"
                    status = 'executed'
                elif res.get('status') == 'blocked':
                    notes = f"Blocked: {res.get('reason')} - {res.get('evidence')}"
                    status = 'failed'
                else:
                    notes = f"Error: {res.get('error')}"
                    status = 'failed'
                
                self.memory_engine.update_action_status(action_id, status, notes=notes, result_ref=session_id)
                return res.get('status') == 'success', notes
            else:
                return False, f"Unknown action type: {action['type']}"
            
            self.memory_engine.update_action_status(action_id, 'executed', notes=notes)
            return True, notes
        except Exception as e:
            self.memory_engine.update_action_status(action_id, 'failed', notes=str(e))
            return False, str(e)

    def get_inbox_insights(self, limit=10):
        """Summarize and classify recent emails."""
        if not self.inbox_insight or not self.gmail:
            return {"error": "Gmail integration not available"}
        
        messages = self.gmail.list_messages(limit=limit)
        return self.inbox_insight.analyze_inbox(messages)

    def draft_gmail_reply(self, message_id, tone="professional", instructions=None):
        """Generate a reply draft and queue for approval."""
        if not self.gmail:
            return {"error": "Gmail integration not available"}
        
        # 1. Fetch original message (safe)
        original = self.gmail.get_message(message_id, body_limit=2000)
        
        # 2. LLM Generate Reply
        prompt = f"""
Draft a {tone} email reply to the following message.
Original From: {original.get('from')}
Original Subject: {original.get('subject')}
Original Body: {original.get('body')}

Instructions: {instructions or 'Review the email and reply appropriately.'}

Return ONLY the reply body text.
"""
        reply_text = self.brain.think(prompt)
        
        # 3. Create Draft in Gmail
        draft = self.gmail.create_draft(
            to=original.get('from'),
            subject=f"RE: {original.get('subject')}",
            body=reply_text
        )
        
        # 4. Queue Action for Sending
        payload = {
            "draft_id": draft['id'],
            "to": original.get('from'),
            "subject": f"RE: {original.get('subject')}",
            "reply_text": reply_text
        }
        action_id = self.propose_action('gmail_send_draft', payload)
        
        return {
            "draft_id": draft['id'],
            "action_id": action_id,
            "reply_text": reply_text
        }
    
    def _on_goal_event(self, event_type, goal):
        """
        Callback for goal events to trigger notifications.
        
        Args:
            event_type (str): 'created', 'completed', 'failed'
            goal (dict): Goal data
        """
        goal_id = goal.get('id')
        description = goal.get('objective', goal.get('description', 'Unknown'))
        priority = goal.get('priority', 'normal')
        
        # Normalize priority
        is_high = priority in [2, 3, 'high', 'critical']
        is_critical = priority in [3, 'critical']
        
        if event_type == 'created' and is_high:
            # High/Critical priority notification
            priority_label = 'CRITICAL' if is_critical else 'HIGH'
            self.notifications.notify(
                goal_id=goal_id,
                title=f"New {priority_label} Priority Goal",
                message=f"{description} (ID: {goal_id})",
                urgency="critical" if is_critical else "normal"
            )
        
        elif event_type == 'completed':
            self.notifications.notify(
                goal_id=goal_id,
                title="Goal Completed",
                message=f"{description} (ID: {goal_id})",
                urgency="normal"
            )
        
        elif event_type == 'failed':
            self.notifications.notify(
                goal_id=goal_id,
                title="Goal Failed",
                message=f"{description} (ID: {goal_id})",
                urgency="critical"
            )

    # ── Phase 7.1 Goal Engine forwarders ──────────────────────────────────────

    def reconcile_goal(self, goal_id):
        """Reconcile step statuses against their pending action outcomes."""
        return self.goal_engine.reconcile_goal(goal_id)

    def resume_goal(self, goal_id):
        """Reconcile, then continue advancing the goal if safe."""
        return self.goal_engine.resume_goal(goal_id, brain=self)

    def get_goal_summary(self, goal_id):
        """Return the rich Phase 7.1 goal summary dict."""
        summary = self.goal_engine.summarize_goal(goal_id)
        if not summary:
            return None
        context = self.goal_engine.get_goal_context(goal_id)
        dependencies = self.permissions.describe_goal_dependencies(
            context,
            runtime=self.get_permission_runtime(),
        )
        summary["permission_dependencies"] = dependencies
        summary["controls"] = {
            "can_plan": summary["status"] == "draft",
            "can_edit": summary["status"] not in ("completed", "failed"),
            "can_pause": summary["status"] in ("planned", "active", "awaiting_approval"),
            "can_resume": summary.get("can_resume", False),
            "can_stop": summary["status"] not in ("completed", "failed", "stopped"),
            "can_replan": summary["status"] not in ("completed", "failed"),
            "can_reconcile": summary["status"] in ("awaiting_approval", "blocked", "failed", "active", "planned", "paused"),
        }
        blocked_dependencies = [item for item in dependencies if item["effective_status"] != "active"]
        summary["blocked_dependencies"] = blocked_dependencies
        summary["permission_dependency_summary"] = (
            f"{len(blocked_dependencies)} permission blocker(s) detected"
            if blocked_dependencies else "No permission blockers detected"
        )
        summary["profile_plan_summary"] = self._goal_profile_plan_summary(context, dependencies)
        summary["relevant_skills"] = self._goal_skill_matches(context)
        return summary

    def get_next_recommended_action(self, goal_id):
        """Shorthand for recommended next action from the goal summary."""
        summary = self.goal_engine.summarize_goal(goal_id)
        return summary.get('recommended_next_action') if summary else None

    def think(self, user_input):
        """
        Process user input and generate a response.
        Wrapper for get_response to maintain backward compatibility if needed.
        """
        return self.get_response(user_input)

    def get_response(self, user_input):
        """
        Main method to get a response from the 'LLM'.
        Currently uses mock logic.
        
        Args:
            user_input (str): The user's message.
            
        Returns:
            str: The AI's response.
        """
        # 1. Save user input to memory
        self.memory.add_context("user", user_input)

        # 2. Generate Response (legacy deterministic compatibility logic)
        response = ""
        user_input_lower = user_input.lower()
        # Retrieve context for context-aware responses
        context = self.memory.get_context()
        if True:
            if "add a goal:" in user_input_lower:
                description_part = user_input.split(":", 1)[1].strip()
                priority = 1
                tags = []
                
                # Parse Priority
                if "high priority" in description_part.lower():
                    priority = 2
                    description_part = description_part.replace("high priority", "").strip()
                elif "critical" in description_part.lower():
                    priority = 3
                    description_part = description_part.replace("critical", "").strip()

                # Parse Tags: "Goal description tags: t1, t2"
                if "tags:" in description_part.lower():
                    parts = description_part.lower().split("tags:")
                    description = parts[0].strip()
                    tag_str = parts[1].strip()
                    tags = [t.strip() for t in tag_str.split(",")]
                else:
                    description = description_part

                goal = self.goal_engine.create_goal(description, priority=priority)
                
                # Phase 7.2 Auto-plan
                plan_result = self.goal_engine.plan_goal(goal['id'], brain=self)
                
                p_label = " (Normal)"
                if priority == 2: p_label = " (High)"
                if priority == 3: p_label = " (Critical)"

                response = (
                    f"Goal added: '{description}' (ID: {goal['id']}){p_label}.\n"
                    f"I have generated a multi-step plan using the {plan_result.get('planner_type')} planner.\n"
                    f"Steps: {plan_result.get('steps_count')}"
                )
                if plan_result.get('planner_warnings'):
                    response += f"\nNote: {', '.join(plan_result['planner_warnings'])}"
            
            elif "learn that" in user_input_lower:
                # "Jarvis, learn that [key] is [value]"
                try:
                    content = user_input.split("that", 1)[1].strip()
                    if " is " in content:
                        parts = content.split(" is ", 1)
                        key = parts[0].strip()
                        value = parts[1].strip()
                        self.long_term_memory.save(key, value)
                        response = f"I have learned that '{key}' is '{value}'."
                    else:
                        response = "Please use the format: 'Learn that [thing] is [value]'."
                except Exception:
                    response = "I couldn't understand what to learn. Try 'Learn that X is Y'."
            
            elif "list my goals" in user_input_lower:
                goals = self.goal_engine.list_goals()
                if not goals:
                    response = "You have no active goals."
                else:
                    response = "Current Goals:\n"
                    for g in goals:
                        response += f"- [{g['id']}] {g['description']} ({g['status']})\n"

            elif "show steps for goal" in user_input_lower:
                try:
                    # Extract ID (very precise parsing for mock)
                    parts = user_input_lower.split("goal")
                    goal_id = int(parts[-1].strip())
                    goal = self.goal_engine.get_goal_context(goal_id)
                    if goal:
                        steps_str = "\n".join([f"  {i+1}. {s}" for i, s in enumerate(goal['steps'])])
                        response = f"Steps for Goal {goal_id} ('{goal['description']}'):\n{steps_str}"
                    else:
                        response = f"Goal {goal_id} not found."
                except ValueError:
                    response = "Please specify a valid goal ID."

            elif "run goal" in user_input_lower:
                try:
                    mode = 'mock'
                    if "real mode" in user_input_lower:
                        mode = 'real'
                    
                    parts = user_input_lower.split("goal")
                    # Clean up string
                    remainder = parts[-1].replace("in", "").replace("autonomous", "").replace("mode", "").replace("real", "").strip()
                    if not remainder: # Handle edge case where replace removes everything
                         # Regex would be better but keeping simple:
                         # try to find first digit
                         import re
                         match = re.search(r'\d+', parts[-1])
                         if match:
                             remainder = match.group()
                    
                    goal_id = int(remainder)
                    
                    response = self.autonomy.run_goal(goal_id, mode=mode)
                except ValueError:
                    response = "Please specify a valid goal ID for execution."

            elif "complete goal" in user_input_lower:
                try:
                    parts = user_input_lower.split("goal")
                    goal_id = int(parts[-1].strip())
                    goal = self.goal_engine.complete_goal(goal_id)
                    if goal:
                        response = f"Goal {goal_id} marked as completed!"
                    else:
                        response = f"Goal {goal_id} not found."
                except ValueError:
                    response = "Please specify a valid goal ID."
            
            # --- Simulation Commands ---
            elif "simulate creating file" in user_input_lower:
                filename = user_input.split("file", 1)[1].strip()
                response = self.system_tool.create_file(filename)
                
            elif "simulate opening url" in user_input_lower:
                url = user_input.split("url", 1)[1].strip()
                response = self.web_tool.open_url(url)
                
            elif "simulate sending message to" in user_input_lower:
                # Format: "Simulate sending message to [number]: [message]"
                try:
                    parts = user_input.split("to", 1)[1].split(":", 1)
                    number = parts[0].strip()
                    msg = parts[1].strip()
                    response = self.mobile_tool.send_message(number, msg)
                except IndexError:
                    response = "Format error. Use: 'Simulate sending message to [number]: [message]'"

            # --- Long Term Memory Commands ---
            elif "remember this permanently:" in user_input_lower:
                data = user_input.split(":", 1)[1].strip()
                # Simple key generation (timestamp or incremental)
                # For mock, just use 'last_note' or simple key
                key = f"note_{len(self.long_term_memory.get_all()) + 1}"
                response = self.long_term_memory.save(key, data)
                
            elif "show my saved data" in user_input_lower:
                data = self.long_term_memory.get_all()
                if not data:
                    response = "No permanently saved data found."
                else:
                    response = "Saved Data:\n" + "\n".join([f"{k}: {v}" for k, v in data.items()])

            elif "hello" in user_input_lower or "hi" in user_input_lower:
                response = "Hello! I am Axis. I am ready to assist you."
            elif "help" in user_input_lower:
                response = "I can help you with tasks, planning, and information. Just ask!"
            elif "time" in user_input_lower:
                from datetime import datetime
                response = f"The current time is {datetime.now().strftime('%H:%M')}."
            elif "remember" in user_input_lower:
                 # Simple context test
                if len(context) > 1:
                    last_user_msg = [m for m in context if m['role'] == 'user'][-2]['content'] # Get strictly previous user msg
                    response = f"I remember you just said: '{last_user_msg}'"
                else:
                    response = "I don't have much memory yet."
            elif "exit" in user_input_lower or "quit" in user_input_lower:
                response = "Goodbye! Shutting down systems."
            else:
                response = f"I heard you say: '{user_input}'. This compatibility path is deterministic and intentionally limited."

        # TODO: Legacy compatibility path retained for older integrations.

        # 3. Save AI response to memory
        self.memory.add_context("ai", response)
        
        return response

    # ── Phase 7.3 Control Plane Logic ─────────────────────────────────────────

    def get_recommended_next_actions(self, limit=5):
        """
        Derive human-readable next steps from current system state.
        Uses deterministic rules based on Database metrics.
        """
        recommendations = []
        
        # 1. Check for pending approvals
        pending = self.memory_engine.get_pending_approvals_with_linkage(limit=3)
        for p in pending:
            action_id = p['action_id'][:8]
            if p['goal_id']:
                goal_id = p['goal_id'][:8]
                recommendations.append({
                    "goal_id": p['goal_id'],
                    "goal_title": p['goal_title'] or f"Goal {goal_id}",
                    "recommended_action": f"Approve pending {p['action_type']} action ({action_id})"
                })
            else:
                recommendations.append({
                    "goal_id": None,
                    "goal_title": "Approval queue",
                    "recommended_action": f"Approve pending {p['action_type']} action ({action_id})"
                })

        permission_requests = self.memory_engine.list_permission_requests(status='pending', limit=3)
        for req in permission_requests:
            recommendations.append({
                "goal_id": req.get("goal_id"),
                "goal_title": req.get("goal_title") or "Permissions & Access",
                "recommended_action": f"Review permission request for {req.get('title') or req.get('permission_key')}"
            })
                
        # 2. Check for blocked items
        blocked = self.memory_engine.get_blocked_items(limit=2)
        for b in blocked:
            if b['item_type'] == 'goal':
                goal_id = b['goal_id'][:8]
                recommendations.append({
                    "goal_id": b['goal_id'],
                    "goal_title": b.get('goal_title') or f"Goal {goal_id}",
                    "recommended_action": f"Inspect blocked goal ({goal_id}): {b['blocked_reason']}"
                })
            elif b['item_type'] == 'step':
                goal_id = b['goal_id'][:8]
                step_id = b['step_id'][:8]
                recommendations.append({
                    "goal_id": b['goal_id'],
                    "goal_title": b.get('goal_title') or f"Goal {goal_id}",
                    "recommended_action": f"Inspect blocked step ({step_id}) in goal ({goal_id}): {b['blocked_reason']}"
                })

        paused_goals = [goal for goal in self.goal_engine.list_goals() if goal.get("status") == "paused"][:2]
        for goal in paused_goals:
            recommendations.append({
                "goal_id": goal["id"],
                "goal_title": goal.get("title") or f"Goal {goal['id'][:8]}",
                "recommended_action": "Resume or stop the paused goal after reviewing its dependencies"
            })

        # 3. Check for recently completed or failed goals
        try:
            from jarvis_ai.db.supabase_client import get_supabase
            res = get_supabase().table("goal_events").select("goal_id, to_status").in_("to_status", ["completed", "failed"]).order("created_at", desc=True).limit(3).execute()
            if res.data:
                rows = res.data
            for r in rows:
                if r['to_status'] == 'completed':
                    recommendations.append({
                        "goal_id": r['goal_id'],
                        "goal_title": f"Goal {r['goal_id'][:8]}",
                        "recommended_action": f"Review results for completed goal ({r['goal_id'][:8]})"
                    })
                elif r['to_status'] == 'failed':
                    recommendations.append({
                        "goal_id": r['goal_id'],
                        "goal_title": f"Goal {r['goal_id'][:8]}",
                        "recommended_action": f"Review and replan failed goal ({r['goal_id'][:8]})"
                    })
        except Exception:
            pass
                    
        # 4. Fallback default
        if not recommendations:
            recommendations.append({
                "goal_id": None,
                "goal_title": "System",
                "recommended_action": "Add a new goal to get started"
            })

        # Deduplicate and limit
        seen = set()
        final_recs = []
        for r in recommendations:
            dedupe_key = (r.get("goal_id"), r.get("recommended_action"))
            if dedupe_key not in seen:
                seen.add(dedupe_key)
                final_recs.append(r)
            if len(final_recs) >= limit:
                break
                
        return final_recs
