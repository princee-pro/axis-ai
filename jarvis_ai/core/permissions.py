"""
Permission model and capability guide metadata for the Jarvis trust center.
"""

from __future__ import annotations

import json
from copy import deepcopy


MOBILE_UA_MARKERS = (
    "android",
    "iphone",
    "ipad",
    "mobile",
    "windows phone",
)


PERMISSION_CATALOG = [
    {
        "key": "dashboard.access",
        "group": "Control Plane",
        "name": "Dashboard access",
        "description": "Allows authenticated sessions to open the operator dashboard and fetch live control-plane summaries.",
        "default_state": "enabled",
        "risk_level": "low",
        "availability": "live",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
    {
        "key": "goals.view",
        "group": "Goals & Execution",
        "name": "Goal visibility",
        "description": "Allows Jarvis sessions to inspect the goal queue, goal detail, and execution history.",
        "default_state": "enabled",
        "risk_level": "low",
        "availability": "live",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
    {
        "key": "goals.manage",
        "group": "Goals & Execution",
        "name": "Goal management",
        "description": "Allows new goals to be created from the dashboard or routed commands.",
        "default_state": "enabled",
        "risk_level": "medium",
        "availability": "live",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
    {
        "key": "goals.edit",
        "group": "Goals & Execution",
        "name": "Goal editing",
        "description": "Allows owners to change goal title, objective, and priority after creation.",
        "default_state": "enabled",
        "risk_level": "medium",
        "availability": "live",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
    {
        "key": "goals.execute",
        "group": "Goals & Execution",
        "name": "Goal execution",
        "description": "Allows Jarvis to plan, advance, and continue real goal steps that are already inside the governed execution loop.",
        "default_state": "enabled",
        "risk_level": "high",
        "availability": "live",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
    {
        "key": "goals.control",
        "group": "Goals & Execution",
        "name": "Pause / stop / resume control",
        "description": "Allows owners to pause, resume, stop, reconcile, and replan in-flight goals.",
        "default_state": "enabled",
        "risk_level": "high",
        "availability": "live",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
    {
        "key": "approvals.manage",
        "group": "Goals & Execution",
        "name": "Approvals management",
        "description": "Allows approval queues to be reviewed, approved, denied, and executed within the existing safety model.",
        "default_state": "enabled",
        "risk_level": "high",
        "availability": "live",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
    {
        "key": "voice.input",
        "group": "Voice & Interaction",
        "name": "Voice input",
        "description": "Allows microphone or transcript input to route requests through the voice surface.",
        "default_state": "enabled",
        "risk_level": "medium",
        "availability": "dynamic_voice",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
    {
        "key": "voice.output",
        "group": "Voice & Interaction",
        "name": "Voice output",
        "description": "Allows Jarvis to prepare spoken follow-up output for voice requests.",
        "default_state": "enabled",
        "risk_level": "low",
        "availability": "dynamic_voice",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
    {
        "key": "browser.web_access",
        "group": "Web & Browser",
        "name": "Browser / web access",
        "description": "Allows Jarvis to use browser-backed research and grounded web routes that stay inside the local safety boundary.",
        "default_state": "enabled",
        "risk_level": "medium",
        "availability": "dynamic_web",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
    {
        "key": "browser.web_automation",
        "group": "Web & Browser",
        "name": "Web automation",
        "description": "Allows governed web execution plans that still stop on sensitive events like login, payment, or CAPTCHA prompts.",
        "default_state": "enabled",
        "risk_level": "high",
        "availability": "dynamic_web",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
    {
        "key": "files.read",
        "group": "Files & Local System",
        "name": "File read access",
        "description": "Represents future or partial ability to inspect local files from governed execution flows.",
        "default_state": "limited",
        "risk_level": "medium",
        "availability": "limited",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
    {
        "key": "files.write",
        "group": "Files & Local System",
        "name": "File write / save access",
        "description": "Represents future or limited ability to save files locally. This build keeps it constrained and non-default.",
        "default_state": "disabled",
        "risk_level": "high",
        "availability": "limited",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
    {
        "key": "files.local_folders",
        "group": "Files & Local System",
        "name": "Local folder access",
        "description": "Represents scoped local folder access for future desktop execution realism.",
        "default_state": "limited",
        "risk_level": "high",
        "availability": "limited",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
    {
        "key": "clipboard.access",
        "group": "Voice & Interaction",
        "name": "Clipboard access",
        "description": "Clipboard inspection or writes are not currently exposed as a live Jarvis capability.",
        "default_state": "disabled",
        "risk_level": "high",
        "availability": "planned",
        "grant_policy": "desktop_owner_only",
        "toggleable": False,
    },
    {
        "key": "notifications.desktop",
        "group": "Voice & Interaction",
        "name": "Notifications",
        "description": "Allows Jarvis to surface owner-facing notifications when notable goal events happen.",
        "default_state": "enabled",
        "risk_level": "low",
        "availability": "dynamic_notifications",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
    {
        "key": "integrations.gmail",
        "group": "Integrations",
        "name": "Gmail access",
        "description": "Allows governed Gmail read and draft flows. The capability still follows approval rules and can be unavailable when auth is degraded.",
        "default_state": "enabled",
        "risk_level": "high",
        "availability": "dynamic_gmail",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
    {
        "key": "integrations.calendar",
        "group": "Integrations",
        "name": "Calendar access",
        "description": "Allows governed calendar proposal and event creation flows when the integration is healthy.",
        "default_state": "enabled",
        "risk_level": "high",
        "availability": "dynamic_calendar",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
    {
        "key": "browser.chrome_control",
        "group": "Web & Browser",
        "name": "Chrome / browser control",
        "description": "Direct Chrome control is roadmap-only in this build and is not available for live execution yet.",
        "default_state": "disabled",
        "risk_level": "high",
        "availability": "planned",
        "grant_policy": "desktop_owner_only",
        "toggleable": False,
    },
    {
        "key": "system.keyboard_mouse",
        "group": "Files & Local System",
        "name": "Keyboard / mouse simulation",
        "description": "Direct keyboard or mouse simulation remains intentionally unavailable in the current release.",
        "default_state": "disabled",
        "risk_level": "critical",
        "availability": "planned",
        "grant_policy": "desktop_owner_only",
        "toggleable": False,
    },
    {
        "key": "transfers.downloads",
        "group": "Web & Browser",
        "name": "Download handling",
        "description": "Download handling is limited and only supported through tightly governed future surfaces.",
        "default_state": "limited",
        "risk_level": "medium",
        "availability": "limited",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
    {
        "key": "transfers.uploads",
        "group": "Web & Browser",
        "name": "Upload handling",
        "description": "Upload handling is limited and remains off the main execution path for now.",
        "default_state": "limited",
        "risk_level": "high",
        "availability": "limited",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
    {
        "key": "integrations.external",
        "group": "Integrations",
        "name": "External integrations",
        "description": "Represents future third-party integrations beyond the current local and Google-adjacent surfaces.",
        "default_state": "limited",
        "risk_level": "high",
        "availability": "experimental",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
    {
        "key": "safety.high_risk",
        "group": "Safety & Experimental",
        "name": "Dangerous / high-risk actions",
        "description": "A hard owner-controlled gate for any future risky execution surfaces. It stays off by default and should be treated cautiously.",
        "default_state": "disabled",
        "risk_level": "critical",
        "availability": "limited",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
    {
        "key": "experimental.capabilities",
        "group": "Safety & Experimental",
        "name": "Experimental capabilities",
        "description": "Allows experimental surfaces to appear in guide data or future execution paths without making them silently active.",
        "default_state": "limited",
        "risk_level": "medium",
        "availability": "experimental",
        "grant_policy": "desktop_owner_only",
        "toggleable": True,
    },
]


CAPABILITY_GUIDE = [
    {
        "key": "dashboard",
        "group": "Current System",
        "name": "Dashboard control plane",
        "summary": "The dashboard is the main owner console for goals, approvals, blocked items, results, permissions, and runtime diagnostics.",
        "details": "It reads live data from the local Jarvis bridge and keeps the UI grounded in the current database state instead of generic mock summaries.",
        "realism": "live",
        "owner_controls": "Use the Overview, Goals, Approvals, Blocked, Results, Permissions & Access, and Capabilities & Guide sections to inspect and steer the system.",
    },
    {
        "key": "goals",
        "group": "Current System",
        "name": "Goals and execution queue",
        "summary": "Goals are created as durable records, planned into steps, and then advanced through governed execution states.",
        "details": "Creating a goal writes to SQLite immediately. Planning adds structured steps. Advancing a goal can queue approvals, block on dependencies, or complete steps.",
        "realism": "live",
        "owner_controls": "You can inspect steps, edit goals, pause, resume, stop, and replan from the goal workspace.",
    },
    {
        "key": "approvals",
        "group": "Current System",
        "name": "Approvals",
        "summary": "Approvals remain the enforcement point for sensitive or owner-review actions before they are executed.",
        "details": "Approvals are backed by persisted pending actions. Items can move from pending to approved, denied, or executed while preserving linkage to the goal and step.",
        "realism": "live",
        "owner_controls": "Approve, deny, or execute from the queue. Jarvis uses these items for recommendations and routing.",
    },
    {
        "key": "voice",
        "group": "Current System",
        "name": "Voice and command routing",
        "summary": "Voice and text fallback route into the same grounded command layer used by the dashboard.",
        "details": "The transcript path is real and grounded in control-plane data, but STT or TTS providers may still be mocked depending on the runtime configuration.",
        "realism": "mocked",
        "owner_controls": "Use push-to-talk or text fallback. The route should show intent, source, and grounded system context after each request.",
    },
    {
        "key": "web_automation",
        "group": "Current System",
        "name": "Web automation",
        "summary": "Web automation is governed, approval-aware, and intentionally conservative.",
        "details": "Execution is routed through a safety-focused engine that should stop on sensitive browser conditions instead of pushing through them.",
        "realism": "experimental",
        "owner_controls": "Enable or disable browser permissions from Permissions & Access and review any approval items before execution.",
    },
    {
        "key": "permissions",
        "group": "Current System",
        "name": "Permissions and trust center",
        "summary": "The trust center explains what Jarvis can access, what is blocked, and which changes require desktop-owner approval.",
        "details": "Permissions are persisted and enforced in live backend behavior. When Jarvis cannot continue, it can create a permission request with the exact reason.",
        "realism": "live",
        "owner_controls": "Review permission state, risk, default posture, session limitations, and pending permission requests in one place.",
    },
    {
        "key": "google",
        "group": "Current System",
        "name": "Google integrations",
        "summary": "Google surfaces are supported conceptually but can be degraded or unavailable when auth is missing.",
        "details": "Jarvis is designed to boot in degraded mode without breaking the rest of the system. Gmail and Calendar stay behind approvals when enabled.",
        "realism": "degraded",
        "owner_controls": "The guide shows health state, but this pass intentionally keeps Google work secondary to core trust and execution controls.",
    },
    {
        "key": "execution_realism",
        "group": "Current System",
        "name": "Execution realism controls",
        "summary": "Execution realism focuses on visible state, inspectability, and owner control rather than hidden autonomy.",
        "details": "Paused, stopped, blocked, awaiting approval, and active states should now be easier to interpret from the goal detail surface.",
        "realism": "partially_live",
        "owner_controls": "Use edit, pause, resume, stop, replan, and dependency inspect controls instead of opaque background execution.",
    },
    {
        "key": "llm_integration",
        "group": "Current System",
        "name": "LLM Integration",
        "summary": "Axis connects to 4 real AI providers: Groq, OpenRouter, HuggingFace, and Anthropic.",
        "details": "All providers are live with automatic fallback chaining. If one provider fails, requests cascade through the chain until a model responds.",
        "realism": "live",
        "owner_controls": "Switch providers from Settings > AI Model without restarting the server.",
    },
    {
        "key": "available_models",
        "group": "Current System",
        "name": "Available Models",
        "summary": "10 models across free and pro tiers are available from the model selector.",
        "details": "Free models: Llama 3.3 70B, Mixtral 8x7B, Gemma 2 9B (Groq), Llama 3.1 8B, Mistral 7B, Gemma 3 4B (OpenRouter), Mistral 7B Instruct, DialoGPT Large (HuggingFace). Pro models: Claude Haiku, Claude Sonnet (Anthropic).",
        "realism": "live",
        "owner_controls": "Owner has unrestricted access to all models. Free plan users can access 8 free models.",
    },
    {
        "key": "model_selector",
        "group": "Current System",
        "name": "Model Selector",
        "summary": "Switch models live from the Settings page without any server restart.",
        "details": "Current model preference is persisted to Supabase. The status bar and assistant panel update immediately when a new model is selected.",
        "realism": "live",
        "owner_controls": "Navigate to Settings > AI Model to select a provider and model. Use the Test button to verify the active model.",
    },
    {
        "key": "chrome_control",
        "group": "Roadmap",
        "name": "Chrome / browser control",
        "summary": "Direct browser control is a future capability and is not available in this build.",
        "details": "It should remain clearly labeled as future work until there is a real, governed implementation behind it.",
        "realism": "planned",
        "owner_controls": "For now, rely on the existing governed web automation surfaces instead.",
    },
    {
        "key": "keyboard_mouse",
        "group": "Roadmap",
        "name": "Keyboard typing / system interaction",
        "summary": "Direct system interaction is intentionally unavailable and remains future work.",
        "details": "This stays outside the live path to keep deployment simple and avoid unsafe local automation.",
        "realism": "planned",
        "owner_controls": "Use the guide as a roadmap indicator only. There is no live execution route behind this item.",
    },
    {
        "key": "file_saving",
        "group": "Roadmap",
        "name": "File saving on the PC",
        "summary": "File read and write surfaces remain limited so the owner can understand the gap between current UI control and future desktop realism.",
        "details": "Permission entries expose current posture, but the product still treats broad file system access as a constrained capability.",
        "realism": "partially_live",
        "owner_controls": "Keep file writing disabled unless a future controlled workflow needs it.",
    },
    {
        "key": "device_control",
        "group": "Roadmap",
        "name": "Future device control",
        "summary": "Phone or companion-device control remains limited and should stay subordinate to desktop-owner controls.",
        "details": "This build keeps permission management desktop-first and avoids granting high-risk changes from mobile-class sessions.",
        "realism": "planned",
        "owner_controls": "Treat mobile sessions as a lighter companion surface, not the primary trust console.",
    },
]


GUIDE_WORKFLOWS = [
    {
        "key": "goal_lifecycle",
        "title": "What happens when a goal is created",
        "summary": "A new goal starts in draft, receives a structured plan, and then moves through active, awaiting approval, blocked, paused, stopped, or completed states.",
        "status": "live",
    },
    {
        "key": "planning",
        "title": "How planning and replan work",
        "summary": "Planning turns a goal into structured steps. Replan archives future work, resets the goal to draft, and generates a new plan without hiding prior history.",
        "status": "live",
    },
    {
        "key": "approvals_flow",
        "title": "How approvals work",
        "summary": "Sensitive work creates persisted approval items. Owners can approve, deny, or execute them, and the linked goal step reconciles from that outcome.",
        "status": "live",
    },
    {
        "key": "blocked_states",
        "title": "How blocked states happen",
        "summary": "A goal becomes blocked when a step fails, a safety gate triggers, or a required permission or integration is not available.",
        "status": "live",
    },
    {
        "key": "resume_reconcile",
        "title": "How resume and reconcile work",
        "summary": "Reconcile re-reads linked approvals and step outcomes. Resume uses that fresh state to continue only when the next step is allowed.",
        "status": "live",
    },
    {
        "key": "voice_routing",
        "title": "How voice routes into commands",
        "summary": "Voice or text fallback feeds the same grounded command router, which answers from real approvals, blocked items, results, readiness, and permissions.",
        "status": "partially_live",
    },
    {
        "key": "web_governance",
        "title": "How web automation is governed",
        "summary": "Web execution is permission-aware, approval-aware, and should stop on sensitive browser states instead of bypassing them.",
        "status": "experimental",
    },
    {
        "key": "permission_requests",
        "title": "How permission requests work",
        "summary": "When Jarvis hits a disabled dependency, it can create a permission request that names the blocked capability, why it is needed, and what goal depends on it.",
        "status": "live",
    },
]


STEP_PERMISSION_MAP = {
    "web": "browser.web_automation",
    "web_plan": "browser.web_automation",
    "gmail_draft": "integrations.gmail",
    "calendar_proposal": "integrations.calendar",
}


ACTION_PERMISSION_MAP = {
    "web.plan.execute": "browser.web_automation",
    "gmail_send_draft": "integrations.gmail",
    "calendar_create_event": "integrations.calendar",
}


class PermissionService:
    def __init__(self, config, memory_engine):
        self.config = config or {}
        self.memory_engine = memory_engine
        self._catalog = {entry["key"]: entry for entry in PERMISSION_CATALOG}

    def _load_overrides(self):
        raw = self.memory_engine.get_setting("permissions_state_v1", "{}")
        if not raw:
            return {}
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

    def _save_overrides(self, overrides):
        self.memory_engine.set_setting("permissions_state_v1", json.dumps(overrides, sort_keys=True))

    def get_session_class(self, auth_context=None, user_agent=""):
        ua = (user_agent or "").lower()
        is_mobile = any(marker in ua for marker in MOBILE_UA_MARKERS)
        if auth_context and auth_context.get("type") == "owner":
            return "mobile_owner" if is_mobile else "desktop_owner"
        if auth_context and auth_context.get("type") == "device":
            return "mobile_device" if is_mobile else "desktop_device"
        return "mobile_guest" if is_mobile else "desktop_guest"

    def can_manage_permissions(self, auth_context=None, user_agent=""):
        return bool(
            auth_context
            and auth_context.get("type") == "owner"
            and self.get_session_class(auth_context=auth_context, user_agent=user_agent) == "desktop_owner"
        )

    def _availability_state(self, entry, runtime):
        runtime = runtime or {}
        availability = entry.get("availability", "live")
        if availability == "planned":
            return "planned", "This capability is roadmap-only in the current build."
        if availability == "limited":
            return "limited", "This capability is intentionally constrained and not fully live yet."
        if availability == "experimental":
            return "limited", "This capability is experimental and should be treated cautiously."
        if availability == "dynamic_web":
            if runtime.get("web_automation_enabled", False):
                return "active", None
            return "unavailable", "Web automation is disabled in the current runtime."
        if availability == "dynamic_voice":
            if runtime.get("voice_enabled", False):
                return "active", None
            return "unavailable", "Voice is unavailable in the current runtime."
        if availability == "dynamic_notifications":
            if runtime.get("notifications_enabled", False):
                return "active", None
            return "unavailable", "Desktop notifications are unavailable in the current runtime."
        if availability == "dynamic_gmail":
            if runtime.get("google_gmail_available", False):
                return "active", None
            if runtime.get("google_enabled", False):
                return "unavailable", "Gmail is configured but currently degraded or unauthenticated."
            return "unavailable", "Gmail integration is disabled."
        if availability == "dynamic_calendar":
            if runtime.get("google_calendar_available", False):
                return "active", None
            if runtime.get("google_enabled", False):
                return "unavailable", "Calendar is configured but currently degraded or unauthenticated."
            return "unavailable", "Calendar integration is disabled."
        return "active", None

    def get_permission(self, permission_key, runtime=None, auth_context=None, user_agent=""):
        entry = self._catalog.get(permission_key)
        if not entry:
            return None

        overrides = self._load_overrides()
        current_state = overrides.get(permission_key, entry["default_state"])
        availability_state, availability_reason = self._availability_state(entry, runtime or {})

        effective_status = availability_state
        if availability_state not in ("planned", "unavailable"):
            if current_state == "disabled":
                effective_status = "disabled"
            elif current_state == "limited":
                effective_status = "limited"
            elif availability_state == "limited":
                effective_status = "limited"
            else:
                effective_status = "active"

        manageable = self.can_manage_permissions(auth_context=auth_context, user_agent=user_agent)
        if not entry.get("toggleable", True):
            manageable = False

        return {
            **deepcopy(entry),
            "current_state": current_state,
            "effective_status": effective_status,
            "available": effective_status == "active",
            "manageable": manageable,
            "session_class": self.get_session_class(auth_context=auth_context, user_agent=user_agent),
            "management_mode": "full" if manageable else "read_only",
            "availability_reason": availability_reason,
        }

    def list_permissions(self, runtime=None, auth_context=None, user_agent=""):
        return [
            self.get_permission(entry["key"], runtime=runtime, auth_context=auth_context, user_agent=user_agent)
            for entry in PERMISSION_CATALOG
        ]

    def summarize_permissions(self, runtime=None, auth_context=None, user_agent=""):
        counts = {
            "active": 0,
            "disabled": 0,
            "limited": 0,
            "planned": 0,
            "unavailable": 0,
            "high_risk_enabled": 0,
        }
        disabled = []
        active = []
        for item in self.list_permissions(runtime=runtime, auth_context=auth_context, user_agent=user_agent):
            counts[item["effective_status"]] = counts.get(item["effective_status"], 0) + 1
            if item["effective_status"] == "disabled":
                disabled.append(item["key"])
            if item["effective_status"] == "active":
                active.append(item["key"])
            if item["risk_level"] in ("high", "critical") and item["effective_status"] == "active":
                counts["high_risk_enabled"] += 1
        return {
            "counts": counts,
            "disabled_keys": disabled,
            "active_keys": active,
        }

    def is_allowed(self, permission_key, runtime=None):
        item = self.get_permission(permission_key, runtime=runtime)
        return bool(item and item["effective_status"] == "active")

    def set_permission_state(self, permission_key, state):
        if state not in ("enabled", "disabled", "limited"):
            raise ValueError("Invalid permission state")
        entry = self._catalog.get(permission_key)
        if not entry:
            raise KeyError(permission_key)
        if not entry.get("toggleable", True):
            raise ValueError("Permission is not toggleable in this build")
        overrides = self._load_overrides()
        overrides[permission_key] = state
        self._save_overrides(overrides)
        return self.get_permission(permission_key)

    def step_permission_key(self, step):
        if not step:
            return None
        return STEP_PERMISSION_MAP.get(step.get("capability_type"))

    def action_permission_key(self, action_type):
        return ACTION_PERMISSION_MAP.get(action_type)

    def describe_goal_dependencies(self, goal_context, runtime=None):
        permissions = {}
        steps = (goal_context or {}).get("steps", []) or []
        for step in steps:
            permission_key = self.step_permission_key(step)
            if not permission_key:
                continue
            current = permissions.setdefault(permission_key, {
                "permission_key": permission_key,
                "required_by": [],
            })
            current["required_by"].append({
                "step_id": step.get("id"),
                "title": step.get("title"),
                "status": step.get("status"),
                "capability_type": step.get("capability_type"),
            })

        output = []
        for permission_key, item in permissions.items():
            permission = self.get_permission(permission_key, runtime=runtime)
            output.append({
                **item,
                "name": permission["name"] if permission else permission_key,
                "effective_status": permission["effective_status"] if permission else "unknown",
                "risk_level": permission["risk_level"] if permission else "unknown",
                "description": permission["description"] if permission else None,
            })
        output.sort(key=lambda row: (row["effective_status"], row["name"]))
        return output

    def request_permission(
        self,
        permission_key,
        reason,
        *,
        goal_id=None,
        goal_title=None,
        action_label=None,
        source="system",
        requested_by="jarvis",
        requested_state="enabled",
        context=None,
    ):
        permission = self.get_permission(permission_key)
        if not permission or permission["effective_status"] == "active":
            return None
        return self.memory_engine.create_permission_request(
            permission_key=permission_key,
            title=permission["name"],
            reason=reason,
            goal_id=goal_id,
            goal_title=goal_title,
            action_label=action_label,
            source=source,
            requested_by=requested_by,
            requested_state=requested_state,
            context=context or {},
        )

    def build_permission_block(
        self,
        permission_key,
        reason,
        *,
        action_label=None,
        goal_id=None,
        goal_title=None,
        source="system",
        requested_by="jarvis",
    ):
        permission = self.get_permission(permission_key)
        request = self.request_permission(
            permission_key,
            reason,
            goal_id=goal_id,
            goal_title=goal_title,
            action_label=action_label,
            source=source,
            requested_by=requested_by,
            context={
                "permission_key": permission_key,
                "goal_id": goal_id,
                "goal_title": goal_title,
                "action_label": action_label,
            },
        )
        return {
            "error": "permission_blocked",
            "permission_key": permission_key,
            "permission_name": permission["name"] if permission else permission_key,
            "message": f"{permission['name'] if permission else permission_key} is currently {permission['effective_status'] if permission else 'disabled'}. {reason} Open Permissions & Access to review it.",
            "reason": reason,
            "permission_request": request,
        }

    def get_capabilities_guide(self, runtime=None):
        runtime = runtime or {}
        capabilities = deepcopy(CAPABILITY_GUIDE)
        voice_mode = "mocked"
        if runtime.get("voice_enabled"):
            stt = (runtime.get("voice_stt_provider") or "").lower()
            tts = (runtime.get("voice_tts_provider") or "").lower()
            if stt == "mock" and tts == "mock":
                voice_mode = "mocked"
            elif stt and tts and stt != "mock" and tts != "mock":
                voice_mode = "live"
            else:
                voice_mode = "partially_live"
        else:
            voice_mode = "degraded"

        google_mode = "degraded" if runtime.get("google_enabled", False) else "planned"
        if runtime.get("google_gmail_available") and runtime.get("google_calendar_available"):
            google_mode = "live"

        for item in capabilities:
            if item["key"] == "voice":
                item["realism"] = voice_mode
            elif item["key"] == "google":
                item["realism"] = google_mode
            elif item["key"] == "web_automation" and not runtime.get("web_automation_enabled", False):
                item["realism"] = "degraded"

        counts = {
            "live": 0,
            "partially_live": 0,
            "mocked": 0,
            "degraded": 0,
            "planned": 0,
            "experimental": 0,
        }
        for item in capabilities:
            counts[item["realism"]] = counts.get(item["realism"], 0) + 1

        return {
            "summary": counts,
            "capabilities": capabilities,
            "workflows": deepcopy(GUIDE_WORKFLOWS),
        }
