import os
import sys
import logging

logger = logging.getLogger(__name__)

def validate_startup(config: dict, memory_engine):
    """
    Validates Jarvis configuration and environment before boot.
    Raises SystemExit if issues are detected to prevent starting in a broken state.
    """
    errors = []

    # 1. Secret Token
    secret = os.environ.get('JARVIS_SECRET_TOKEN') or config.get('security_token')
    if not secret:
        errors.append("FATAL: JARVIS_SECRET_TOKEN is not set.")
    elif len(secret) < 32 and secret != "dev_secret_token_123":
        errors.append("WARNING: JARVIS_SECRET_TOKEN is suspiciously short. It should be a strong secret.")

    # 2. Storage Directory
    storage_dir = os.path.join(os.getcwd(), 'storage')
    if not os.path.exists(storage_dir):
        try:
            os.makedirs(storage_dir, exist_ok=True)
        except Exception as e:
            errors.append(f"FATAL: Cannot create storage directory at {storage_dir}. {e}")
    elif not os.access(storage_dir, os.W_OK):
         errors.append(f"FATAL: Storage directory {storage_dir} is not writable.")

    # 3. Database Write Access
    try:
        from jarvis_ai.db.supabase_client import ping_supabase
        if not ping_supabase():
            raise Exception("Supabase ping returned False.")
    except Exception as e:
        errors.append(f"WARNING: Database connection failed. {e}")

    # 4. Config variables & Kill-switches
    if 'web_automation' in config:
        web_config = config['web_automation']
        if not isinstance(web_config.get('enabled', False), bool):
            errors.append("FATAL: config.web_automation.enabled must be a boolean.")
        
    if 'google' in config and 'gmail' in config['google']:
        if not isinstance(config['google']['gmail'].get('send_enabled', False), bool):
            errors.append("FATAL: config.google.gmail.send_enabled must be a boolean.")

    # 5. LLM Provider (Check basic struct, allow fallback if empty)
    if 'llm' in config:
        # just verify it's a dict if present
        if not isinstance(config['llm'], dict):
             errors.append("FATAL: config.llm must be a dictionary configuration.")


    if errors:
        for err in errors:
            if err.startswith("FATAL"):
                print(f"[STARTUP VALIDATION FAILED] {err}")
            else:
                print(f"[STARTUP WARNING] {err}")
        
        fatal_count = sum(1 for e in errors if e.startswith("FATAL"))
        if fatal_count > 0:
            print("[STARTUP VALIDATION FAILED] Shutting down to prevent broken state.")
            sys.exit(1)
        
    return True

def print_startup_summary(config: dict, app_version: str, schema_version: str, db_path: str):
    """Prints a safe startup summary (no secrets)."""
    storage_path = os.path.join(os.getcwd(), 'storage')
    web_enabled = config.get('capabilities', {}).get('web_automation', {}).get('enabled', False)
    gmail_send = config.get('google', {}).get('gmail', {}).get('send_enabled', False)

    server_config = config.get('server', {})
    remote = server_config.get('remote_enabled', False)
    proxy = server_config.get('behind_reverse_proxy', False)

    print("\n" + "="*50)
    print(f" Jarvis API Boot Summary (v{app_version})")
    print("="*50)
    print(f"• Schema Version  : {schema_version}")
    print(f"• DB Path         : {db_path}")
    print(f"• Storage Path    : {storage_path}")
    print("\n[Capabilities]")
    print(f"• Web Automation  : {'ENABLED' if web_enabled else 'DISABLED'}")
    print(f"• Gmail Send      : {'ENABLED' if gmail_send else 'DISABLED'}")
    print(f"• Remote APIs     : {'ENABLED' if remote else 'LOCAL ONLY'}")
    print(f"• Reverse Proxy   : {'AWARE' if proxy else 'LOCKED'}")
    print("="*50 + "\n")
