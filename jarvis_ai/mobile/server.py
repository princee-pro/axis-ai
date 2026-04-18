"""
Mobile Server Bridge â€” Phase 5.
Secure-by-default: local-only binding unless explicitly enabled.
Supports dual auth (owner token + device token) with RBAC.
"""
from dotenv import load_dotenv
load_dotenv(dotenv_path='D:\\Axis\\.env', override=True)

import http.server
import socketserver
import json
import threading
import sys
import os
import time
import secrets
import email.parser
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

_jarvis_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_project_root = os.path.dirname(_jarvis_root)
print("[SERVER] .env loaded from D:\\Axis\\.env (override=True).")

from jarvis_ai.core.version import APP_VERSION, DB_SCHEMA_VERSION
from jarvis_ai.db.supabase_client import ping_supabase
from jarvis_ai.core.brain import Brain

# â”€â”€â”€ Rate Limiter â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Simple in-memory per-IP counter for brute-force protection on public endpoints.
_RATE_LIMIT_WINDOW = 60   # seconds
_RATE_LIMIT_MAX    = 10   # max attempts per window per IP

_rate_limit_lock   = threading.Lock()
_rate_counters     = {}   # {ip: (count, window_start)}

def _check_rate_limit(ip):
    """Return True if the IP is within the allowed rate. False if throttled."""
    now = time.monotonic()
    with _rate_limit_lock:
        entry = _rate_counters.get(ip)
        if entry is None or (now - entry[1]) > _RATE_LIMIT_WINDOW:
            _rate_counters[ip] = (1, now)
            return True
        count, start = entry
        if count >= _RATE_LIMIT_MAX:
            return False
        _rate_counters[ip] = (count + 1, start)
        return True


# â”€â”€â”€ Request Handler â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class JarvisRequestHandler(http.server.BaseHTTPRequestHandler):
    brain           = None
    server_start_time = 0
    # Reverse-proxy config (injected by JarvisServer)
    _remote_enabled             = False
    _behind_reverse_proxy       = False
    _require_https_proto        = True
    _trusted_proxy_ips          = []

    # â”€â”€ Logging â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def log_message(self, format, *args):
        """Suppress default access log (we use audit log instead)."""
        pass

    # â”€â”€ Low-level helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

    def _send_json(self, data, status=200):
        try:
            self._set_headers(status)
            self.wfile.write(json.dumps(data, default=str).encode())
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return

    def _serve_static(self, path):
        """Serve files from jarvis_ai/ui/."""
        # Sanitize path to prevent traversal
        rel_path = path.lstrip('/')
        if not rel_path or rel_path in ('ui', 'dashboard', 'index.html'):
            rel_path = 'index.html'
        elif rel_path.startswith('ui/'):
            rel_path = rel_path[3:]
        elif rel_path.startswith('dashboard/'):
            rel_path = rel_path[10:]
            
        # Map to physical path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.abspath(os.path.join(current_dir, '..', 'ui'))
        safe_path = os.path.abspath(os.path.join(base_dir, rel_path))
        
        # Security check - normalized for Windows
        if not safe_path.lower().startswith(base_dir.lower()):
            self._send_json({"error": "Forbidden: Path escape detected"}, 403)
            return

        if not os.path.isfile(safe_path):
            # Try static/ prefix if not found and it's not index.html
            if not rel_path.startswith('static/') and rel_path != 'index.html':
                 alt_path = os.path.join(base_dir, 'static', rel_path)
                 if os.path.isfile(alt_path):
                     safe_path = alt_path
                 else:
                     self._send_json({"error": f"File not found: {rel_path}"}, 404)
                     return
            else:
                self._send_json({"error": f"File not found: {rel_path}"}, 404)
                return

        # Determine content type
        ext = os.path.splitext(safe_path)[1].lower()
        mime_map = {
            '.html': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon',
            '.json': 'application/json'
        }
        content_type = mime_map.get(ext, 'application/octet-stream')

        try:
            with open(safe_path, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-type', content_type)
            self.send_header('Content-length', len(content))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _get_client_ip(self):
        """Return real client IP, honouring X-Forwarded-For ONLY for trusted proxies."""
        direct_ip = self.client_address[0]
        if self._behind_reverse_proxy and self._trusted_proxy_ips:
            if direct_ip in self._trusted_proxy_ips:
                forwarded = self.headers.get('X-Forwarded-For', '').split(',')[0].strip()
                return forwarded if forwarded else direct_ip
        return direct_ip

    def _enforce_tls_proto(self):
        """If behind reverse proxy with HTTPS enforcement, reject non-HTTPS requests.
        Returns True if the request should be rejected."""
        if not (self._remote_enabled and self._behind_reverse_proxy and self._require_https_proto):
            return False  # not enforcing
        proto = self.headers.get('X-Forwarded-Proto', '')
        if proto.lower() != 'https':
            self._send_json({
                'error': 'HTTPS required. Request rejected (X-Forwarded-Proto is not https).'
            }, 400)
            return True
        return False

    # â”€â”€ Auth context â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _get_auth_context(self):
        """Identify if requester is Owner or a registered Device.
        Returns dict or None. NEVER logs secret values."""
        # Check Owner Token (env takes precedence over config file)
        owner_token = self.headers.get('X-Jarvis-Token')
        auth_method_used = 'X-Jarvis-Token'
        
        # Legacy fallback
        if not owner_token and self.headers.get('Authorization'):
            auth_header = self.headers.get('Authorization')
            if auth_header.startswith('Bearer '):
                owner_token = auth_header.split(' ')[1]
                auth_method_used = 'Authorization: Bearer (Deprecated)'
        
        secret = os.environ.get('JARVIS_SECRET_TOKEN')
        if not secret and self.brain and hasattr(self.brain, 'config'):
            secret = self.brain.config.get('security_token')

        if secret and owner_token:
            if secrets.compare_digest(owner_token, secret):
                return {"type": "owner", "id": None, "role": "admin", "auth_method": auth_method_used}

        # Check Device Token
        device_token = self.headers.get('X-Device-Token')
        if device_token:
            device = self.brain.memory_engine.authenticate_device_token(device_token)
            print(f"[DEBUG] Auth attempt: device_token={device_token[:4]}... found={bool(device)}")
            if device:
                return {"type": "device", "id": device['device_id'], "role": device['role'], "auth_method": "X-Device-Token"}

        print(f"[DEBUG] Auth failed for path: {self.path}")
        return None

    # â”€â”€ RBAC â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _check_permission(self, auth, required_role):
        """RBAC hierarchy: executor > operator > reader. Owner bypasses all."""
        if not auth:
            return False
        if auth['role'] == 'admin':
            return True
        roles = ['reader', 'operator', 'executor']
        if auth['role'] not in roles or required_role not in roles:
            return False
        return roles.index(auth['role']) >= roles.index(required_role)

    def _user_agent(self):
        return self.headers.get('User-Agent', '')

    def _permission_runtime(self):
        return self.brain.get_permission_runtime()

    def _session_class(self, auth):
        return self.brain.permissions.get_session_class(auth_context=auth, user_agent=self._user_agent())

    def _can_manage_permissions(self, auth):
        return self.brain.permissions.can_manage_permissions(auth_context=auth, user_agent=self._user_agent())

    def _can_manage_workspace_config(self, auth):
        return bool(auth and (auth.get('type') == 'owner' or self._check_permission(auth, 'admin')))

    def _permission_block_payload(self, auth, permission_key, reason, *, action_label=None, goal_id=None, goal_title=None, source="server"):
        payload = self.brain.permissions.build_permission_block(
            permission_key,
            reason,
            goal_id=goal_id,
            goal_title=goal_title,
            action_label=action_label,
            source=source,
        )
        payload["session_class"] = self._session_class(auth)
        payload["can_manage_permissions"] = self._can_manage_permissions(auth)
        return payload

    def _require_system_permission(self, auth, permission_key, reason, *, action_label=None, goal_id=None, goal_title=None, source="server"):
        if self.brain.permissions.is_allowed(permission_key, runtime=self._permission_runtime()):
            return True
        payload = self._permission_block_payload(
            auth,
            permission_key,
            reason,
            action_label=action_label,
            goal_id=goal_id,
            goal_title=goal_title,
            source=source,
        )
        self._log_request(auth, 403, error=f"Permission blocked: {permission_key}")
        self._send_json(payload, 403)
        return False

    def _linked_goal_context_for_action(self, action_id):
        step = self.brain.memory_engine.get_step_by_action_ref(action_id)
        if not step or not step.get("goal_id"):
            return None, None
        goal_id = step["goal_id"]
        self.brain.goal_engine.reconcile_goal(goal_id)
        return step, self.brain.get_goal_summary(goal_id)

    def _approval_action_snapshot(self, action_id):
        linked = self.brain.memory_engine.get_pending_approvals_with_linkage(
            limit=1,
            status='all',
            action_id=action_id,
        )
        if linked:
            return linked[0]
        action = self.brain.memory_engine.get_pending_action(action_id)
        if not action:
            return None
        try:
            details = json.loads(action.get("payload_json") or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            details = None
        return {
            "action_id": action["id"],
            "action_type": action.get("type"),
            "action_status": action.get("status"),
            "created_at": action.get("created_at"),
            "approved_at": action.get("approved_at"),
            "executed_at": action.get("executed_at"),
            "created_by": action.get("created_by"),
            "notes": action.get("notes"),
            "result_ref": action.get("result_ref"),
            "goal_id": None,
            "goal_title": None,
            "plan_id": None,
            "step_id": None,
            "step_title": None,
            "preview": f"Action {action.get('type')}",
            "action_details": details,
            "last_transition_at": action.get("executed_at") or action.get("approved_at") or action.get("created_at"),
        }

    # â”€â”€ Audit log â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _log_request(self, auth, status_code, error=None, summary=None):
        """Write to audit log. Never log secrets, tokens, or full bodies."""
        actor_type = auth['type'] if auth else "unauthorized"
        device_id  = auth.get('id') if auth else None
        ip         = self._get_client_ip()
        ua         = self.headers.get('User-Agent', '')[:200]

        try:
            self.brain.memory_engine.log_activity(
                actor_type     = actor_type,
                device_id      = device_id,
                endpoint       = self.path.split('?')[0],
                method         = self.command,
                status_code    = status_code,
                action_summary = summary,
                error          = str(error)[:256] if error else None,
                ip             = ip,
                user_agent     = ua,
            )
        except Exception as e:
            print(f"[SERVER] Failed to log activity: {e}")

    # â”€â”€ GET dispatcher â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def do_GET(self):
        if self._enforce_tls_proto():
            return

        auth   = self._get_auth_context()
        parsed = urlparse(self.path)
        path   = parsed.path

        # â”€â”€ Public root (no auth required) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            html = f"""
            <html>
                <head><title>Axis Bridge</title></head>
                <body style="font-family: sans-serif; padding: 2rem; max-width: 800px; margin: auto; line-height: 1.6;">
                    <h1 style="color: #2c3e50;">Axis Bridge is Running</h1>
                    <p style="color: #7f8c8d;">Version: 1.2.0 (Phase 5 Secure)</p>
                    <hr/>
                    <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; border-left: 5px solid #3498db;">
                        <strong>Status:</strong> Active & Secure<br/>
                        <strong>Endpoint Auth:</strong> Headers Required (legacy X-Jarvis-Token or X-Device-Token)
                    </div>
                    <p>This is the backend API server. To interact with Axis, use the 
                    pairing flow or send authorized requests via <code>curl</code> or Postman.</p>
                    <pre style="background: #2c3e50; color: #ecf0f1; padding: 1rem; border-radius: 5px;">
curl http://127.0.0.1:8001/health -H "X-Jarvis-Token: YOUR_TOKEN"</pre>
                </body>
            </html>
            """
            self.wfile.write(html.encode('utf-8'))
            return

        if path in ['/ui', '/dashboard'] or path.startswith('/static/'):
            return self._serve_static(path)

        # Unauthenticated GET â†’ allow health (local), UI, and static assets
        if not auth:
            is_public = (path in ['/ui', '/dashboard', '/', '/favicon.ico']) or path.startswith('/static/')
            if path == '/health':
                client_ip = self._get_client_ip()
                if client_ip in ['127.0.0.1', '::1']:
                    is_public = True
            
            if not is_public:
                self._log_request(None, 403, "Unauthorized GET")
                self._send_json({'error': 'Unauthorized'}, 403)
                return

        # Determine required role for this path
        if path in ['/devices', '/activity']:
            required_role = 'admin'
        else:
            required_role = 'reader'   # /health, /gmail/*, /actions, etc.

        if auth and auth['type'] == 'device' and not self._check_permission(auth, required_role):
            self._log_request(auth, 403, f"Forbidden: {auth['role']} < {required_role}")
            self._send_json({'error': 'Forbidden: Insufficient permissions'}, 403)
            return

        try:
            if path == '/health':
                self._handle_health()
            elif path == '/conversations':
                self._handle_conversations()
            elif path.startswith('/conversations/'):
                self._handle_conversation_detail(path.split('/')[-1])
            elif path == '/memories':
                self._handle_memories(parsed)
            elif path == '/gmail/inbox':
                if not self._require_system_permission(
                    auth,
                    'integrations.gmail',
                    'Gmail inbox access is disabled for this Axis session.',
                    action_label='Read Gmail inbox',
                    source='gmail_inbox',
                ):
                    return
                if not self.brain.gmail:
                    self._send_json({"error": "gmail_integration_unavailable", "reason": self.brain.google_degraded_reason}, 503)
                    return
                lim = int(parse_qs(parsed.query).get('limit', [10])[0])
                inbox = self.brain.gmail.list_messages(limit=lim)
                self._send_json({"messages": inbox})
            elif path == '/gmail/insights':
                if not self._require_system_permission(
                    auth,
                    'integrations.gmail',
                    'Gmail insights are disabled for this Axis session.',
                    action_label='Read Gmail insights',
                    source='gmail_insights',
                ):
                    return
                if not self.brain.inbox_insight:
                    self._send_json({"error": "gmail_insights_unavailable", "reason": self.brain.google_degraded_reason}, 503)
                    return
                lim = int(parse_qs(parsed.query).get('limit', [10])[0])
                insights = self.brain.get_inbox_insights(limit=lim)
                self._send_json(insights)
            elif path == '/calendar/upcoming':
                if not self._require_system_permission(
                    auth,
                    'integrations.calendar',
                    'Calendar access is disabled for this Axis session.',
                    action_label='Read upcoming calendar events',
                    source='calendar_upcoming',
                ):
                    return
                if not self.brain.calendar:
                    self._send_json({"error": "calendar_integration_unavailable", "reason": self.brain.google_degraded_reason}, 503)
                    return
                events = self.brain.calendar.list_events()
                self._send_json({"events": events})
            elif path == '/actions':
                if not self._require_system_permission(
                    auth,
                    'approvals.manage',
                    'Approval queue access is disabled for this Axis session.',
                    action_label='Inspect approvals queue',
                    source='actions_list',
                ):
                    return
                params = parse_qs(parsed.query)
                status = params.get('status', ['pending'])[0]
                actions = self.brain.memory_engine.list_pending_actions(status=status)
                self._send_json({"actions": actions})
            elif path == '/devices':
                devices = self.brain.memory_engine.list_devices()
                self._send_json({"devices": devices})
            elif path == '/status':
                if not self._require_system_permission(
                    auth,
                    'dashboard.access',
                    'System status depends on dashboard access being enabled.',
                    action_label='Inspect system status',
                    source='status',
                ):
                    return
                active_goals = self.brain.goal_engine.list_goals()
                self._send_json({
                    'active_goals': active_goals,
                    'autonomous_loop_active': getattr(
                        getattr(self.brain, 'autonomy', None),
                        'autonomous_loop_active', False
                    )
                })
            elif path == '/whoami':
                self._handle_whoami(auth)
            elif path == '/activity/recent':
                self._handle_recent_activity(auth, parsed)
            elif path == '/goals':
                if not self._require_system_permission(
                    auth,
                    'goals.view',
                    'Goal visibility is disabled for this Axis session.',
                    action_label='Inspect goals',
                    source='goals_list',
                ):
                    return
                goals = self.brain.goal_engine.list_goals()
                self._send_json({"goals": goals})
            elif path.startswith('/goals/') and path.endswith('/summary'):
                goal_id = path.split('/')[2]
                goal = self.brain.memory_engine.get_goal_record(goal_id)
                if not self._require_system_permission(
                    auth,
                    'goals.view',
                    'Goal summaries are disabled for this Axis session.',
                    action_label='Inspect goal summary',
                    goal_id=goal_id,
                    goal_title=goal.get('title') if goal else None,
                    source='goal_summary',
                ):
                    return
                res = self.brain.get_goal_summary(goal_id)
                if res: self._send_json(res)
                else: self._send_json({"error": "Goal not found"}, 404)
            elif path.startswith('/goals/') and path.endswith('/events'):
                goal_id = path.split('/')[2]
                goal = self.brain.memory_engine.get_goal_record(goal_id)
                if not self._require_system_permission(
                    auth,
                    'goals.view',
                    'Goal event history is disabled for this Axis session.',
                    action_label='Inspect goal events',
                    goal_id=goal_id,
                    goal_title=goal.get('title') if goal else None,
                    source='goal_events',
                ):
                    return
                events = self.brain.goal_engine.get_goal_events(goal_id)
                self._log_request(auth, 200, summary=f"Goal events fetched: {goal_id}")
                self._send_json({"goal_id": goal_id, "events": events, "count": len(events)})
            elif path.startswith('/goals/') and len(path.split('/')) == 3:
                goal_id = path.split('/')[2]
                goal = self.brain.memory_engine.get_goal_record(goal_id)
                if not self._require_system_permission(
                    auth,
                    'goals.view',
                    'Goal detail is disabled for this Axis session.',
                    action_label='Inspect goal detail',
                    goal_id=goal_id,
                    goal_title=goal.get('title') if goal else None,
                    source='goal_detail',
                ):
                    return
                res = self.brain.goal_engine.get_goal_context(goal_id)
                if res: self._send_json({"goal": res})
                else: self._send_json({"error": "Goal not found"}, 404)
            elif path.startswith('/web/actions/') and path.endswith('/result'):
                action_id = path.split('/')[-2]
                self._handle_web_result(auth, action_id)
            elif path == '/debug/config':
                self._handle_debug_config(auth)
            # â”€â”€ Phase 7.3 Control Plane Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            elif path == '/control/summary':
                if not self._require_system_permission(
                    auth,
                    'dashboard.access',
                    'Control-plane summary access is disabled for this Axis session.',
                    action_label='Open dashboard overview',
                    source='control_summary',
                ):
                    return
                self._handle_control_summary(auth)
            elif path == '/control/approvals':
                if not self._require_system_permission(
                    auth,
                    'approvals.manage',
                    'Approvals access is disabled for this Axis session.',
                    action_label='Review approvals',
                    source='control_approvals',
                ):
                    return
                self._handle_control_approvals(auth, parsed)
            elif path == '/control/blocked':
                if not self._require_system_permission(
                    auth,
                    'goals.view',
                    'Blocked-goal visibility is disabled for this Axis session.',
                    action_label='Inspect blocked goals',
                    source='control_blocked',
                ):
                    return
                self._handle_control_blocked(auth, parsed)
            elif path == '/control/results':
                if not self._require_system_permission(
                    auth,
                    'dashboard.access',
                    'Result visibility is disabled for this Axis session.',
                    action_label='Inspect recent results',
                    source='control_results',
                ):
                    return
                self._handle_control_results(auth, parsed)
            elif path == '/control/permissions':
                self._handle_control_permissions(auth)
            elif path == '/control/capabilities':
                self._handle_control_capabilities(auth)
            elif path == '/control/axis-hub':
                self._handle_control_axis_hub(auth)
            elif path == '/control/security':
                self._handle_control_security(auth)
            elif path == '/control/settings':
                self._handle_control_settings(auth)
            elif path == '/control/profiles':
                self._handle_control_profiles(auth)
            elif path == '/control/help-center':
                self._handle_control_help_center(auth, parsed)
            elif path == '/control/about':
                self._handle_control_about(auth)
            # â”€â”€ Phase 7.4 Readiness Endpoint â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            elif path == '/control/readiness':
                if not self._require_system_permission(
                    auth,
                    'dashboard.access',
                    'Readiness diagnostics depend on dashboard access being enabled.',
                    action_label='Inspect readiness diagnostics',
                    source='control_readiness',
                ):
                    return
                self._handle_control_readiness(auth)
            # â”€â”€ Phase 8 Voice Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            elif path == '/voice/capabilities':
                self._handle_voice_capabilities(auth)
            elif path == '/llm/models':
                from jarvis_ai.llm.router import get_all_models, PROVIDER_MAP, _get_saved_model, FALLBACK_CHAIN
                now = time.time()
                lc = JarvisRequestHandler.__dict__.get('_llm_models_cache', None)
                if lc is None:
                    JarvisRequestHandler._llm_models_cache = {}
                    lc = JarvisRequestHandler._llm_models_cache
                if not lc or (now - lc.get('ts', 0)) > 60:
                    providers = {name: p.is_available() for name, p in PROVIDER_MAP.items()}
                    active_model = _get_saved_model() or FALLBACK_CHAIN[0][1]
                    lc.update({
                        'ts': now,
                        'data': {"models": get_all_models(), "active_model": active_model, "providers": providers}
                    })
                self._send_json(lc['data'])
            elif path == '/llm/test':
                from jarvis_ai.llm.router import chat as llm_chat
                start_time = time.time()
                result = llm_chat(
                    messages=[{"role": "user", "content": "Say hello in one sentence."}],
                    system="You are an AI.",
                    fallback=True
                )
                duration_ms = int((time.time() - start_time) * 1000)
                self._send_json({
                    "response": result.get("response"),
                    "model_id": result.get("model_id"),
                    "provider": result.get("provider"),
                    "latency_ms": duration_ms
                })
            else:
                self._log_request(auth, 404)
                self._send_json({'error': 'Not Found'}, 404)
                return

            self._log_request(auth, 200, summary=f"GET {path}")
        except Exception as e:
            self._log_request(auth, 500, error=e)
            self._send_json({'error': str(e)}, 500)

    # â”€â”€ POST dispatcher â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def do_POST(self):
        print(f"[DEBUG] Received POST: {self.path}")
        if self._enforce_tls_proto():
            return

        parsed = urlparse(self.path)
        path   = parsed.path

        # â”€â”€ Public endpoints (no auth required) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if path == '/pairing/register':
            self._handle_pairing_register()
            return

        auth = self._get_auth_context()

        if not auth:
            self._log_request(None, 403, "Unauthorized POST")
            self._send_json({'error': 'Unauthorized'}, 403)
            return

        # â”€â”€ RBAC for authenticated POST â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # Default permission level for each path
        if path == '/pairing/code':
            required_role = 'admin'
        elif path.startswith('/devices/') and (path.endswith('/revoke') or path.endswith('/rotate')):
            required_role = 'admin'
        elif path.startswith('/actions/') and path.endswith('/execute'):
            required_role = 'executor'
        elif path == '/voice/capabilities':
            required_role = 'reader'
        elif path.startswith('/voice/'):
            required_role = 'operator'
        else:
            required_role = 'operator'  # /chat, etc.

        if auth['type'] == 'device' and not self._check_permission(auth, required_role):
            self._log_request(auth, 403, f"Forbidden POST: {auth['role']} < {required_role}")
            self._send_json({'error': 'Forbidden: Insufficient permissions'}, 403)
            return

        try:
            print(f"[DEBUG] POST Path: {path}")
            data = {}

            # Voice endpoints may receive multipart uploads, so they must read the
            # request body themselves exactly once.
            if path not in ('/voice/transcribe', '/voice/chat'):
                content_length = int(self.headers.get('Content-Length', 0))
                print(f"[DEBUG] Content-Length: {content_length}")
                body = self.rfile.read(content_length)
                print(f"[DEBUG] Body Read Complete ({len(body)} bytes)")
                data = json.loads(body.decode()) if content_length > 0 else {}
                print(f"[DEBUG] Data Parsed: {bool(data)}")

            if path == '/chat':
                self._handle_chat(auth, data)

            elif path == '/voice/transcribe':
                if not self._require_system_permission(
                    auth,
                    'voice.input',
                    'Voice input is disabled for this Axis session.',
                    action_label='Transcribe voice input',
                    source='voice_transcribe',
                ):
                    return
                self._handle_voice_transcribe(auth)

            elif path == '/voice/chat':
                if not self._require_system_permission(
                    auth,
                    'voice.input',
                    'Voice input is disabled for this Axis session.',
                    action_label='Route voice request',
                    source='voice_chat',
                ):
                    return
                self._handle_voice_chat(auth)

            elif path == '/voice/speak':
                if not self._require_system_permission(
                    auth,
                    'voice.output',
                    'Voice output is disabled for this Axis session.',
                    action_label='Prepare voice output',
                    source='voice_speak',
                ):
                    return
                self._handle_voice_speak(auth, data)

            elif path == '/pairing/code':
                role = data.get('role', 'reader')
                name = data.get('name', 'Unknown Device')
                code = self.brain.memory_engine.create_pairing_code(role, name)
                expires_at = (datetime.now() + timedelta(minutes=10)).isoformat()
                self._log_request(auth, 200, summary=f"Pairing code created for role={role}")
                self._send_json({"code": code, "expires_at": expires_at, "expires_in": "10 minutes"})

            elif path == '/actions/approve':
                if not self._require_system_permission(
                    auth,
                    'approvals.manage',
                    'Approvals management is disabled for this Axis session.',
                    action_label='Approve pending action',
                    source='actions_approve',
                ):
                    return
                action_id = data.get('action_id')
                if not action_id:
                    self._send_json({"error": "Missing action_id"}, 400)
                    return
                success = self.brain.memory_engine.update_action_status(action_id, 'approved')
                step, goal_summary = self._linked_goal_context_for_action(action_id) if success else (None, None)
                self._log_request(auth, 200, summary=f"Action approved: {action_id}")
                self._send_json({
                    "success": success,
                    "message": "Approval granted. Action is ready for execution." if success else "Approval could not be granted.",
                    "action": self._approval_action_snapshot(action_id),
                    "goal_summary": goal_summary,
                    "linked_step": step,
                })

            elif path == '/actions/reject':
                if not self._require_system_permission(
                    auth,
                    'approvals.manage',
                    'Approvals management is disabled for this Axis session.',
                    action_label='Reject pending action',
                    source='actions_reject',
                ):
                    return
                action_id = data.get('action_id')
                if not action_id:
                    self._send_json({"error": "Missing action_id"}, 400)
                    return
                success = self.brain.memory_engine.update_action_status(action_id, 'rejected')
                step, goal_summary = self._linked_goal_context_for_action(action_id) if success else (None, None)
                self._log_request(auth, 200, summary=f"Action rejected: {action_id}")
                self._send_json({
                    "success": success,
                    "message": "Approval denied. Linked goal state has been reconciled." if success else "Approval could not be denied.",
                    "action": self._approval_action_snapshot(action_id),
                    "goal_summary": goal_summary,
                    "linked_step": step,
                })

            elif path == '/gmail/draft_reply':
                if not self._require_system_permission(
                    auth,
                    'integrations.gmail',
                    'Gmail drafting is disabled for this Axis session.',
                    action_label='Draft Gmail reply',
                    source='gmail_draft_reply',
                ):
                    return
                res = self.brain.draft_gmail_reply(
                    message_id=data.get('message_id'),
                    tone=data.get('tone', 'professional'),
                    instructions=data.get('instructions')
                )
                self._send_json(res)
            elif path == '/web/propose':
                if not self._require_system_permission(
                    auth,
                    'browser.web_automation',
                    'Web automation is disabled for this Axis session.',
                    action_label='Queue web automation',
                    source='web_propose',
                ):
                    return
                print("[DEBUG] Dispatching to _handle_web_propose")
                self._handle_web_propose(auth, data)
                print("[DEBUG] Returned from _handle_web_propose")
            elif path.startswith('/web/actions/') and path.endswith('/execute'):
                if not self._require_system_permission(
                    auth,
                    'browser.web_automation',
                    'Web automation is disabled for this Axis session.',
                    action_label='Execute web automation',
                    source='web_execute',
                ):
                    return
                action_id = path.split('/')[-2]
                self._handle_web_execute(auth, action_id)
            elif path.startswith('/actions/') and path.endswith('/execute'):
                if not self._require_system_permission(
                    auth,
                    'approvals.manage',
                    'Approvals management is disabled for this Axis session.',
                    action_label='Execute approved action',
                    source='actions_execute',
                ):
                    return
                action_id = path.split('/')[-2]
                ok, msg = self.brain.execute_pending_action(action_id)
                step, goal_summary = self._linked_goal_context_for_action(action_id) if self.brain.memory_engine.get_pending_action(action_id) else (None, None)
                self._log_request(auth, 200 if ok else 400,
                                  summary=f"Action execute: {action_id} -> {ok}")
                self._send_json({
                    "success": ok,
                    "message": msg,
                    "action": self._approval_action_snapshot(action_id),
                    "goal_summary": goal_summary,
                    "linked_step": step,
                })
                
            # â”€â”€ Phase 7 Goal Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            elif path == '/goals':
                if not self._require_system_permission(
                    auth,
                    'goals.manage',
                    'Goal creation is disabled for this Axis session.',
                    action_label='Create goal',
                    source='goals_create',
                ):
                    return
                objective = data.get('objective')
                if not objective:
                    self._send_json({"error": "Missing objective"}, 400)
                    return
                title = data.get('title', 'Untitled Goal')
                priority = data.get('priority', 'normal')
                default_requires_approval = self.brain._axis_setting_values().get('goals.default_requires_approval', True)
                requires_approval = data.get('requires_approval', default_requires_approval)
                
                goal = self.brain.goal_engine.create_goal(objective, title=title, priority=priority, requires_approval=requires_approval)
                self._log_request(auth, 200, summary=f"Goal created: {goal['id']}")
                self._send_json({"goal": goal})
                
            elif path.startswith('/goals/') and path.endswith('/plan'):
                goal_id = path.split('/')[2]
                goal = self.brain.memory_engine.get_goal_record(goal_id)
                if not self._require_system_permission(
                    auth,
                    'goals.execute',
                    'Goal planning is disabled for this Axis session.',
                    action_label='Plan goal',
                    goal_id=goal_id,
                    goal_title=goal.get('title') if goal else None,
                    source='goal_plan',
                ):
                    return
                res = self.brain.goal_engine.plan_goal(goal_id, brain=self.brain)
                if "error" in res:
                    self._send_json(res, 400)
                else:
                    self._log_request(auth, 200, summary=f"Goal planned: {goal_id}")
                    self._send_json(res)
                    
            elif path.startswith('/goals/') and path.endswith('/advance'):
                goal_id = path.split('/')[2]
                goal = self.brain.memory_engine.get_goal_record(goal_id)
                if not self._require_system_permission(
                    auth,
                    'goals.execute',
                    'Goal execution is disabled for this Axis session.',
                    action_label='Advance goal',
                    goal_id=goal_id,
                    goal_title=goal.get('title') if goal else None,
                    source='goal_advance',
                ):
                    return
                ok, msg = self.brain.goal_engine.advance_goal(goal_id, brain=self.brain)
                self._log_request(auth, 200 if ok else 400, summary=f"Goal advanced: {goal_id} -> {ok}")
                self._send_json({"success": ok, "message": msg})

            # â”€â”€ Phase 7.1 Reconciliation & Resume Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            elif path.startswith('/goals/') and path.endswith('/reconcile'):
                goal_id = path.split('/')[2]
                goal = self.brain.memory_engine.get_goal_record(goal_id)
                if not self._require_system_permission(
                    auth,
                    'goals.control',
                    'Goal control is disabled for this Axis session.',
                    action_label='Reconcile goal',
                    goal_id=goal_id,
                    goal_title=goal.get('title') if goal else None,
                    source='goal_reconcile',
                ):
                    return
                res = self.brain.goal_engine.reconcile_goal(goal_id)
                code = 404 if "error" in res else 200
                self._log_request(auth, code, summary=f"Goal reconciled: {goal_id}")
                self._send_json(res, code)

            elif path.startswith('/goals/') and path.endswith('/resume'):
                goal_id = path.split('/')[2]
                goal = self.brain.memory_engine.get_goal_record(goal_id)
                if not self._require_system_permission(
                    auth,
                    'goals.control',
                    'Goal control is disabled for this Axis session.',
                    action_label='Resume goal',
                    goal_id=goal_id,
                    goal_title=goal.get('title') if goal else None,
                    source='goal_resume',
                ):
                    return
                res = self.brain.goal_engine.resume_goal(goal_id, brain=self.brain)
                code = 404 if "error" in res else 200
                self._log_request(auth, code, summary=f"Goal resumed: {goal_id}")
                self._send_json(res, code)

            elif path.startswith('/goals/') and path.endswith('/pause'):
                goal_id = path.split('/')[2]
                goal = self.brain.memory_engine.get_goal_record(goal_id)
                if not self._require_system_permission(
                    auth,
                    'goals.control',
                    'Goal control is disabled for this Axis session.',
                    action_label='Pause goal',
                    goal_id=goal_id,
                    goal_title=goal.get('title') if goal else None,
                    source='goal_pause',
                ):
                    return
                res = self.brain.goal_engine.pause_goal(goal_id, reason=data.get('reason', 'Paused by owner'))
                code = 404 if "error" in res else 200
                self._log_request(auth, code, summary=f"Goal paused: {goal_id}")
                self._send_json(res, code)

            elif path.startswith('/goals/') and path.endswith('/stop'):
                goal_id = path.split('/')[2]
                goal = self.brain.memory_engine.get_goal_record(goal_id)
                if not self._require_system_permission(
                    auth,
                    'goals.control',
                    'Goal control is disabled for this Axis session.',
                    action_label='Stop goal',
                    goal_id=goal_id,
                    goal_title=goal.get('title') if goal else None,
                    source='goal_stop',
                ):
                    return
                res = self.brain.goal_engine.stop_goal(goal_id, reason=data.get('reason', 'Stopped by owner'))
                code = 404 if "error" in res else 200
                self._log_request(auth, code, summary=f"Goal stopped: {goal_id}")
                self._send_json(res, code)

            elif path.startswith('/goals/') and path.endswith('/edit'):
                goal_id = path.split('/')[2]
                goal = self.brain.memory_engine.get_goal_record(goal_id)
                if not self._require_system_permission(
                    auth,
                    'goals.edit',
                    'Goal editing is disabled for this Axis session.',
                    action_label='Edit goal',
                    goal_id=goal_id,
                    goal_title=goal.get('title') if goal else None,
                    source='goal_edit',
                ):
                    return
                res = self.brain.goal_engine.edit_goal(goal_id, data)
                code = 404 if "error" in res else 200
                self._log_request(auth, code, summary=f"Goal edited: {goal_id}")
                self._send_json(res, code)

            elif path.startswith('/goals/') and path.endswith('/replan'):
                goal_id = path.split('/')[2]
                goal = self.brain.memory_engine.get_goal_record(goal_id)
                if not self._require_system_permission(
                    auth,
                    'goals.control',
                    'Goal replan is disabled for this Axis session.',
                    action_label='Replan goal',
                    goal_id=goal_id,
                    goal_title=goal.get('title') if goal else None,
                    source='goal_replan',
                ):
                    return
                res = self.brain.goal_engine.replan_goal(goal_id, brain=self.brain)
                code = 404 if "error" in res else 200
                self._log_request(auth, code, summary=f"Goal replanned: {goal_id}")
                self._send_json(res, code)

            elif path == '/goals/reconcile_all':
                # Owner-only bulk reconciliation
                if auth.get('type') == 'device' and auth.get('role') != 'admin':
                    self._send_json({'error': 'Forbidden: owner token required'}, 403)
                    return
                if not self._require_system_permission(
                    auth,
                    'goals.control',
                    'Goal control is disabled for this Axis session.',
                    action_label='Bulk reconcile goals',
                    source='goals_reconcile_all',
                ):
                    return
                res = self.brain.goal_engine.reconcile_all_goals()
                self._log_request(auth, 200, summary="Bulk reconcile executed")
                self._send_json(res)

            elif path == '/control/profiles/update':
                self._handle_update_axis_profile(auth, data)

            elif path == '/control/settings/update':
                self._handle_update_axis_setting(auth, data)

            elif path.startswith('/control/permissions/') and len(path.split('/')) == 4:
                permission_key = path.split('/')[3]
                self._handle_set_permission_state(auth, permission_key, data)

            elif path.startswith('/control/permission-requests/') and path.endswith('/approve'):
                request_id = path.split('/')[-2]
                self._handle_permission_request_decision(auth, request_id, 'approved', data)

            elif path.startswith('/control/permission-requests/') and path.endswith('/deny'):
                request_id = path.split('/')[-2]
                self._handle_permission_request_decision(auth, request_id, 'denied', data)


            # â”€â”€ Device management (RESTful paths) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            elif path.startswith('/devices/') and path.endswith('/revoke'):
                device_id = path.split('/')[-2]
                ok = self.brain.memory_engine.revoke_device(device_id)
                self._log_request(auth, 200, summary=f"Device revoked: {device_id}")
                self._send_json({"success": ok, "device_id": device_id})

            elif path.startswith('/devices/') and path.endswith('/rotate'):
                device_id = path.split('/')[-2]
                new_token = self.brain.memory_engine.rotate_device_token(device_id)
                if new_token:
                    self._log_request(auth, 200, summary=f"Token rotated: {device_id}")
                    self._send_json({"success": True, "device_id": device_id,
                                     "new_device_token": new_token})
                else:
                    self._log_request(auth, 404, f"Rotate failed: {device_id}")
                    self._send_json({"success": False, "error": "Device not found or revoked"}, 404)

            # â”€â”€ Legacy body-based revoke (backward compat) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            elif path == '/devices/revoke':
                device_id = data.get('device_id')
                ok = self.brain.memory_engine.revoke_device(device_id)
                self._log_request(auth, 200, summary=f"Device revoked (legacy): {device_id}")
                self._send_json({"success": ok})
            
            elif path == '/llm/model':
                model_id = data.get('model_id')
                if model_id:
                    from jarvis_ai.llm.router import save_model_preference
                    save_model_preference(model_id)
                    JarvisRequestHandler._llm_models_cache = {}
                    self._send_json({"success": True, "model_id": model_id})
                else:
                    self._send_json({"error": "Missing model_id"}, 400)

            else:
                self._log_request(auth, 501, "Endpoint not implemented")
                self._send_json({'error': 'Endpoint not implemented'}, 501)

        except Exception as e:
            import traceback
            err = traceback.format_exc()
            with open("test_out.txt", "w") as f: f.write(err)
            self._log_request(auth, 500, error=e)
            self._send_json({'error': "Internal server error: " + str(e)}, 500)

    # â”€â”€ Public handler: pairing registration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _handle_pairing_register(self):
        """Allow a mobile app to register using a one-time pairing code.
        Rate-limited per IP to prevent brute-force guessing."""
        ip = self._get_client_ip()

        if not _check_rate_limit(ip):
            self._log_request(None, 429, "Rate limit exceeded on /pairing/register")
            self._send_json({"error": "Too many requests. Try again in a minute."}, 429)
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json({"error": "Missing body"}, 400)
                return

            data        = json.loads(self.rfile.read(content_length).decode())
            code        = data.get('code', '').strip()
            device_name = data.get('device_name', 'Mobile App')[:64]
            requested_role = data.get('requested_role', '')

            if not code:
                self._send_json({"error": "Missing pairing code"}, 400)
                return

            record = self.brain.memory_engine.get_pairing_code(code)
            if not record:
                self._log_request(None, 403, error="Invalid or expired pairing code")
                self._send_json({"error": "Invalid or expired pairing code"}, 403)
                return

            # Role: use requested_role from body, but cap it to the pairing code's allowed role.
            # Hierarchy: executor > operator > reader
            role_hierarchy = ['reader', 'operator', 'executor']
            allowed_role   = record['role']
            if requested_role in role_hierarchy:
                req_idx     = role_hierarchy.index(requested_role)
                allowed_idx = role_hierarchy.index(allowed_role) if allowed_role in role_hierarchy else 0
                final_role  = role_hierarchy[min(req_idx, allowed_idx)]
            else:
                final_role = allowed_role  # default to pairing code's role

            # Consume the code (single-use)
            self.brain.memory_engine.use_pairing_code(code)
            device_id, token = self.brain.memory_engine.register_device(device_name, final_role)

            auth_ctx = {"type": "device", "id": device_id, "role": final_role}
            self._log_request(auth_ctx, 200, summary=f"Device paired: {device_name} role={final_role}")
            self._send_json({
                "device_id":    device_id,
                "device_token": token,
                "role":         final_role,
            })
        except Exception as e:
            self._log_request(None, 400, error=f"Pairing exception: {type(e).__name__}")
            self._send_json({"error": "Pairing failed"}, 400)

    # â”€â”€ Endpoint handlers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Module-level health cache: {result, timestamp}
    _health_cache = {}
    _HEALTH_CACHE_TTL = 10  # seconds

    def _handle_health(self):
        uptime = int(time.time() - self.server_start_time) if self.server_start_time else 0
        now = time.time()
        cache = JarvisRequestHandler._health_cache
        if not cache or (now - cache.get('ts', 0)) > self._HEALTH_CACHE_TTL:
            db_healthy = ping_supabase()
            cache['db'] = db_healthy
            cache['ts'] = now
        else:
            db_healthy = cache['db']
        self._send_json({
            'status':  'ok',
            'version':  APP_VERSION,
            'uptime':   uptime,
            'database': 'supabase' if db_healthy else 'degraded'
        })

    def _handle_conversations(self):
        try:
            from jarvis_ai.db.supabase_client import get_supabase
            res = get_supabase().table("conversations").select("id, updated_at").order("updated_at", desc=True).execute()
            self._send_json({"conversations": res.data if res.data else []})
        except Exception:
            self._send_json({"conversations": []})

    def _handle_conversation_detail(self, conv_id):
        messages = self.brain.memory_engine.get_messages(conv_id)
        summary  = self.brain.memory_engine.get_summary(conv_id)
        self._send_json({"conversation_id": conv_id, "messages": messages, "summary": summary})

    def _handle_memories(self, parsed):
        query    = parse_qs(parsed.query).get('query', [None])[0]
        memories = (self.brain.memory_engine.search_long_term_memory(query)
                    if query else self.brain.memory_engine.list_long_term_memories())
        self._send_json({"memories": memories})

    def _handle_chat(self, auth, data):
        message = data.get("message", "")
        conv_id = data.get("conversation_id", secrets.token_hex(8))
        dashboard_context = data.get("dashboard_context")
        chat_result = self.brain.chat_with_metadata(
            conv_id,
            message,
            dashboard_context=dashboard_context,
        )
        reply = chat_result.get("reply", "")
        self._log_request(auth, 200, summary=f"Chat: conv={conv_id} len={len(message)}")
        self._send_json({
            "conversation_id": conv_id,
            "response": reply,
            "reply": reply,
            "actions": chat_result.get("actions", []),
            "routing": chat_result.get("routing", {})
        })

    def _handle_whoami(self, auth):
        """Diagnostic endpoint to show current auth context."""
        ip = self._get_client_ip()
        ua = self.headers.get('User-Agent', '')
        
        # Determine permissions for the current auth context
        # This is a bit of a duplicate of logic elsewhere, but useful for diagnostics.
        permissions = []
        if auth:
            if auth['type'] == 'owner':
                permissions = ["all"]
            else:
                # Basic roles
                role = auth.get('role', 'reader')
                if role == 'reader': permissions = ["read"]
                elif role == 'operator': permissions = ["read", "operate"]
                elif role == 'executor': permissions = ["read", "operate", "execute"]

        res = {
            "status": "authenticated" if auth else "unauthenticated",
            "auth_type": f"{auth['type']}_token" if auth else "none",
            "auth_method": auth.get('auth_method', 'none') if auth else "none",
            "is_owner": auth['type'] == 'owner' if auth else False,
            "permissions": permissions,
            "auth_context": {
                "type": auth['type'] if auth else "none",
                "role": "owner" if (auth and auth['type'] == 'owner') else (auth.get('role', 'none') if auth else "none"),
                "id": auth.get('id') if auth and auth['type'] == 'device' else None,
                "name": auth.get('name') if auth and auth['type'] == 'device' else ("Owner" if auth and auth['type'] == 'owner' else "None"),
                "session_class": self._session_class(auth) if auth else "desktop_guest",
                "can_manage_permissions": self._can_manage_permissions(auth) if auth else False,
                "can_manage_workspace_config": self._can_manage_workspace_config(auth) if auth else False,
            },
            "request": {
                "ip": ip,
                "user_agent": ua,
                "path": self.path,
                "method": self.command
            },
            "server": {
                "version": APP_VERSION,
                "schema_version": DB_SCHEMA_VERSION
            }
        }
        if auth:
            profiles = self.brain.get_profiles_and_plans_snapshot()
            res["auth_context"]["profile"] = profiles["active_profile"]
            res["auth_context"]["plan"] = profiles["active_plan"]
        self._send_json(res)

    def _handle_web_propose(self, auth, data):
        """Queue a web automation plan for approval."""
        print("[DEBUG] Inside _handle_web_propose")
        try:
            objective = data.get('objective', 'Web automation task')
            plan = data.get('plan')

            if not isinstance(plan, dict) or 'steps' not in plan or not isinstance(plan['steps'], list):
                self._send_json({"error": "Invalid or missing automation plan"}, 400)
                return

            # 1. Enforce constraints
            constraints = plan.get('constraints', {})
            if not isinstance(constraints, dict):
                constraints = {}
            plan['constraints'] = {
                'max_steps': min(int(constraints.get('max_steps', 30)), 30),
                'timeout_ms': min(int(constraints.get('timeout_ms', 30000)), 30000),
                'stop_on_captcha': True,
                'stop_on_login': True,
                'stop_on_payment': True
            }

            # 2. Extract and restrict steps
            allowed_actions = {'goto', 'click', 'type', 'extract', 'screenshot', 'wait_for'}
            commit_keywords = ['submit', 'apply', 'send', 'confirm', 'purchase', 'checkout', 'place', 'order', 'continue-final']

            valid_steps = []
            has_commit_risk = False
            commit_risk_reasons = []

            for i, step in enumerate(plan['steps']):
                if i >= plan['constraints']['max_steps']:
                    break # Enforce max steps server-side
                
                action = step.get('action')
                if action not in allowed_actions:
                    self._send_json({"error": f"Invalid action at step {i}: {action}"}, 400)
                    return

                # Validate specific actions
                if action == 'goto':
                    url = step.get('url', '')
                    if not isinstance(url, str) or not url.startswith(('http://', 'https://')) or len(url) > 2000:
                        self._send_json({"error": f"Invalid or malformed url at step {i}"}, 400)
                        return
                    if any(kw in url.lower() for kw in ['checkout', 'payment', 'cart', 'buy']):
                        has_commit_risk = True
                        commit_risk_reasons.append(f"goto URL indicates commit risk ({url[:30]}...)")
                
                elif action in ['click', 'extract', 'type', 'wait_for']:
                    selector = step.get('selector')
                    if not isinstance(selector, str) or not selector or len(selector) > 500:
                        self._send_json({"error": f"Invalid or missing selector at step {i}"}, 400)
                        return
                    
                    sel_lower = selector.lower()
                    if action == 'click' and (any(kw in sel_lower for kw in commit_keywords) or 'type="submit"' in sel_lower or "type='submit'" in sel_lower):
                        has_commit_risk = True
                        commit_risk_reasons.append(f"Selector suggests commit action: {selector}")
                        
                    if action == 'type':
                        text = step.get('text')
                        if not isinstance(text, str) or len(text) > 2000:
                            self._send_json({"error": f"Invalid text payload at step {i}"}, 400)
                            return
                            
                    elif action == 'extract':
                        name = step.get('name')
                        if not isinstance(name, str) or not name or len(name) > 100:
                            self._send_json({"error": f"Invalid name for extract at step {i}"}, 400)
                            return
                            
                elif action == 'screenshot':
                    name = step.get('name')
                    if not isinstance(name, str) or not name or len(name) > 100:
                        self._send_json({"error": f"Invalid name for screenshot at step {i}"}, 400)
                        return

                valid_steps.append(step)

            plan['steps'] = valid_steps
            plan['has_commit_risk'] = has_commit_risk
            plan['commit_risk_reasons'] = commit_risk_reasons

            # Combine objective into plan for persistence
            plan['objective'] = objective
            action_id = self.brain.propose_action('web.plan.execute', plan, conversation_id=auth.get('id', 'mobile'))
            
            self._log_request(auth, 200, summary=f"Web plan proposed: {objective} (ID: {action_id})")
            self._send_json({"action_id": action_id, "status": "pending"})
        except Exception as e:
            self._log_request(auth, 500, error=e)
            self._send_json({"error": str(e)}, 500)

    def _handle_web_execute(self, auth, action_id):
        """Manually trigger execution of an APPROVED web action."""
        ok, msg = self.brain.execute_pending_action(action_id)
        status_code = 200 if ok else 400
        self._log_request(auth, status_code, summary=f"Web execute: {action_id} -> {ok}")
        self._send_json({"success": ok, "message": msg})

    def _handle_web_result(self, auth, action_id):
        """Retrieve results and screenshots from a completed web session."""
        action = self.brain.memory_engine.get_pending_action(action_id)
        if not action or action['type'] != 'web.plan.execute':
            self._send_json({"error": "Web action not found"}, 404)
            return

        # Results are stored in storage/web_sessions/<session_id>/result.json
        result_ref = action.get('result_ref')
        
        # Fallback for old actions created before Phase 7
        notes = action.get('notes', '')
        if not result_ref and "Session: " in notes:
            result_ref = notes.split("Session: ")[1].strip()
        
        if not result_ref:
            self._send_json({
                "action_id": action_id,
                "status": action['status'],
                "notes": notes,
                "result": None
            })
            return

        from pathlib import Path
        storage_dir = Path(self.brain.config.get('paths', {}).get('storage_dir', 'storage/')) / 'web_sessions' / result_ref
        result_path = storage_dir / "result.json"

        if not result_path.exists():
            self._send_json({"error": "Result file missing"}, 404)
            return

        with open(result_path, 'r') as f:
            result_data = json.load(f)

        self._send_json({
            "action_id": action_id,
            "status": action['status'],
            "session_id": result_ref,
            "result": result_data
        })

    def _handle_recent_activity(self, auth, parsed):
        """View latest activity logs."""
        params = parse_qs(parsed.query)
        limit = int(params.get('limit', [50])[0])
        req_device_id = params.get('device_id', [None])[0]

        # RBAC: device token can only view its own entries
        if auth['type'] == 'device':
            # If device_id is requested, it MUST match the token's device_id
            if req_device_id and req_device_id != auth['id']:
                self._log_request(auth, 403, error="Attempted to view other device activity")
                self._send_json({'error': 'Forbidden: Cannot view other device logs'}, 403)
                return
            # Force filter to own device_id
            rows = self.brain.memory_engine.get_recent_activity(limit=limit, device_id=auth['id'])
        else:
            # Owner can view everything/any device
            rows = self.brain.memory_engine.get_recent_activity(limit=limit, device_id=req_device_id)

        self._send_json({"activity": rows})

    def _handle_debug_config(self, auth):
        """Safe config snapshot (no secrets). Owner only."""
        if auth['type'] != 'owner':
             self._log_request(auth, 403, error="Unauthorized debug access")
             self._send_json({'error': 'Forbidden: Owner only'}, 403)
             return

        # Safely extract config (manual selection to avoid secrets)
        srv_cfg = self.brain.config.get('server', {})
        host, port = self.server.server_address
        res = {
            "server_bind": f"{host}:{port}",
            "remote_enabled": self._remote_enabled,
            "behind_reverse_proxy": self._behind_reverse_proxy,
            "db_path": "supabase",
            "schema_version": DB_SCHEMA_VERSION,
            "feature_flags": {
                "google_gmail": self.brain.config.get('google', {}).get('enabled', False),
                # Add others if they exist in standard config
            },
            "request_limits": {
                "rate_limit_max": _RATE_LIMIT_MAX,
                "rate_limit_window": _RATE_LIMIT_WINDOW
            }
        }
        self._send_json(res)

    def _handle_control_permissions(self, auth):
        snapshot = self.brain.get_permissions_snapshot(auth_context=auth, user_agent=self._user_agent())
        snapshot["runtime"] = self._permission_runtime()
        snapshot["session_guidance"] = (
            "This session can grant or revoke permissions."
            if snapshot.get("can_manage")
            else "This session is read-only for trust settings. High-risk permission changes require a desktop owner session."
        )
        self._send_json(snapshot)

    def _handle_control_capabilities(self, auth):
        guide = self.brain.get_capabilities_guide()
        guide["runtime"] = self._permission_runtime()
        guide["session_class"] = self._session_class(auth)
        self._send_json(guide)

    def _handle_control_axis_hub(self, auth):
        snapshot = self.brain.get_axis_hub_snapshot()
        snapshot["session_class"] = self._session_class(auth)
        self._send_json(snapshot)

    def _handle_control_security(self, auth):
        snapshot = self.brain.get_security_compliance_snapshot(auth_context=auth, user_agent=self._user_agent())
        snapshot["session_class"] = self._session_class(auth)
        self._send_json(snapshot)

    def _handle_control_settings(self, auth):
        snapshot = self.brain.get_settings_snapshot()
        snapshot["session_class"] = self._session_class(auth)
        snapshot["can_manage"] = self._can_manage_workspace_config(auth)
        self._send_json(snapshot)

    def _handle_control_profiles(self, auth):
        snapshot = self.brain.get_profiles_and_plans_snapshot()
        snapshot["session_class"] = self._session_class(auth)
        snapshot["can_manage"] = self._can_manage_workspace_config(auth)
        self._send_json(snapshot)

    def _handle_control_help_center(self, auth, parsed):
        params = parse_qs(parsed.query)
        page_id = params.get('page', ['overview'])[0]
        goal_id = params.get('goal_id', [None])[0]
        snapshot = self.brain.get_axis_help_snapshot(
            page_id=page_id,
            goal_id=goal_id,
            auth_context=auth,
            user_agent=self._user_agent(),
        )
        self._send_json(snapshot)

    def _handle_update_axis_profile(self, auth, data):
        if not self._can_manage_workspace_config(auth):
            self._send_json({
                "error": "owner_required",
                "message": "Profiles and plans can only be updated from an owner-controlled configuration session.",
            }, 403)
            return
        try:
            snapshot = self.brain.update_axis_profile(
                display_name=data.get("display_name"),
                profile_type=data.get("profile_type"),
                plan_id=data.get("plan_id"),
            )
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 400)
            return
        self._send_json({
            "success": True,
            "snapshot": snapshot,
        })

    def _handle_update_axis_setting(self, auth, data):
        if not self._can_manage_workspace_config(auth):
            self._send_json({
                "error": "owner_required",
                "message": "Settings can only be updated from an owner-controlled configuration session.",
            }, 403)
            return
        setting_key = data.get("key")
        if not setting_key:
            self._send_json({"error": "Missing setting key"}, 400)
            return
        try:
            snapshot = self.brain.update_axis_setting(setting_key, data.get("value"))
        except KeyError:
            self._send_json({"error": "Setting not found"}, 404)
            return
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 400)
            return
        self._send_json({
            "success": True,
            "snapshot": snapshot,
        })

    def _handle_set_permission_state(self, auth, permission_key, data):
        if not self._can_manage_permissions(auth):
            self._send_json({
                "error": "desktop_owner_required",
                "message": "Permission changes require a desktop owner session. Mobile and device sessions are read-only here.",
                "session_class": self._session_class(auth),
            }, 403)
            return

        state = data.get("state")
        if not state:
            self._send_json({"error": "Missing permission state"}, 400)
            return

        permission = self.brain.permissions.get_permission(
            permission_key,
            runtime=self._permission_runtime(),
            auth_context=auth,
            user_agent=self._user_agent(),
        )
        if not permission:
            self._send_json({"error": "Permission not found"}, 404)
            return
        if permission.get("risk_level") in ("high", "critical") and state == "enabled" and not data.get("acknowledge_risk"):
            self._send_json({
                "error": "risk_acknowledgement_required",
                "message": f"{permission['name']} is marked {permission['risk_level']}. Confirm the risk before enabling it.",
                "permission": permission,
            }, 400)
            return

        try:
            updated = self.brain.permissions.set_permission_state(permission_key, state)
        except KeyError:
            self._send_json({"error": "Permission not found"}, 404)
            return
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 400)
            return

        request_id = data.get("request_id")
        request = None
        if request_id:
            request = self.brain.memory_engine.resolve_permission_request(
                request_id,
                'approved',
                resolution_note=data.get("note") or f"Set to {state}",
            )

        self._send_json({
            "success": True,
            "permission": updated,
            "request": request,
            "snapshot": self.brain.get_permissions_snapshot(auth_context=auth, user_agent=self._user_agent()),
        })

    def _handle_permission_request_decision(self, auth, request_id, decision, data):
        if not self._can_manage_permissions(auth):
            self._send_json({
                "error": "desktop_owner_required",
                "message": "Permission request decisions require a desktop owner session.",
                "session_class": self._session_class(auth),
            }, 403)
            return

        request = self.brain.memory_engine.get_permission_request(request_id)
        if not request:
            self._send_json({"error": "Permission request not found"}, 404)
            return
        if request.get("status") != "pending":
            self._send_json({"error": "Permission request is no longer pending", "request": request}, 400)
            return

        permission = self.brain.permissions.get_permission(
            request["permission_key"],
            runtime=self._permission_runtime(),
            auth_context=auth,
            user_agent=self._user_agent(),
        )

        if decision == 'approved':
            requested_state = request.get("requested_state") or data.get("state") or "enabled"
            if permission and permission.get("risk_level") in ("high", "critical") and requested_state == "enabled" and not data.get("acknowledge_risk"):
                self._send_json({
                    "error": "risk_acknowledgement_required",
                    "message": f"{permission['name']} is marked {permission['risk_level']}. Confirm the risk before approving it.",
                    "request": request,
                }, 400)
                return
            try:
                if requested_state and permission and permission.get("toggleable", True):
                    permission = self.brain.permissions.set_permission_state(request["permission_key"], requested_state)
            except ValueError as exc:
                self._send_json({"error": str(exc), "request": request}, 400)
                return

        resolved = self.brain.memory_engine.resolve_permission_request(
            request_id,
            decision,
            resolution_note=data.get("note") or f"Permission request {decision}",
        )
        self._send_json({
            "success": True,
            "decision": decision,
            "request": resolved,
            "permission": permission,
            "snapshot": self.brain.get_permissions_snapshot(auth_context=auth, user_agent=self._user_agent()),
        })

    def _handle_control_summary(self, auth):
        """Unified control plane snapshot."""
        is_owner = auth and auth['type'] == 'owner'
        if not is_owner and not self._check_permission(auth, 'operator'):
            self._log_request(auth, 403, error="Unauthorized control summary access")
            self._send_json({'error': 'Forbidden: Insufficient role for control summary'}, 403)
            return

        snapshot = self.brain.get_live_control_snapshot()
        counts = snapshot.get("counts", {})
        llm_info = snapshot.get("llm", {})
        blocked_items = snapshot.get("blocked", [])
        blocked_counts = {
            "goals": sum(1 for item in blocked_items if item.get("item_type") == "goal"),
            "steps": sum(1 for item in blocked_items if item.get("item_type") == "step"),
        }
        permissions_summary = snapshot.get("permissions", {})
        ui_summary = {
            "active_goals_count": counts.get("goals_active", 0),
            "pending_approvals_count": self.brain.memory_engine.count_pending_actions(status='actionable'),
            "blocked_counts": blocked_counts,
            "recent_results_count": len(snapshot.get("results", [])),
            "paused_goals_count": counts.get("goals_paused", 0),
            "stopped_goals_count": counts.get("goals_stopped", 0),
            "permission_requests_pending": counts.get("permission_requests_pending", 0),
            "disabled_permissions_count": permissions_summary.get("counts", {}).get("disabled", 0),
            "high_risk_enabled_count": permissions_summary.get("counts", {}).get("high_risk_enabled", 0),
            "recommended_next_actions": snapshot.get("recommendations", []),
            "llm_active_model": llm_info.get("active_model", "llama-3.3-70b-versatile"),
            "llm_providers": llm_info.get("providers", {})
        }

        res = {
            "server": {
                "version": APP_VERSION,
                "schema_version": DB_SCHEMA_VERSION,
            },
            "auth": {
                "type": f"{auth['type']}_token" if auth else "none",
                "is_owner": is_owner,
                "role": auth.get('role', 'admin') if auth else "none",
                "session_class": self._session_class(auth) if auth else "desktop_guest",
            },
            "summary": ui_summary,
            "pending_approvals": snapshot.get("approvals", []),
            "blocked_items": blocked_items,
            "recent_goal_events": snapshot.get("events", []),
            "feature_flags": {
                "autonomous_loop": getattr(getattr(self.brain, 'autonomy', None), 'autonomous_loop_active', False),
                "web_automation": self.brain.config.get('capabilities', {}).get('web_automation', {}).get('enabled', False),
                "mock_llm": False,
            },
            "permissions": permissions_summary,
            "permission_requests": snapshot.get("permission_requests", []),
            "google": snapshot.get("google"),
            "voice": snapshot.get("voice"),
        }

        if not is_owner:
            res.pop("feature_flags", None)

        self._send_json(res)

    def _handle_control_approvals(self, auth, parsed):
        if not self._check_permission(auth, 'operator'):
            self._send_json({'error': 'Forbidden'}, 403)
            return
            
        params = parse_qs(parsed.query)
        limit = min(int(params.get('limit', [50])[0]), 100)
        status = params.get('status', ['actionable'])[0]
        goal_id = params.get('goal_id', [None])[0]
        action_type = params.get('type', [None])[0]

        items = self.brain.memory_engine.get_pending_approvals_with_linkage(
            limit=limit, status=status, goal_id=goal_id, action_type=action_type
        )
        self._send_json({
            "pending_approvals": items,
            "status_counts": self.brain.memory_engine.get_pending_action_status_counts(),
        })

    def _handle_control_blocked(self, auth, parsed):
        if not self._check_permission(auth, 'operator'):
            self._send_json({'error': 'Forbidden'}, 403)
            return
            
        params = parse_qs(parsed.query)
        limit = min(int(params.get('limit', [50])[0]), 100)

        items = self.brain.get_live_control_snapshot(
            approvals_limit=1,
            blocked_limit=limit,
            results_limit=1,
            events_limit=1,
            goals_limit=1,
            rec_limit=1,
        ).get("blocked", [])
        self._send_json({"blocked_items": items})

    def _handle_control_results(self, auth, parsed):
        if not self._check_permission(auth, 'reader'):
            self._send_json({'error': 'Forbidden'}, 403)
            return
            
        params = parse_qs(parsed.query)
        limit = min(int(params.get('limit', [50])[0]), 100)
        
        items = self.brain.memory_engine.get_recent_results(limit=limit)
        self._send_json({"results": items})

    def _handle_control_about(self, auth):
        """GET /control/about. Release manifest and about info."""
        from jarvis_ai.core.version import APP_VERSION, DB_SCHEMA_VERSION
        
        # Publicly visible modules (names only)
        modules = ["MemoryEngine", "Brain", "GoalEngine"]
        if self.brain and self.brain.config.get('capabilities', {}).get('web_automation', {}).get('enabled'):
            modules.append("WebAutomation")
        if hasattr(self.brain, "voice"):
            modules.append("VoiceSubsystem")
            
        about = {
            "app_name": "Axis",
            "legacy_internal_name": "Jarvis",
            "app_version": APP_VERSION,
            "schema_version": DB_SCHEMA_VERSION,
            "status": "online",
            "modules_enabled": modules,
            "canonical_auth": "Axis owner header (legacy X-Jarvis-Token) | X-Device-Token",
            "ui_available": True,
            "dashboard_sections": [
                "Overview",
                "Goals",
                "Approvals",
                "Blocked",
                "Results",
                "Voice",
                "Permissions & Access",
                "Capabilities & Guide",
                "Axis Hub",
                "Security & Compliance",
                "Settings",
                "Profiles & Plans",
            ],
        }
        self._send_json(about)

    def _handle_control_readiness(self, auth):
        """Phase 7.4 health and readiness report for operators."""
        from jarvis_ai.core.version import DB_SCHEMA_VERSION, APP_VERSION
        from jarvis_ai.core.runtime_lock import RuntimeLock
        import os
        from datetime import datetime

        # RBAC: Owner only for full readiness details
        if auth['type'] == 'device' and auth['role'] != 'admin':
            self._send_json({'error': 'Forbidden: Owner role required for readiness report'}, 403)
            return

        report = {
            "status": "online",
            "timestamp": datetime.now().isoformat(),
            "app_version": APP_VERSION,
            "schema_version": DB_SCHEMA_VERSION,
        }

        # DB Check
        from jarvis_ai.db.supabase_client import ping_supabase
        report["database_writable"] = ping_supabase()

        # Storage Check
        storage_dir = self.brain.config.get('paths', {}).get('storage_dir', 'storage/')
        try:
            os.makedirs(storage_dir, exist_ok=True)
            test_file = os.path.join(storage_dir, ".readiness_test")
            with open(test_file, "w") as f: f.write("ok")
            os.remove(test_file)
            report["storage_writable"] = True
        except Exception:
            report["storage_writable"] = False

        # Secret Check
        report["secret_configured"] = bool(self.brain.config.get('security_token'))

        # Lock Check
        lock_info = RuntimeLock.check_active()
        report["runtime_lock"] = lock_info

        # LLM Check
        from jarvis_ai.llm.router import _get_saved_model, FALLBACK_CHAIN
        report["llm_mode"] = _get_saved_model() or FALLBACK_CHAIN[0][1]

        # Web Automation Check
        report["web_automation_enabled"] = self.brain.config.get('capabilities', {}).get('web_automation', {}).get('enabled', False)

        # Google Integration Check
        google_status = "available"
        if self.brain.google_degraded_reason:
            google_status = "degraded" if self.brain.google_degraded_reason not in ["disabled_by_config", "dependencies_missing"] else "unavailable"
            
        report["google_integration"] = {
            "status": google_status,
            "reason": self.brain.google_degraded_reason,
            "gmail": bool(self.brain.gmail),
            "calendar": bool(self.brain.calendar)
        }

        # â”€â”€ Phase 8 Voice Readiness â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if hasattr(self.brain, "voice") and hasattr(self.brain.voice, "get_capabilities"):
            voice_caps = self.brain.voice.get_capabilities()
            report["voice_subsystem"] = voice_caps
        else:
            report["voice_subsystem"] = {"enabled": False, "error": "Module missing"}

        # Overall Status
        critical_ok = all([report["database_writable"], report["storage_writable"], report["secret_configured"]])
        report["overall"] = "ready" if critical_ok else "degraded"
        
        # Integration Manifest (RC1)
        report["manifest"] = {
            "web_safety_heuristics": True,
            "policy_firewall_active": True,
            "audit_logging": True
        }

        self._send_json(report)

    # â”€â”€ Phase 8 Voice Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _handle_voice_capabilities(self, auth):
        """GET /voice/capabilities. Public-info endpoint."""
        caps = self.brain.voice.get_capabilities()
        runtime = self._permission_runtime()
        caps["input_permission"] = self.brain.permissions.get_permission(
            "voice.input",
            runtime=runtime,
            auth_context=auth,
            user_agent=self._user_agent(),
        )
        caps["output_permission"] = self.brain.permissions.get_permission(
            "voice.output",
            runtime=runtime,
            auth_context=auth,
            user_agent=self._user_agent(),
        )
        self._send_json(caps)

    def _handle_voice_transcribe(self, auth):
        """POST /voice/transcribe. Accept audio upload, return text."""
        try:
            fields = self._parse_multipart()
            if 'audio' not in fields:
                self._send_json({"error": "Missing 'audio' file in multipart form"}, 400)
                return
            
            audio_field = fields['audio']
            # audio_field might be a list if multiple files sent? cgi handles this.
            if isinstance(audio_field, list):
                audio_field = audio_field[0]

            audio_bytes = audio_field['content']
            mime_type   = audio_field['type']
            filename    = audio_field['filename']

            result = self.brain.voice.transcribe(audio_bytes, mime_type, filename)
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, 400)

    def _handle_voice_chat(self, auth):
        """POST /voice/chat. Accept audio or text, route to brain.chat."""
        try:
            transcript = None
            metadata   = {}
            request_data = {}

            # 1. Try multipart upload (audio)
            ctype_header = self.headers.get('Content-Type', '')
            ctype, _ = self._parse_header(ctype_header)
            
            if ctype == 'multipart/form-data':
                fields = self._parse_multipart()
                if 'audio' in fields:
                    audio_field = fields['audio']
                    if isinstance(audio_field, list): audio_field = audio_field[0]
                    audio_bytes = audio_field['content']
                    res = self.brain.voice.transcribe(audio_bytes, audio_field['type'], audio_field['filename'])
                    transcript = res['transcript']
                    metadata['stt'] = res
                
                if 'transcript' in fields and not transcript:
                    transcript = fields['transcript']
                    if isinstance(transcript, list): transcript = transcript[0]
                
                if 'tts_reply' in fields:
                    tts_val = fields['tts_reply']
                    if isinstance(tts_val, list): tts_val = tts_val[0]
                    request_data['tts_reply'] = tts_val.lower() == 'true'
            else:
                # 2. Try JSON body (text-only test)
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                request_data = json.loads(body.decode()) if content_length > 0 else {}
                transcript = request_data.get('transcript')

            if not transcript:
                self._send_json({"error": "No transcript or audio provided"}, 400)
                return

            # Safety Screening (Phase 8.6)
            screen = self.brain.voice.screen_transcript(transcript)
            if not screen['safe']:
                metadata['safety_warning'] = screen['warning']

            # 3. Route to Brain
            conv_id = request_data.get('conversation_id', secrets.token_hex(8))
            chat_res = self.brain.chat_with_metadata(conv_id, transcript)
            assistant_text = chat_res.get("reply", "")
            metadata["routing"] = chat_res.get("routing", {})
            
            response = {
                "conversation_id": conv_id,
                "transcript": transcript,
                "assistant_text": assistant_text,
                "metadata": metadata
            }

            # 4. Optional TTS reply
            if request_data.get('tts_reply'):
                if not self.brain.permissions.is_allowed("voice.output", runtime=self._permission_runtime()):
                    metadata["voice_output_blocked"] = "Voice output is disabled. Open Permissions & Access to enable it."
                else:
                    tts_res = self.brain.voice.speak(assistant_text)
                    response["audio_reply"] = tts_res

            self._send_json(response)

        except Exception as e:
            import traceback
            # print rather than logger for now (aligns with rest of server.py)
            print(f"[VOICE] Error in _handle_voice_chat: {traceback.format_exc()}")
            self._send_json({"error": str(e)}, 400)

    def _handle_voice_speak(self, auth, data):
        """POST /voice/speak. Convert text to speech metadata."""
        text = data.get('text')
        fmt  = data.get('format', 'wav')
        if not text:
            self._send_json({"error": "Missing 'text' in JSON body"}, 400)
            return
        
        try:
            res = self.brain.voice.speak(text, fmt)
            self._send_json(res)
        except Exception as e:
            self._send_json({"error": str(e)}, 400)

    def _parse_header(self, line):
        """Replacement for cgi.parse_header."""
        parts = [p.strip() for p in line.split(';')]
        key = parts[0].lower()
        params = {}
        for p in parts[1:]:
            if '=' in p:
                k, v = p.split('=', 1)
                params[k.strip().lower()] = v.strip().strip('"')
        return key, params

    def _parse_multipart(self):
        """Helper to parse multipart/form-data using email.parser."""
        ctype_header = self.headers.get('Content-Type', '')
        ctype, pdict = self._parse_header(ctype_header)
        
        if ctype != 'multipart/form-data':
            raise ValueError(f"Content-Type must be multipart/form-data, got {ctype}")
        
        boundary = pdict.get('boundary')
        if not boundary:
            raise ValueError("Missing boundary in Content-Type")

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        # We need to prepend the headers to the body for email.parser
        payload = f"Content-Type: {ctype_header}\r\n\r\n".encode('ascii') + body
        msg = email.parser.BytesParser().parsebytes(payload)
        
        fields = {}
        for part in msg.get_payload():
            if isinstance(part, str): continue # Should not happen with multipart
            
            disposition = part.get('Content-Disposition', '')
            _, params = self._parse_header(disposition)
            name = params.get('name')
            
            if not name: continue
                
            filename = params.get('filename')
            content = part.get_payload(decode=True)
            mtype = part.get_content_type()
            
            if filename:
                fields[name] = {
                    'filename': filename,
                    'content': content,
                    'type': mtype
                }
            else:
                fields[name] = content.decode('utf-8', errors='replace')
                
        return fields


# â”€â”€â”€ Server Launcher â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class JarvisServer:
    """
    Jarvis mobile bridge server.

    Security model:
    - remote_enabled=False (default): always binds to 127.0.0.1. Safe.
    - remote_enabled=True: REQUIRES behind_reverse_proxy=True.
      Will enforce X-Forwarded-Proto: https on every request.
      Refuses to start if requirements are not met.
    """

    def __init__(self, brain, port=8001, host="127.0.0.1", server_config=None):
        self.brain = brain
        cfg        = server_config or {}

        remote_enabled       = cfg.get('remote_enabled', False)
        behind_proxy         = cfg.get('behind_reverse_proxy', False)
        require_https_proto  = cfg.get('require_https_forwarded_proto', True)
        trusted_proxy_ips    = cfg.get('trusted_proxy_ips', []) or []

        # ── Startup security enforcement ────────────────────────────────────────
        # Allow ENV override: if SERVER_HOST is explicitly set to 0.0.0.0 (e.g. Render),
        # skip the local-only binding restriction so the server can reach the internet.
        env_host_override = os.environ.get('SERVER_HOST', '')
        if not remote_enabled and env_host_override != '0.0.0.0':
            # Force local-only binding regardless of configured host
            host = '127.0.0.1'
        elif remote_enabled and not behind_proxy and env_host_override != '0.0.0.0':
            raise RuntimeError(
                "[JARVIS] STARTUP REFUSED: server.remote_enabled=true but "
                "server.behind_reverse_proxy=false. Jarvis will NOT bind to a "
                "public interface without a TLS-terminating reverse proxy. "
                "Set behind_reverse_proxy: true and configure Caddy/Nginx/Cloudflare Tunnel."
            )
        elif remote_enabled:
            print("!" * 70)
            print("[JARVIS] REMOTE ACCESS ENABLED — ensure TLS reverse proxy is active.")
            print("[JARVIS] Jarvis does NOT implement native TLS. Use Caddy or Cloudflare Tunnel.")
            print("!" * 70)

        self.port = port
        self.host = host

        # â”€â”€ Inject config into handler â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self.handler = JarvisRequestHandler
        self.handler.brain                  = brain
        self.handler.server_start_time      = time.time()
        self.handler._remote_enabled        = remote_enabled
        self.handler._behind_reverse_proxy  = behind_proxy
        self.handler._require_https_proto   = require_https_proto
        self.handler._trusted_proxy_ips     = list(trusted_proxy_ips)

        socketserver.ThreadingTCPServer.allow_reuse_address = True
        self.httpd = socketserver.ThreadingTCPServer((self.host, self.port), self.handler)
        self.server_thread = threading.Thread(target=self.httpd.serve_forever)
        self.server_thread.daemon = True

    def start(self):
        self.server_thread.start()
        print(f"[SERVER] Jarvis bridge running on http://{self.host}:{self.port}", flush=True)

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


# ————————————————————————————————————————————————————————————————————————————————
if __name__ == "__main__":
    import yaml

    # Load .env BEFORE reading config so JARVIS_SECRET_TOKEN is available
    # (Already loaded at top of file for early imports)


    config_path = os.path.join(_jarvis_root, 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Execute Phase 7.4 Startup Validation
    from jarvis_ai.core.startup_validator import validate_startup, print_startup_summary
    from jarvis_ai.core.version import APP_VERSION, DB_SCHEMA_VERSION
    from jarvis_ai.core.runtime_lock import RuntimeLock
    import signal

    # Runtime lock â€” prevent duplicate instances
    _lock = RuntimeLock()
    try:
        _lock.acquire()
    except RuntimeError as e:
        print(str(e))
        sys.exit(1)

    # Boot the main reasoning engine and DB memory connection
    from jarvis_ai.core.brain import Brain
    brain = Brain(config=config)

    # Validates DB writeability, Storage, LLM mappings, KillSwitches, and Secret. Exits on failure.
    validate_startup(config, brain.memory_engine)
    db_path = getattr(brain.memory_engine, 'db_path', 'unknown')
    print_startup_summary(config, APP_VERSION, DB_SCHEMA_VERSION, db_path)

    srv_cfg = config.get('server', {})
    PORT = int(os.environ.get('PORT',
               os.environ.get('SERVER_PORT', 8001)))
    HOST = os.environ.get('SERVER_HOST', '0.0.0.0')

    print("Axis AI OS starting...", flush=True)
    print(f"Port: {PORT}", flush=True)
    print("Database: Supabase", flush=True)
    print("LLM providers: groq, openrouter, huggingface, anthropic", flush=True)
    print("Owner token: configured", flush=True)
    print(f"Ready at http://{HOST}:{PORT}/ui", flush=True)

    if not os.environ.get('GROQ_API_KEY'): print("WARNING: GROQ_API_KEY not set - provider disabled", flush=True)
    if not os.environ.get('OPENROUTER_API_KEY'): print("WARNING: OPENROUTER_API_KEY not set - provider disabled", flush=True)
    if not os.environ.get('HUGGINGFACE_API_KEY'): print("WARNING: HUGGINGFACE_API_KEY not set - provider disabled", flush=True)
    if not os.environ.get('ANTHROPIC_API_KEY'): print("WARNING: ANTHROPIC_API_KEY not set - provider disabled", flush=True)

    server = JarvisServer(brain, port=PORT, host=HOST, server_config=srv_cfg)
    server.start()

    def _shutdown(signum, frame):
        print(f"\n[SERVER] Shutdown signal received ({signum}). Stopping gracefully...")
        import traceback
        traceback.print_stack(frame)
        server.stop()
        try:
            _lock.release()
        except Exception:
            pass
        print("[SERVER] Shutdown complete.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    try:
        signal.signal(signal.SIGTERM, _shutdown)
    except (OSError, AttributeError):
        pass  # SIGTERM not available on all Windows configs

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        _shutdown(0, None)

