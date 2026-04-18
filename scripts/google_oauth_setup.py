"""
CLI Script to set up Google OAuth tokens.
"""
import os
import sys
from pathlib import Path

import yaml
from google_auth_oauthlib.flow import InstalledAppFlow

# Add project root to path with priority
PROJECT_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(PROJECT_ROOT))

def _load_settings():
    settings_path = PROJECT_ROOT / "jarvis_ai" / "config" / "settings.yaml"
    if not settings_path.exists():
        return {}
    with settings_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}

def _resolve_path(value, fallback):
    raw = value or fallback
    path = Path(raw)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path

def main():
    print("=== Jarvis AI: Google OAuth Setup ===")

    config = _load_settings()
    google_config = config.get("google", {})
    client_secrets = _resolve_path(
        os.environ.get("GOOGLE_OAUTH_CLIENT_FILE") or google_config.get("client_file"),
        "credentials.json",
    )
    if not client_secrets.exists():
        print(f"ERROR: {client_secrets} not found.")
        print("Please download 'credentials.json' from Google Cloud Console (OAuth 2.0 Client ID) and place it in the configured client path.")
        sys.exit(1)

    token_file = _resolve_path(
        os.environ.get("GOOGLE_OAUTH_TOKEN_FILE") or google_config.get("token_file"),
        "storage/google_token.json",
    )

    merged_config = dict(config)
    merged_google = dict(google_config)
    merged_google["client_file"] = str(client_secrets)
    merged_google["token_file"] = str(token_file)
    merged_config["google"] = merged_google

    print(f"Using client secrets: {client_secrets}")
    print(f"Token will be saved to: {token_file}")
    print(f"Gmail modify enabled: {bool(google_config.get('gmail', {}).get('allow_modify', False))}")
    print(f"Gmail send enabled: {bool(google_config.get('gmail', {}).get('send_enabled', False))}")
    scopes = google_config.get("scopes") or [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.compose",
        "https://www.googleapis.com/auth/calendar.events",
    ]
    print(f"Configured scopes: {', '.join(scopes)}")
    
    try:
        print("Starting OAuth flow (browser will open)...")
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secrets),
            scopes=scopes,
        )
        creds = flow.run_local_server(port=0)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        with token_file.open("w", encoding="utf-8") as handle:
            handle.write(creds.to_json())
        
        if creds and creds.valid:
            print("\n[SUCCESS] Authentication complete.")
            print(f"Tokens saved to {token_file}")
        else:
            print("\n[ERROR] Authentication failed or credentials invalid.")
            
    except Exception as e:
        print(f"\n[CRITICAL ERROR] {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
