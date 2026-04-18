"""
Google Authentication Helper.
Handles OAuth2 flow and token token management for Google APIs.
"""
import os

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

class GoogleAuth:
    def __init__(
        self,
        config=None,
        token_file="storage/google_token.json",
        client_secrets="credentials.json",
        allow_interactive_login=None
    ):
        self.token_file = token_file
        self.client_secrets = client_secrets
        self.allow_interactive_login = (
            str(os.environ.get("JARVIS_GOOGLE_INTERACTIVE_AUTH", "")).strip().lower()
            in {"1", "true", "yes", "on"}
        ) if allow_interactive_login is None else bool(allow_interactive_login)
        
        # Default least-privilege scopes
        self.scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.compose',
            'https://www.googleapis.com/auth/calendar.events'
        ]
        
        if config and 'google' in config:
            self.token_file = config['google'].get('token_file', self.token_file)
            self.client_secrets = config['google'].get('client_file', self.client_secrets)
            
            # Allow modification if explicitly enabled
            if config['google'].get('gmail', {}).get('allow_modify', False):
                self.scopes.append('https://www.googleapis.com/auth/gmail.modify')
            
            # Allow scope override from config if provided
            if 'scopes' in config['google']:
                self.scopes = config['google']['scopes']

    def get_credentials(self):
        """Get valid user credentials from storage or run flow."""
        if not HAS_LIBS:
            raise ImportError("Google authentication libraries are not installed.")
            
        creds = None
        # The file google_token.json stores the user's access and refresh tokens.
        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_file(self.token_file, self.scopes)
            except Exception as e:
                print(f"[GOOGLE AUTH] Failed to load token file: {e}")
                creds = None
        
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    from google.auth.transport.requests import Request
                    creds.refresh(Request())
                except Exception as e:
                    # This is the critical hotfix: catch RefreshError (expired/revoked)
                    print(f"[GOOGLE AUTH] Token refresh failed: {e}")
                    raise e # Re-raise to be caught by Brain init
            else:
                if not os.path.exists(self.client_secrets):
                    raise FileNotFoundError(f"Missing {self.client_secrets}. Please provide Google OAuth credentials.json")
                
                if not self.allow_interactive_login:
                    raise RuntimeError(
                        "google_oauth_setup_required: missing or invalid Google token. "
                        "Run scripts/google_oauth_setup.py to authenticate."
                    )

                try:
                    flow = InstalledAppFlow.from_client_secrets_file(self.client_secrets, self.scopes)
                    flow.redirect_uri = f'http://localhost:60040/'
                    auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
                    with open("storage/current_oauth_url.txt", "w") as f:
                        f.write(auth_url)
                    print(f"[GOOGLE AUTH] Expected state: {flow.state}", flush=True)
                    print(f"[GOOGLE AUTH] URL saved to storage/current_oauth_url.txt", flush=True)
                    
                    try:
                        # Try local server with fixed port
                        print(f"[GOOGLE AUTH] Starting local server on port 60040...", flush=True)
                        creds = flow.run_local_server(port=60040, open_browser=False, timeout_seconds=300)
                    except Exception as e:
                        print(f"[GOOGLE AUTH] Local server flow failed: {e}", flush=True)
                        raise e
                except Exception as e:
                    print(f"[GOOGLE AUTH] Failed to run auth flow: {e}", flush=True)
                    raise e
            
            # Save the credentials for the next run if we successfully refreshed/got new ones
            if creds and creds.valid:
                print(f"[GOOGLE AUTH] Authentication successful. Attempting to save token to {self.token_file}...", flush=True)
                os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
                try:
                    with open(self.token_file, 'w') as token:
                        token.write(creds.to_json())
                    print(f"[GOOGLE AUTH] Token successfully saved to {os.path.abspath(self.token_file)}", flush=True)
                except Exception as e:
                    print(f"[GOOGLE AUTH] CRITICAL: Failed to save token to {self.token_file}: {e}", flush=True)
                    raise e
        
        return creds

    def build_service(self, service_name, version):
        """Build a Google API service."""
        creds = self.get_credentials()
        return build(service_name, version, credentials=creds)
