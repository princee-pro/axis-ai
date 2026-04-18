import os
import json
import uuid
import time
import re
from datetime import datetime
from pathlib import Path

def redact_sensitive_data(text):
    if not isinstance(text, str):
        return text
    # Redact email addresses
    text = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '[REDACTED_EMAIL]', text)
    # Redact Bearer tokens
    text = re.sub(r'Bearer\s+[A-Za-z0-9\-\._~+/]+=*', 'Bearer [REDACTED_TOKEN]', text)
    # Redact API keys and passwords heuristically
    text = re.sub(r'(?i)(api[_-]?key[\s:=]+)[A-Za-z0-9\-_]{20,}', r'\1[REDACTED_KEY]', text)
    text = re.sub(r'(?i)(password[\s:=]+)[^\s]+', r'\1[REDACTED_PASSWORD]', text)
    return text


try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

class WebAutomationEngine:
    """
    Safe-by-default web automation engine using Playwright.
    Implements heuristics to detect and block risky operations (Login, CAPTCHA, Payment).
    """

    def __init__(self, config):
        self.config = config
        self.enabled = config.get('capabilities', {}).get('web_automation', {}).get('enabled', False)
        self.storage_dir = Path(config.get('paths', {}).get('storage_dir', 'storage/')) / 'web_sessions'
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self):
        return PLAYWRIGHT_AVAILABLE

    def _check_safety(self, page):
        """
        Scan the page for risky elements.
        Returns (is_risky, reason, evidence)
        """
        # 1. CAPTCHA Detection
        captcha_selectors = [
            ".g-recaptcha", ".h-captcha", "#captcha", "iframe[src*='captcha']", 
            "iframe[src*='recaptcha']", ".cf-turnstile"
        ]
        for sel in captcha_selectors:
            if page.locator(sel).count() > 0:
                return True, "captcha", f"Detected CAPTCHA element: {sel}"

        # 2. Login Detection
        login_indicators = ["input[type='password']", "input[name*='password']", "input[id*='password']"]
        for sel in login_indicators:
            if page.locator(sel).count() > 0:
                return True, "login", "Detected password field"

        # 3. Payment Detection
        payment_keywords = ["checkout", "payment", "card-number", "cvv", "credit-card"]
        html_lower = page.content().lower()
        for kw in payment_keywords:
            if kw in html_lower:
                # Better check: is there a button with checkout/pay text?
                return True, "payment", f"Detected payment keyword: {kw}"

        return False, None, None

    def run_plan(self, plan):
        """
        Execute a series of automation steps.
        """
        if not self.enabled:
            return {"status": "error", "error": "Web automation kill-switch is active."}

        if not self.is_available():
            return {"status": "error", "error": "Playwright is not installed on this server."}

        session_id = str(uuid.uuid4())[:8]
        session_path = self.storage_dir / session_id
        session_path.mkdir(parents=True, exist_ok=True)

        results = {
            "session_id": session_id,
            "start_time": datetime.now().isoformat(),
            "steps_executed": [],
            "extracted_data": {},
            "screenshots": [],
            "status": "pending"
        }

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) JarvisAI/1.2.0",
                    accept_downloads=False
                )
                page = context.new_page()

                download_flag = [False]
                upload_flag = [False]

                def handle_download(download):
                    download_flag[0] = True

                def handle_filechooser(file_chooser):
                    upload_flag[0] = True

                page.on("download", handle_download)
                page.on("filechooser", handle_filechooser)

                # Enforce timeout
                timeout = plan.get('constraints', {}).get('timeout_ms', 30000)
                page.set_default_timeout(timeout)

                max_steps = plan.get('constraints', {}).get('max_steps', 30)
                has_commit_risk = plan.get('has_commit_risk', False)
                commit_risk_reasons = plan.get('commit_risk_reasons', [])
                
                for i, step in enumerate(plan.get('steps', [])):
                    if download_flag[0]:
                        results["status"] = "blocked"
                        results["reason"] = "download_blocked"
                        break
                    
                    if upload_flag[0]:
                        results["status"] = "blocked"
                        results["reason"] = "file_upload_blocked"
                        break

                    if i >= max_steps:
                        results["status"] = "blocked"
                        results["reason"] = "max_steps_exceeded"
                        break

                    action = step.get('action')
                    
                    # Commit-Risk Execution Gate
                    if has_commit_risk and action == 'click':
                        sel_lower = step.get('selector', '').lower()
                        commit_keywords = ['submit', 'apply', 'send', 'confirm', 'purchase', 'checkout', 'place', 'order', 'continue-final']
                        if any(kw in sel_lower for kw in commit_keywords) or 'type="submit"' in sel_lower or "type='submit'" in sel_lower:
                            results["status"] = "partial"
                            results["reason"] = "commit_confirmation_required"
                            results["completed_steps"] = len(results["steps_executed"])
                            results["blocked_step_index"] = i
                            results["evidence"] = commit_risk_reasons
                            break

                    try:
                        if action == 'goto':
                            url = step.get('url')
                            if not url.startswith(('http://', 'https://')):
                                raise ValueError("Only http/https allowed")
                            page.goto(url)
                        
                        elif action == 'click':
                            page.click(step.get('selector'))
                        
                        elif action == 'type':
                            page.fill(step.get('selector'), step.get('text'))
                        
                        elif action == 'extract':
                            val = page.inner_text(step.get('selector'))
                            results["extracted_data"][step.get('name')] = redact_sensitive_data(val)
                        
                        elif action == 'screenshot':
                            name = step.get('name', f'step_{i}')
                            path = session_path / f"{name}.png"
                            page.screenshot(path=str(path))
                            results["screenshots"].append(str(path))

                        # Safety Check after every step
                        is_risky, reason, evidence = self._check_safety(page)
                        if is_risky:
                            results["status"] = "blocked"
                            results["reason"] = reason
                            results["evidence"] = evidence
                            results["at_url"] = page.url
                            break

                        results["steps_executed"].append(step)

                    except Exception as step_error:
                        results["status"] = "error"
                        results["error"] = str(step_error)
                        results["failed_at_step"] = i
                        break

                if results["status"] == "pending":
                    results["status"] = "success"

                results["end_time"] = datetime.now().isoformat()
                browser.close()

        except Exception as e:
            results["status"] = "error"
            results["error"] = str(e)

        # Save result to file
        with open(session_path / "result.json", "w") as f:
            json.dump(results, f, indent=2)

        return results
