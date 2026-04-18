# Jarvis AI Project Runbook

## Setup Instructions

1.  **Environment Configuration**:
    *   Copy `.env.example` to `.env`.
    *   Fill in the required keys in `.env`, specifically `LLM_API_KEY` and `JARVIS_SECRET_TOKEN`.
    *   Ensure `JARVIS_SECRET_TOKEN` is a secure 64-character string (or matches your configuration).

2.  **Dependencies**:
    *   Install required Python packages:
        ```bash
        pip install -r requirements.txt
        ```
    *   **Phase 6 (Web Automation)**:
        ```bash
        pip install playwright
        python -m playwright install
        ```

3.  **Project Structure**:
    *   Ensure the following directories exist:
        *   `logs/`
        *   `storage/` (Used for long-term persistence)
        *   `data/` (Used for temporary or demo data)

### Chat & Conversation (Phase 3)
The Jarvis Brain now supports stateful conversations with memory.
- **Run Chat Self-Test**:
  ```powershell
  python scripts/conversation_self_test.py
  ```
- **Session Management**: Each chat session has an ID. History is automatically persisted and summarized every few turns.
- **Long-term Memory**: Strategic info is stored in searchable FTS5 tables for cross-session retrieval.
- **Explicit Memory Policy**: By default, Jarvis only saves long-term memories when explicitly commanded (e.g., "remember this: ...").

### Google Integration (Phase 4)
Jarvis now integrates with Gmail and Google Calendar with a mandatory approval workflow.

- **Setup**:
  1. Go to [Google Cloud Console](https://console.cloud.google.com/).
  2. Create a project and enable **Gmail API** and **Google Calendar API**.
  3. Configure OAuth Consent Screen (External/Testing).
  4. Create **OAuth 2.0 Client ID** (Desktop Application) and download `credentials.json` to the project root.
  5. Run the setup script:
     ```powershell
     python scripts/google_oauth_setup.py
     ```
     > [!IMPORTANT]
     > If you change scopes in `settings.yaml` (e.g. enabling `allow_modify`), you MUST re-run this setup script and re-authenticate in the browser to update your local tokens.

- **Approval Queue**: All sensitive actions (sending email, creating events) are queued as `pending`.
  - List pending: `curl http://127.0.0.1:8000/actions?status=pending -H "X-Jarvis-Token: YOUR_SECRET"`
  - Approve: `curl -X POST http://127.0.0.1:8000/actions/<ID>/approve -H "X-Jarvis-Token: YOUR_SECRET"`
  - Execute: `curl -X POST http://127.0.0.1:8000/actions/<ID>/execute -H "X-Jarvis-Token: YOUR_SECRET"`

- **Google Degraded Mode**:
  Jarvis is designed to boot successfully even if Google integrations are unavailable.
  - **Symptoms**: `GET /control/readiness` reports `status: degraded`.
  - **Behavior**: Gmail/Calendar endpoints return `503 Service Unavailable`.
  - **Recovery**: Refer to the **Google Recovery Guide** below if you need to restore functionality.

### Google Recovery Guide (Re-authentication)
If your Google token has expired or been revoked, follow these steps to restore Gmail and Calendar:
1. **Locate Token**: The token is stored at `storage/google_token.json`.
2. **Delete Old Token**: 
   ```powershell
   Remove-Item storage/google_token.json -Force
   ```
3. **Re-authenticate**: Run the setup script and follow the browser prompt:
   ```powershell
   python scripts/google_oauth_setup.py
   ```
4. **Verify**: Restart Jarvis and check `http://localhost:8000/control/readiness`.

### API Reference (v1.2.0)
All endpoints require `X-Jarvis-Token`.

- **Gmail Inbox**:
  ```bash
  curl http://127.0.0.1:8000/gmail/inbox?limit=5 -H "X-Jarvis-Token: YOUR_SECRET"
  ```
- **Draft Reply**:
  ```bash
  curl -X POST http://127.0.0.1:8000/gmail/draft_reply \
    -H "X-Jarvis-Token: YOUR_SECRET" \
    -H "Content-Type: application/json" \
    -d '{"message_id": "MSG_ID", "instructions": "Say I will be 5 mins late"}'
  ```
- **Propose Meeting**:
  ```bash
  curl -X POST http://127.0.0.1:8000/calendar/propose_event \
    -H "X-Jarvis-Token: YOUR_SECRET" \
    -H "Content-Type: application/json" \
    -d '{"title": "Sync", "start": "2026-02-16T10:00:00Z"}'
  ```

## Running the System

1.  **Start the Brain (Mock Mode)**:
    *   You can start the main reasoning engine using:
        ```bash
        python main.py
        ```
        *(Note: If `main.py` is not present, use the provided demo scripts like `production_pilot_live.py`.)*

2.  **Start the Mobile Bridge Server**:
    *   Run the server module directly:
        ```bash
        python -m jarvis_ai.mobile.server
        ```
    *   The server will run on `http://127.0.0.1:8000`.

3.  **Verification**:
    *   Run the smoke test to ensure everything is configured correctly:
        ```bash
        python scripts/smoke_test.py
        ```

## Architecture Overview

*   **Core**: Contains the `Brain` and specialized engines (Governance, Security, Stabilization, etc.).
*   **Mobile**: Contains the bridge server for external interactions.
*   **Memory**: Manages short-term and long-term persistence via SQLite.
*   **Tools**: Contains modular toolsets for system, web, and mobile operations.

---

## Expose Jarvis Securely Over the Internet (Phase 5)

> [!CAUTION]
> Remote access is **OFF by default** (`remote_enabled: false`). Never expose Jarvis directly over HTTP. Always terminate TLS at the reverse proxy.

### Prerequisites

Before enabling remote access, update `jarvis_ai/config/settings.yaml`:

```yaml
server:
  bind_host: "127.0.0.1"            # Keep local binding — proxy handles external
  port: 8000
  remote_enabled: true               # Enable remote mode
  behind_reverse_proxy: true         # REQUIRED when remote_enabled: true
  require_https_forwarded_proto: true
  trusted_proxy_ips: ["127.0.0.1"]   # IP of your proxy (if running locally)
```

If `remote_enabled: true` without `behind_reverse_proxy: true`, Jarvis **refuses to start**.

---

### Option A — Caddy Reverse Proxy (Automatic HTTPS)

[Caddy](https://caddyserver.com/) automatically obtains and renews TLS certificates via Let's Encrypt.

**1. Install Caddy** (Windows):
```powershell
winget install Caddy.Caddy
```

**2. Create a `Caddyfile`** in your project root:
```
your-domain.com {
    reverse_proxy 127.0.0.1:8000

    # Security headers
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
    }
}
```

Replace `your-domain.com` with your actual domain (must point to your server's IP).

**3. Start Caddy**:
```powershell
caddy run --config Caddyfile
```

Caddy will handle TLS automatically. Jarvis stays on `127.0.0.1:8000` (never exposed raw).

---

### Option B — Cloudflare Tunnel (No Open Port Required)

[Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) creates an outbound-only encrypted tunnel — no firewall rules, no exposed ports.

**1. Install `cloudflared`**:
```powershell
winget install Cloudflare.cloudflared
```

**2. Authenticate and create a tunnel**:
```bash
cloudflared tunnel login
cloudflared tunnel create jarvis-tunnel
```

**3. Configure the tunnel** (`.cloudflared/config.yml`):
```yaml
tunnel: jarvis-tunnel
credentials-file: C:\Users\YOU\.cloudflared\<TUNNEL_ID>.json

ingress:
  - hostname: jarvis.your-domain.com
    service: http://127.0.0.1:8000
  - service: http_status:404
```

**4. Route DNS and run**:
```bash
cloudflared tunnel route dns jarvis-tunnel jarvis.your-domain.com
cloudflared tunnel run jarvis-tunnel
```

Cloudflare terminates TLS. All traffic to Jarvis arrives as HTTP on `127.0.0.1:8000` with `X-Forwarded-Proto: https` set automatically.

Update `trusted_proxy_ips` in settings.yaml to Cloudflare's IP ranges if you want strict forwarded-for validation.

---

### Security Checklist Before Going Live

- [ ] `JARVIS_SECRET_TOKEN` is a cryptographically random 64-char hex string (not the default)
- [ ] `remote_enabled: true` and `behind_reverse_proxy: true` in settings.yaml
- [ ] TLS is terminated by Caddy or Cloudflare (not Jarvis directly)
- [ ] `google.gmail.send_enabled: false` unless you need automated email sending
- [ ] Reviewed `activity_log` to confirm no secrets are logged
- [ ] Mobile device tokens stored securely on devices (OS keychain, not plaintext)

---

## Phase 5 Verification Runbook (Windows + Tailscale + iPhone)

### 1. Start the Server
In PowerShell:
```powershell
python -m jarvis_ai.mobile.server
```
Verify locally: `GET http://127.0.0.1:8000/health` (should return 200 OK).

### 2. Tailscale Serve (Expected Pattern)
To expose your local port 8000 over Tailscale with HTTPS:
```bash
tailscale serve 8000
```
- **Confirm Status**: `tailscale serve status`
- **Stop Serving**: `tailscale serve --off`
- **Verification**: Open the Tailscale HTTPS URL in a local browser (e.g., `https://your-machine.tailscale.net/health`).

### 3. iPhone Testing (3 Options)
1. **Safari Test**: Open your Tailscale HTTPS URL. You should see "Jarvis Bridge is Running".
2. **iOS Shortcuts**: 
   - Add "Get contents of URL" action.
   - URL: `https://your-machine.tailscale.net/whoami`
   - Method: `GET`
   - Headers: `X-Device-Token: YOUR_DEVICE_TOKEN`
3. **iSH / Termius (curl)**:
   ```bash
   curl https://your-machine.tailscale.net/whoami -H "X-Device-Token: YOUR_TOKEN"
   ```

### 4. Pairing & Registration
1. **Generate Pairing Code** (Owner on PC): 
   ```bash
   curl -X POST http://127.0.0.1:8000/pairing/code -H "X-Jarvis-Token: YOUR_OWNER_TOKEN" -d "{\"role\":\"operator\",\"name\":\"MyiPhone\"}"
   ```
2. **Register from Phone**:
   ```bash
   curl -X POST https://your-machine.tailscale.net/pairing/register -H "Content-Type: application/json" -d "{\"code\":\"CODE_FROM_STEP_1\",\"device_name\":\"iPhone\"}"
   ```
3. **Verify**: Use the returned `device_token` to call `/whoami`.

### 5. Troubleshooting
- **401 Unauthorized**: Check your `X-Jarvis-Token` (owner) or `X-Device-Token` (device) header names and values.
- **403 Forbidden**: Your device role may be insufficient for the requested endpoint or the device has been revoked.
- **Tailscale HTTPS Errors**: Ensure Tailscale is running and `tailscale serve` is active. Check `X-Forwarded-Proto` is correctly handled by the proxy.

---

## Phase 6 — Safe Web Automation

Jarvis now includes a safe-by-default web automation engine powered by Playwright.

### Features
- **Governance**: Every "commit" action is queued for human approval.
- **Safety Heuristics**: Automatically detects and blocks on CAPTCHAs, login forms, and payment fields.
- **Kill-Switch**: `web_automation.enabled: false` by default in `settings.yaml`.

### Usage Flow

1. **Propose a Plan**:
   ```bash
   curl -X POST http://127.0.0.1:8000/web/propose \
     -H "X-Jarvis-Token: YOUR_SECRET" \
     -H "Content-Type: application/json" \
     -d '{
       "objective": "Get the price of a product",
       "plan": {
         "start_url": "https://example.com/product",
         "steps": [
           {"action": "goto", "url": "https://example.com/product"},
           {"action": "extract", "selector": ".price", "name": "price"}
         ]
       }
     }'
   ```

2. **Approve Action**:
   Use the `/actions?status=pending` endpoint to find the `action_id`, then hit `/actions/<ID>/approve`.

3. **Execute Action**:
   ```bash
   curl -X POST http://127.0.0.1:8000/web/actions/<ID>/execute \
     -H "X-Jarvis-Token: YOUR_SECRET"
   ```

4. **Retrieve Results**:
   ```bash
   curl http://127.0.0.1:8000/web/actions/<ID>/result \
     -H "X-Jarvis-Token: YOUR_SECRET"
   ```

### Self-Test
Run the local web automation test suite:
```powershell
python scripts/web_automation_self_test.py
```

## Phase 6.1 Web Automation Safety Rules

To ensure Jarvis behaves safely during background web automation, strict rules and heuristics are enforced at both the API level and the browser execution level.

### What the Engine Can Do
- Navigate to `http`/`https` URLs.
- Click elements via selectors.
- Type text into inputs.
- Extract text content from the page, which goes through an automatic heuristic redaction pass to mask passwords, emails, and API keys.
- Take screenshots and return them via the result endpoint.

### What It Refuses To Do
Jarvis outright blocks or refuses the following actions to eliminate massive risk vectors:
- Navigation to internal or non-HTTP schemes.
- **CAPTCHA Bypass**: Execution stops immediately if CAPTCHAs are detected.
- **Login Automation**: Execution stops if password fields are detected.
- **Payments**: Execution stops if payment-related keywords or fields are detected.
- **File Uploads**: Execution immediately aborts if a file chooser event is triggered or if uploading files is attempted.
- **File Downloads**: Playwright is configured to reject explicitly all download attempts.

### The Execution Flow
Web automation relies on a strict REST lifecycle:
1. **Propose (`POST /web/propose`)**: Sends the JSON automation plan. The server validates the allowed actions (`goto`, `click`, `type`, `extract`, `screenshot`) and enforces bounds (max 30 steps, 30s timeout). The server also analyzes the plan for `has_commit_risk`.
2. **Approve (`POST /actions/approve`)**: An operator must explicitly approve the returned `action_id`.
3. **Execute (`POST /web/actions/<id>/execute`)**: Triggers the headless browser. If a **commit-risk** step is encountered, execution will halt *before* clicking the dangerous element, returning a `partial` execution status.
4. **Result (`GET /web/actions/<id>/result`)**: Can be polled to fetch the execution outcome, sanitized extracted data, and screenshot paths.

### Commit-Risk Behavior
Any proposed click on a button/selector matching keywords like `submit`, `apply`, `checkout`, `purchase`, `order`, or `confirm` is flagged as a `commit_risk`.
During execution (`/execute`), Jarvis will run the preceding steps (like filling out a draft form) but will **stop right before** clicking the risky submit button, returning a `commit_confirmation_required` block reason. This ensures side-effects aren't triggered blindly.

### Running Local Tests
You can verify the safety rules (including login block, commit-risk stop, upload blocks, and invalid plan rejection) using the built-in, local-only test script:
```powershell
python scripts/web_automation_self_test.py
```

---

## Phase 7.1: Goal Reconciliation & Resume

### Why Goals Pause

When Jarvis encounters a goal step requiring external action (e.g., web automation, email sending), it creates a **pending action** and places the goal in `awaiting_approval` state. The goal will not continue until that action is explicitly approved and executed. This is intentional — no side-effects are triggered without explicit human authorization.

### Status Meanings

| Status | Meaning |
|---|---|
| `draft` | Goal created, no plan yet |
| `planned` | Plan generated, ready to advance |
| `active` | Currently executing a step |
| `awaiting_approval` | Paused, waiting for a pending action to be approved/executed |
| `blocked` | A step was rejected or blocked by a safety gate |
| `failed` | A step failed irrecoverably |
| `completed` | All steps finished successfully |

### How Approvals Feed Back into Goals

1. Approve a pending action via `POST /actions/<id>/approve`
2. Execute via `POST /actions/<id>/execute`
3. **Reconcile** the goal via `POST /goals/<id>/reconcile` — Jarvis inspects the linked action and updates the step + goal status automatically
4. Alternatively, call `POST /goals/<id>/resume` to reconcile AND continue advancing in one call

### API Reference: Reconciliation & Resume

**Reconcile a goal** (sync states from pending_action outcomes):
```bash
curl -X POST http://127.0.0.1:8000/goals/<GOAL_ID>/reconcile \
  -H "X-Jarvis-Token: YOUR_SECRET"
```

**Resume a goal** (reconcile + advance next eligible step):
```bash
curl -X POST http://127.0.0.1:8000/goals/<GOAL_ID>/resume \
  -H "X-Jarvis-Token: YOUR_SECRET"
```

**Inspect goal event history**:
```bash
curl http://127.0.0.1:8000/goals/<GOAL_ID>/events \
  -H "X-Jarvis-Token: YOUR_SECRET"
```

**Rich goal summary** (includes `can_resume`, `waiting_approvals`, `result_refs`, `last_event`):
```bash
curl http://127.0.0.1:8000/goals/<GOAL_ID>/summary \
  -H "X-Jarvis-Token: YOUR_SECRET"
```

**Bulk reconcile all active goals** (owner only):
```bash
curl -X POST http://127.0.0.1:8000/goals/reconcile_all \
  -H "X-Jarvis-Token: YOUR_SECRET"
```

### Safety Block Behavior

If a web execution step is blocked by a safety gate (login detected, CAPTCHA, payment form, file upload, commit-risk), the step status becomes `blocked` with an explicit `blocked_reason`. The goal also becomes `blocked`. The `summary` endpoint surfaces the exact reason so you know what halted execution.

### Running Local Tests
```powershell
python scripts/goal_reconciliation_self_test.py
```

---

## Phase 7.2: LLM Goal Planning & Policy Firewall

Jarvis now features a multi-step goal planner powered by LLM advisory providers, protected by a strict policy firewall.

### Features
- **Multi-Step Generation**: Decomposes vague objectives (e.g., "Research and summarize renewable energy") into 3-8 actionable steps.
- **LLM-First Planning**: Prioritizes using the configured LLM provider for flexible planning, with a deterministic fallback for reliability.
- **Policy Firewall**: Automatically rejects or sanitizes plans involving CAPTCHA bypass, login automation, payment automation, or deceptive behavior.
- **Provenance Tracking**: Every plan tracks its `planner_type` (llm/fallback), `planner_provider`, and any safety warnings.
- **Replan Flow**: Discards current draft/pending steps and generates a fresh plan via the `replan` endpoint.

### API Reference: Planning & Replan

**Create and Auto-plan a goal** (via Brain):
When adding a goal via the chat interface (`add a goal: ...`), Jarvis automatically triggers the multi-step planner.

**Trigger a Replan** (discard pending steps and generate new):
```bash
curl -X POST http://127.0.0.1:8000/goals/<GOAL_ID>/replan \
  -H "X-Jarvis-Token: YOUR_SECRET"
```

**Inspect Planner Provenance** (via Summary):
```bash
curl http://127.0.0.1:8000/goals/<GOAL_ID>/summary \
  -H "X-Jarvis-Token: YOUR_SECRET"
```
Look for `planner_type`, `planner_provider`, and `planner_warnings` in the JSON response.

### Safety & Fallback
If the LLM generates a plan with unsafe steps (e.g., "Login to my account"), Jarvis will:
1. **Downgrade** specific unsafe steps to `manual` type with a warning.
2. **Reject** the entire plan and use the **Safe Fallback Planner** if fundamental violations (e.g., CAPTCHA bypass) are found.

### Running Local Tests
Verify the LLM planner, policy firewall, and fallback logic:
```powershell
python scripts/goal_llm_planner_self_test.py
```

---

## Phase 7.3: Control Plane API

Jarvis now includes a centralized Control Plane API designed to serve mobile apps, web dashboards, and integrated frontends with a concise, unified status view of the entire system.

### Features
- **Summary Surface (`GET /control/summary`)**: A lightweight endpoint that returns system health, version, role (Owner vs Device), top-level counts (active goals, blocked goals, pending actions), limited recent events, and immediate recommended actions.
- **Approvals Surface (`GET /control/approvals`)**: Returns `pending` actions enriched with parent goal references and human-readable context.
- **Blocked Surface (`GET /control/blocked`)**: Returns items explicitly marked as blocked by safety constraints (e.g., CAPTCHA, Commit Risk), with linked reasons.
- **Results Surface (`GET /control/results`)**: Returns successfully completed actions that have generated artifacts, summaries, or extracted web data (`result_ref`).

### Role-Based Access Control (RBAC)
- **Owner-Level Access (`X-Jarvis-Token`)**: Full visibility into all pending approvals, active goals, and system versions. Read/Write access.
- **Device-Level Access (`X-Device-Token`)**: Redacted summary visibility. System versions are masked, and details regarding specific goals or blocked items might be filtered depending on the configuration.

### API Reference: Control Plane

**Get Unified Summary (Dashboard Snapshot):**
```bash
curl http://127.0.0.1:8000/control/summary \
  -H "X-Jarvis-Token: YOUR_SECRET"
```

**Get Pending Approvals (Actionable Queue):**
```bash
curl http://127.0.0.1:8000/control/approvals?limit=10 \
  -H "X-Jarvis-Token: YOUR_SECRET"
```

**Get Blocked Items (Intervention Needed):**
```bash
curl http://127.0.0.1:8000/control/blocked?limit=10 \
  -H "X-Jarvis-Token: YOUR_SECRET"
```

**Get Recent Results (Outcome Delivery):**
```bash
curl http://127.0.0.1:8000/control/results?limit=10 \
  -H "X-Jarvis-Token: YOUR_SECRET"
```

### Running Local Tests
Verify the memory schema integrations, endpoints, and RBAC visibility:
```powershell
python scripts/control_plane_self_test.py
```

---

## Phase 7.4: Release Candidate Operations

This section documents the operational procedures for running Jarvis reliably on Windows 11.

### Canonical Auth Format

| Header | Role | Notes |
|---|---|---|
| `X-Jarvis-Token: YOUR_SECRET` | **Owner** | Canonical. Use this in all scripts and docs. |
| `X-Device-Token: YOUR_DEVICE_TOKEN` | **Device** | Canonical. Issued after pairing flow. |
| `Authorization: Bearer YOUR_SECRET` | Owner (Deprecated) | Accepted but logs a warning. Migrate away from this. |

All owner endpoints return `403 Forbidden` if only a device token is provided.  
The `/whoami` endpoint returns `"auth_method"` in its response to diagnose which header was used.

### Startup Steps (Windows)

```powershell
# 1. Ensure .env is present with JARVIS_SECRET_TOKEN set
# 2. Start server:
.\scripts\start_jarvis.ps1
# OR run directly for foreground/debug mode:
python -m jarvis_ai.mobile.server
```

On startup, Jarvis automatically:
- Validates the config (secret, DB path, storage writability, kill-switch types)
- Acquires a PID lock at `storage/runtime/jarvis.pid`
- Prints a safe startup summary (no secrets)

### Shutdown Steps

```powershell
.\scripts\stop_jarvis.ps1
# OR press Ctrl+C if running in foreground
```

Jarvis handles `SIGINT`/`SIGTERM` by flushing DB writes, releasing the lockfile, then exiting.

### Readiness Check

```powershell
# Local script (no server needed):
python scripts/release_readiness_check.py

# Via HTTP (server must be running):
curl http://127.0.0.1:8000/control/readiness -H "X-Jarvis-Token: YOUR_SECRET"
```

Both return a structured report with `overall: ready | degraded | blocked`.

### Backup Steps

```powershell
python scripts/backup_jarvis.py "optional note"
# Backup saved to: storage/backups/YYYYMMDD_HHMMSS_backup.zip
```

### Restore Steps

> [!CAUTION]
> Stop the server before restoring. This will overwrite the current database.

```powershell
.\scripts\stop_jarvis.ps1
python scripts/restore_jarvis.py storage/backups/20260307_HHMMSS_backup.zip --yes
```

### Export Status Snapshot (for support/debugging)

```powershell
python scripts/export_status_snapshot.py snapshot.json
```

Outputs a JSON file with goal counts, pending approvals, and recent results. No secrets included.

### Duplicate Server Recovery

If Jarvis fails to start with a duplicate server error:

```
[JARVIS] DUPLICATE INSTANCE DETECTED: Another Jarvis server process (PID 12345) ...
```

Recovery:
```powershell
.\scripts\stop_jarvis.ps1         # Uses lockfile PID to kill process
# OR manually:
taskkill /PID 12345 /F
Remove-Item storage\runtime\jarvis.pid -Force
```

### Status Check (Quick)

```powershell
.\scripts\check_jarvis.ps1 YOUR_OWNER_TOKEN
```

Shows PID state + HTTP health + readiness report in one call.

### Common Operational Failures

| Symptom | Likely Cause | Fix |
|---|---|---|
| `STARTUP REFUSED: remote_enabled without behind_reverse_proxy` | Config mismatch | Set `behind_reverse_proxy: true` |
| `JARVIS_SECRET_TOKEN is not set` | Missing env var | Add it to `.env` file |
| `DUPLICATE INSTANCE DETECTED` | Stale or live PID | Run `stop_jarvis.ps1` |
| `403 Forbidden` on all requests | Wrong auth header | Use `X-Jarvis-Token` not `Authorization: Bearer` |
| `DB health check failed` | Corrupt or locked `.db` | Restore from backup |
| Port 8000 in use | Another process bound | `netstat -ano | findstr :8000` → kill offender |

### Running Local Tests

```powershell
python scripts/production_hardening_self_test.py
```
---

## Phase 9 — Launch Dashboard MVP

Jarvis now includes a lightweight, browser-based Operator Dashboard for monitoring and control.

### Features
- **Overview**: Real-time snapshot of system health, active goals, and pending approvals.
- **Goals**: Create, plan, and manage multi-step goals with full event history.
- **Approvals**: A unified queue for inspecting and acting on pending system actions.
- **Blocked/Results**: Visibility into why execution halted and access to generated outcomes.
- **Voice**: Browser-side push-to-talk for voice-driven interaction.

### How to Access
1. **Start the Server**: 
   ```powershell
   python -m jarvis_ai.mobile.server
   ```
2. **Open the UI**: Navigate to `http://localhost:8000/ui` in your browser.
3. **Login**: 
   - **Mode**: Choose `Owner` or `Device`.
   - **Token**: Enter your `JARVIS_SECRET_TOKEN` (for owner) or a registered device token.

### Auth & Session
The dashboard stores your token in **sessionStorage** for security (cleared when you close the tab). You can explicitly log out via the dashboard sidebar.

### Browser Push-to-Talk
To use voice features, click **Allow** when your browser requests microphone access.
- **Push-to-Talk**: Hold the microphone button to record, release to transcribe and send.
- **Text Fallback**: Use the text input area if a microphone is not available or supported.

### Verification (Playwright)
Verify the dashboard UI components and auth flow:
```powershell
python scripts/dashboard_ui_self_test.py
```

---

## RC1 — Launch Candidate Hardening

Jarvis has reached **Release Candidate 1 (RC1)**. This milestone ensures system cohesion, end-to-end reliability, and demo-readiness.

### Quick Start (RC1)
1. **Start Server**: `python -m jarvis_ai.mobile.server`
2. **Access Dashboard**: `http://localhost:8000/ui` (Works over Tailscale/Remote URLs)
3. **Login**: Use canonical `Owner` token.

### Demo & Seed Tooling
To quickly populate Jarvis with sample data for a demonstration:
```powershell
python scripts/seed_demo_state.py
```
This adds:
- 3 sample goals (Active, Blocked, Draft)
- 1 pending approval (High-risk branding action)
- 1 recently generated result

### Release Checklist
Verify your local environment is ready for deployment:
```powershell
python scripts/rc1_release_checklist.py
```

### End-to-End Validation
Run the full-stack automated journey test (Owner Auth -> Goal Create -> Voice Chat):
```powershell
python scripts/rc1_e2e_acceptance_test.py
```

### Remote / Tailscale Usage
- The dashboard automatically uses **relative API paths**. No configuration is needed when accessing via `tailscale-ip:8000/ui`.
- **Browser Mic**: Requires HTTPS for remote voice push-to-talk. Localhost overrides this.
- **Troubleshooting**:
  - `401/403`: Check your `JARVIS_SECRET_TOKEN` environment variable.
  - `Network Error`: Ensure the Python server is bound to `0.0.0.0` or Tailscale IP if accessing remotely.

---

---
